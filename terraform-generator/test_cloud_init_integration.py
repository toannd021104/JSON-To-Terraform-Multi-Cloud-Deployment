#!/usr/bin/env python3
"""
Test script to verify cloud-init integration without running terraform
"""
import json
import os
import sys
import shutil
import tempfile
import cloud_init_processor
from validate_openstack import validate_resources

def test_cloud_init_integration():
    """Test the full cloud-init integration workflow"""

    print("\n" + "="*60)
    print("TESTING CLOUD-INIT INTEGRATION")
    print("="*60)

    # Step 1: Load topology.json
    print("\n[1/5] Loading topology.json...")
    with open("topology.json", "r") as f:
        topology = json.load(f)
    print(f"  ✓ Loaded topology with {len(topology['instances'])} instance(s)")

    # Step 2: Simulate resource validation (OpenStack)
    print("\n[2/5] Validating OpenStack resources...")
    validated_resources = validate_resources(topology)

    if not validated_resources.get('valid', False):
        print("  ✗ Resource validation failed:")
        for msg in validated_resources.get('messages', []):
            print(f"    - {msg}")
        return False

    print(f"  ✓ Validated {len(validated_resources['instances'])} instance(s)")

    # Step 3: Create temporary test directory
    print("\n[3/5] Creating temporary test directory...")
    test_dir = tempfile.mkdtemp(prefix="cloud-init-test-")
    print(f"  ✓ Created: {test_dir}")

    try:
        # Copy topology to test directory
        with open(os.path.join(test_dir, 'topology.json'), 'w') as f:
            json.dump(topology, f, indent=2)

        # Step 4: Process cloud-init configurations
        print("\n[4/5] Processing cloud-init configurations...")
        cloud_init_map = cloud_init_processor.process_all_instances(
            topology,
            validated_resources,
            test_dir
        )

        if not cloud_init_map:
            print("  ⚠ No cloud-init configurations found")
        else:
            print(f"  ✓ Processed {len(cloud_init_map)} cloud-init config(s)")
            for instance_name, yaml_file in cloud_init_map.items():
                print(f"    • {instance_name} → {yaml_file}")

        # Step 5: Verify generated files
        print("\n[5/5] Verifying generated files...")
        cloud_init_dir = os.path.join(test_dir, "cloud_init")

        if not os.path.exists(cloud_init_dir):
            print("  ⚠ cloud_init/ directory was not created")
        else:
            yaml_files = [f for f in os.listdir(cloud_init_dir) if f.endswith('.yaml')]
            print(f"  ✓ Found {len(yaml_files)} YAML file(s) in cloud_init/")

            for yaml_file in yaml_files:
                yaml_path = os.path.join(cloud_init_dir, yaml_file)
                with open(yaml_path, 'r') as f:
                    content = f.read()
                    lines = content.split('\n')
                    print(f"\n    📄 {yaml_file} ({len(lines)} lines)")
                    print(f"       First line: {lines[0]}")

                    # Show first few lines
                    print("       Preview:")
                    for i, line in enumerate(lines[:8]):
                        print(f"         {line}")
                    if len(lines) > 8:
                        print(f"         ... ({len(lines) - 8} more lines)")

        print("\n" + "="*60)
        print("✓ CLOUD-INIT INTEGRATION TEST PASSED")
        print("="*60)
        print(f"\nTest files preserved at: {test_dir}")
        print("You can inspect the generated YAML files manually.\n")

        return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Note: We don't clean up the test directory so user can inspect results
    # finally:
    #     shutil.rmtree(test_dir)


if __name__ == "__main__":
    success = test_cloud_init_integration()
    sys.exit(0 if success else 1)
