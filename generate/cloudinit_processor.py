#!/usr/bin/env python3
"""
Cloud-Init Processor Module
Integrates cloud-init into generate workflow
"""
import os
import sys
import subprocess
from typing import Optional, Dict

# Rich library for beautiful CLI output
try:
    from rich.console import Console
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    console = None

# Thư mục chứa generator và user-data JSON (theo cấu trúc mới)
CLOUD_INIT_ROOT = os.path.dirname(__file__)
CLOUD_INIT_USERDATA_DIR = os.path.join(CLOUD_INIT_ROOT, "userdata")


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
    Find cloud-init JSON file in generate/userdata directory
    Returns: Full path to the JSON file or None if not found
    """
    # Try to find the file in generate/userdata directory
    json_path = os.path.join(CLOUD_INIT_USERDATA_DIR, cloud_init_filename)

    if os.path.exists(json_path):
        return json_path

    # Also check without extension if user provided name without .json
    if not cloud_init_filename.endswith('.json'):
        json_path_with_ext = os.path.join(CLOUD_INIT_USERDATA_DIR, f"{cloud_init_filename}.json")
        if os.path.exists(json_path_with_ext):
            return json_path_with_ext

    return None


def generate_cloud_config(json_path: str, os_type: str, output_path: str) -> bool:
    """
    Generate cloud-config using external cloudinit_generator.py script

    Args:
        json_path: Path to cloud-init JSON file
        os_type: 'linux' or 'windows'
        output_path: Path where YAML will be saved

    Returns: True if successful, False otherwise
    """
    try:
        # Path to generator script trong generate/
        generator_script = os.path.join(CLOUD_INIT_ROOT, "cloudinit_generator.py")

        if not os.path.exists(generator_script):
            if RICH_AVAILABLE:
                console.print(f"      [red]✗[/red] Generator script not found")
            else:
                print(f"    ✗ Generator script not found: {generator_script}")
            return False

        # Build command: python3 cloudinit_generator.py input.json -o output.yaml
        cmd = [
            sys.executable,  # Use same Python interpreter
            generator_script,
            json_path,
            "-o", output_path
        ]

        # Run the generator
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=CLOUD_INIT_ROOT
        )

        if result.returncode != 0:
            if RICH_AVAILABLE:
                console.print(f"      [red]✗[/red] Generator failed")
            else:
                print(f"    ✗ Generator failed:")
                if result.stderr:
                    print(f"      {result.stderr}")
            return False

        # Check if output file was created
        if not os.path.exists(output_path):
            if RICH_AVAILABLE:
                console.print(f"      [red]✗[/red] Output file not created")
            else:
                print(f"    ✗ Output file was not created: {output_path}")
            return False

        return True

    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"      [red]✗[/red] Error: {e}")
        else:
            print(f"    ✗ Error running generator: {e}")
            import traceback
            traceback.print_exc()
        return False


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
    if RICH_AVAILABLE:
        console.print(f"    [dim]•[/dim] {instance_name}: ", end="")
    else:
        print(f"\n  → Processing cloud-init for instance '{instance_name}':")
        print(f"    • Looking for cloud-init file: {cloud_init_filename}")

    # Step 1: Find the cloud-init JSON file
    json_path = find_cloud_init_json(cloud_init_filename)

    if not json_path:
        if RICH_AVAILABLE:
            console.print(f"[red]✗ not found[/red]")
        else:
            print(f"    ✗ Cloud-init file not found: {cloud_init_filename}")
            print(f"      Searched in: {CLOUD_INIT_GENERATOR_DIR}")
        return False

    if not RICH_AVAILABLE:
        print(f"    ✓ Found: {json_path}")

    # Step 2: Detect OS type
    os_type = detect_os_type(image_name)
    config_type = "cloudbase-init" if os_type == 'windows' else "cloud-config"
    if not RICH_AVAILABLE:
        print(f"    • Detected OS: {os_type} → Using {config_type}")

    # Step 3: Create cloud_init directory if it doesn't exist
    cloud_init_dir = os.path.join(output_dir, "cloud_init")
    os.makedirs(cloud_init_dir, exist_ok=True)

    # Step 4: Prepare output path
    base_name = os.path.splitext(cloud_init_filename)[0]
    output_filename = f"{base_name}.yaml"
    output_path = os.path.join(cloud_init_dir, output_filename)

    # Step 5: Generate cloud-config using external script
    if not RICH_AVAILABLE:
        print(f"    • Generating {config_type} (validation + conversion)...")
    success = generate_cloud_config(json_path, os_type, output_path)

    if not success:
        if RICH_AVAILABLE:
            console.print(f"[red]✗ failed[/red]")
        else:
            print(f"    ✗ Failed to generate {config_type}")
        return False

    if RICH_AVAILABLE:
        console.print(f"[green]✓[/green]")
    else:
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

    if RICH_AVAILABLE:
        console.print(f"\n[cyan]Processing cloud-init...[/cyan]")
    else:
        print("\n=== Processing Cloud-Init Configurations ===")

    # Create a map of original names to validated resources
    validated_map = {}
    for inst_data in validated_resources['instances']:
        original_name = inst_data['original_spec']['name']
        validated_map[original_name] = inst_data

    # Loop through topology instances (which may have suffix added)
    for instance in topology.get('instances', []):
        instance_name = instance['name']
        cloud_init_filename = instance.get('cloud-init') or instance.get('cloud_init')

        if not cloud_init_filename:
            continue

        # Find the original name by stripping suffix if present
        original_name = None
        for orig_name in validated_map.keys():
            if instance_name == orig_name or instance_name.startswith(orig_name + '_'):
                original_name = orig_name
                break

        if not original_name:
            if RICH_AVAILABLE:
                console.print(f"    [yellow]⚠[/yellow] {instance_name}: no validated data")
            else:
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
        if RICH_AVAILABLE:
            console.print(f"[green]✓[/green] {len(cloud_init_map)} cloud-init config(s) processed")
        else:
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
