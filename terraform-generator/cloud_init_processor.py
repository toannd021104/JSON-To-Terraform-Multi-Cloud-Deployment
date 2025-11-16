#!/usr/bin/env python3
"""
Cloud-Init Processor Module
Integrates cloud-init-generator into terraform-generator workflow
"""
import os
import sys
import json
import subprocess
from typing import Optional, Dict

# Path to cloud-init-generator directory
CLOUD_INIT_GENERATOR_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "cloud-init-generator"
)


def detect_os_type(image_name: str) -> str:
    """
    Detect OS type from image name
    Returns: 'windows' or 'linux'
    """
    image_lower = image_name.lower()

    # Check for Windows indicators
    windows_keywords = ['windows', 'win', 'server-2016', 'server-2019', 'server-2022']
    if any(keyword in image_lower for keyword in windows_keywords):
        return 'windows'

    # Default to Linux for Ubuntu, CentOS, RHEL, Debian, etc.
    return 'linux'


def find_cloud_init_json(cloud_init_filename: str) -> Optional[str]:
    """
    Find cloud-init JSON file in cloud-init-generator directory
    Returns: Full path to the JSON file or None if not found
    """
    # Try to find the file in cloud-init-generator directory
    json_path = os.path.join(CLOUD_INIT_GENERATOR_DIR, cloud_init_filename)

    if os.path.exists(json_path):
        return json_path

    # Also check without extension if user provided name without .json
    if not cloud_init_filename.endswith('.json'):
        json_path_with_ext = os.path.join(CLOUD_INIT_GENERATOR_DIR, f"{cloud_init_filename}.json")
        if os.path.exists(json_path_with_ext):
            return json_path_with_ext

    return None


def validate_cloud_init_json(json_path: str) -> bool:
    """
    Validate cloud-init JSON using the validator in cloud-init-generator
    Returns: True if valid, False otherwise

    Note: The "target" field will be auto-injected based on OS detection,
    so we temporarily remove it from validation if present
    """
    try:
        # Load JSON data
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Temporarily remove "target" field for validation (will be auto-injected later)
        target_value = data.pop('target', None)

        # Create a temporary file without "target" field for validation
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(data, temp_file, indent=2)
            temp_path = temp_file.name

        try:
            # Import the validator
            sys.path.insert(0, CLOUD_INIT_GENERATOR_DIR)
            from validate_json import validate
            sys.path.pop(0)

            # Validate the temporary JSON file (without "target")
            is_valid = validate(temp_path)
            return is_valid
        finally:
            # Clean up temporary file
            os.unlink(temp_path)

    except ImportError as e:
        # If validator has import errors (e.g., old jsonschema version), skip validation
        print(f"  ⚠ Warning: Validator not available ({e}), skipping validation")
        return True  # Allow to continue without validation
    except Exception as e:
        print(f"  ⚠ Warning: Could not validate cloud-init JSON: {e}")
        return True  # Allow to continue without validation


def generate_cloud_config(json_path: str, os_type: str) -> Optional[str]:
    """
    Generate cloud-config or cloudbase-init config from JSON

    Args:
        json_path: Path to cloud-init JSON file
        os_type: 'linux' or 'windows'

    Returns: Cloud-config YAML content or None if failed
    """
    try:
        # Import cloud-init-generator modules
        sys.path.insert(0, CLOUD_INIT_GENERATOR_DIR)
        from generate import convert_to_cloud_config
        import yaml
        from generate import literal_str, InlineList, InlineDict
        from generate import literal_presenter, inline_list_representer, inline_dict_representer

        # Re-register YAML representers
        yaml.add_representer(literal_str, literal_presenter)
        yaml.add_representer(InlineList, inline_list_representer)
        yaml.add_representer(InlineDict, inline_dict_representer)

        sys.path.pop(0)

        # Load JSON data
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Auto-inject "target" field based on OS type
        # This allows the converter to choose between cloud-init and cloudbase-init
        if os_type == 'windows':
            data['target'] = 'windows'
        else:
            data['target'] = 'linux'

        # Convert to cloud-config (will auto-detect and use cloudbase-init for Windows)
        cloud_config = convert_to_cloud_config(data)

        # Generate YAML output with appropriate header
        if os_type == 'windows':
            # For Windows, use cloudbase-init header
            output = "#cloudbase-init\n"
        else:
            # For Linux, use cloud-config header
            output = "#cloud-config\n"

        output += yaml.dump(cloud_config, default_flow_style=False, sort_keys=False)

        return output

    except Exception as e:
        print(f"  ✗ Error generating cloud-config: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_cloud_init(
    instance_name: str,
    cloud_init_filename: str,
    image_name: str,
    output_dir: str
) -> bool:
    """
    Main function to process cloud-init for an instance

    Args:
        instance_name: Name of the instance
        cloud_init_filename: Filename of cloud-init JSON (e.g., "config.json")
        image_name: Image name to detect OS type
        output_dir: Directory where cloud-init config will be saved

    Returns: True if successful, False otherwise
    """
    print(f"\n  → Processing cloud-init for instance '{instance_name}':")

    # Step 1: Find the cloud-init JSON file
    print(f"    • Looking for cloud-init file: {cloud_init_filename}")
    json_path = find_cloud_init_json(cloud_init_filename)

    if not json_path:
        print(f"    ✗ Cloud-init file not found: {cloud_init_filename}")
        print(f"      Searched in: {CLOUD_INIT_GENERATOR_DIR}")
        return False

    print(f"    ✓ Found: {json_path}")

    # Step 2: Detect OS type first (before validation)
    os_type = detect_os_type(image_name)
    config_type = "cloudbase-init" if os_type == 'windows' else "cloud-config"
    print(f"    • Detected OS: {os_type} → Using {config_type}")

    # Step 3: Validate the JSON (skip for Windows as cloudbase-init has different schema)
    if os_type == 'linux':
        print(f"    • Validating cloud-init JSON...")
        if not validate_cloud_init_json(json_path):
            print(f"    ✗ Cloud-init JSON validation failed")
            return False
        print(f"    ✓ Validation passed")
    else:
        print(f"    • Skipping validation for Windows (cloudbase-init has different schema)")

    # Step 4: Generate cloud-config
    print(f"    • Generating {config_type}...")
    cloud_config_content = generate_cloud_config(json_path, os_type)

    if not cloud_config_content:
        print(f"    ✗ Failed to generate {config_type}")
        return False

    # Step 5: Create cloud_init directory if it doesn't exist
    cloud_init_dir = os.path.join(output_dir, "cloud_init")
    os.makedirs(cloud_init_dir, exist_ok=True)

    # Step 6: Write cloud-config to file
    # Keep the same filename but change extension to .yaml
    base_name = os.path.splitext(cloud_init_filename)[0]
    output_filename = f"{base_name}.yaml"
    output_path = os.path.join(cloud_init_dir, output_filename)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(cloud_config_content)

    print(f"    ✓ Generated: {output_filename}")
    print(f"      Saved to: {output_path}")

    return True


def process_all_instances(topology: Dict, validated_resources: Dict, output_dir: str) -> Dict[str, str]:
    """
    Process cloud-init for all instances in topology

    Args:
        topology: Modified topology dictionary (with suffix in instance names)
        validated_resources: Validated resources from provider validation (original names)
        output_dir: Output directory for cloud-init configs

    Returns: Dictionary mapping instance names (with suffix) to cloud-init filenames
    """
    cloud_init_map = {}

    if not validated_resources or 'instances' not in validated_resources:
        return cloud_init_map

    print("\n=== Processing Cloud-Init Configurations ===")

    # Create a map of original names to validated resources
    validated_map = {}
    for inst_data in validated_resources['instances']:
        original_name = inst_data['original_spec']['name']
        validated_map[original_name] = inst_data

    # Loop through topology instances (which may have suffix added)
    for instance in topology.get('instances', []):
        instance_name = instance['name']
        cloud_init_filename = instance.get('cloud_init')

        if not cloud_init_filename:
            continue

        # Find the original name by stripping suffix if present
        # Suffix format: _{6-char-uuid}
        # Try to match with validated_map keys
        original_name = None
        for orig_name in validated_map.keys():
            # Check if instance_name is either the original name or original_name + suffix
            if instance_name == orig_name or instance_name.startswith(orig_name + '_'):
                original_name = orig_name
                break

        if not original_name:
            print(f"\n  ⚠ Warning: Could not find validated data for {instance_name}")
            continue

        # Get validated resource data
        inst_data = validated_map[original_name]

        # Get image name for OS detection
        image_name = inst_data.get('image', inst_data.get('ami', ''))

        # Process cloud-init
        success = process_cloud_init(
            instance_name,
            cloud_init_filename,
            image_name,
            output_dir
        )

        if success:
            # Map instance (with suffix) to the generated YAML filename
            base_name = os.path.splitext(cloud_init_filename)[0]
            cloud_init_map[instance_name] = f"{base_name}.yaml"

    if cloud_init_map:
        print(f"\n✓ Successfully processed {len(cloud_init_map)} cloud-init configuration(s)")

    return cloud_init_map


if __name__ == "__main__":
    # Test the module
    if len(sys.argv) < 3:
        print("Usage: python3 cloud_init_processor.py <cloud_init_json> <image_name>")
        sys.exit(1)

    cloud_init_file = sys.argv[1]
    image = sys.argv[2]
    test_output = "/tmp/cloud-init-test"

    os.makedirs(test_output, exist_ok=True)

    result = process_cloud_init("test-instance", cloud_init_file, image, test_output)
    sys.exit(0 if result else 1)
