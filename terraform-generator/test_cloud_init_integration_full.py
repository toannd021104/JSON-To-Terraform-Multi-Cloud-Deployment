#!/usr/bin/env python3
"""
Full Integration Test for Cloud-Init in Terraform Generator
Tests the complete flow of processing cloud-init configs
"""
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

import cloud_init_processor


def create_test_topology():
    """Create a test topology with cloud-init reference"""
    return {
        "instances": [
            {
                "name": "vm1_test123",  # Instance with suffix
                "image": "ubuntu-server-noble",
                "cpu": 1,
                "ram": 0.5,
                "disk": 5,
                "networks": [{"name": "net1_test123", "ip": "192.168.1.10"}],
                "keypair": "test-keypair",
                "security_groups": ["default"],
                "cloud_init": "test-config.json"
            }
        ],
        "networks": [
            {
                "name": "net1_test123",
                "cidr": "192.168.1.0/24",
                "pool": [],
                "gateway_ip": "192.168.1.1",
                "enable_dhcp": True
            }
        ],
        "routers": []
    }


def create_test_validated_resources():
    """Create test validated resources (original names without suffix)"""
    return {
        "valid": True,
        "instances": [
            {
                "name": "vm1",  # Original name without suffix
                "original_spec": {
                    "name": "vm1",
                    "image": "ubuntu-server-noble",
                    "cpu": 1,
                    "ram": 0.5,
                    "disk": 5,
                    "networks": [{"name": "net1", "ip": "192.168.1.10"}],
                    "keypair": "test-keypair",
                    "security_groups": ["default"],
                    "cloud_init": "test-config.json"
                },
                "image": "ubuntu-server-noble",
                "flavor": "test-flavor"
            }
        ]
    }


def test_full_integration():
    """Test full integration flow"""
    print("=" * 60)
    print("FULL INTEGRATION TEST: Cloud-Init in Terraform Generator")
    print("=" * 60)

    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"\n1. Created test directory: {temp_dir}")

        # Create test topology
        topology = create_test_topology()
        topology_path = os.path.join(temp_dir, "topology.json")
        with open(topology_path, 'w') as f:
            json.dump(topology, f, indent=2)
        print(f"   ✓ Created test topology.json")

        # Create validated resources
        validated_resources = create_test_validated_resources()
        print(f"   ✓ Created validated resources")

        # Process cloud-init for all instances
        print("\n2. Processing cloud-init configurations...")
        cloud_init_map = cloud_init_processor.process_all_instances(
            topology,
            validated_resources,
            temp_dir
        )

        # Verify results
        print("\n3. Verifying results...")

        if not cloud_init_map:
            print("   ✗ FAILED: No cloud-init configs were generated")
            return False

        print(f"   ✓ Generated {len(cloud_init_map)} cloud-init config(s)")

        # Check if the mapping is correct (should use name WITH suffix)
        expected_instance_name = "vm1_test123"
        if expected_instance_name not in cloud_init_map:
            print(f"   ✗ FAILED: Instance '{expected_instance_name}' not in cloud_init_map")
            print(f"   Cloud-init map keys: {list(cloud_init_map.keys())}")
            return False

        print(f"   ✓ Correctly mapped instance '{expected_instance_name}'")

        # Check if YAML file was created
        expected_yaml_filename = cloud_init_map[expected_instance_name]
        yaml_path = os.path.join(temp_dir, "cloud_init", expected_yaml_filename)

        if not os.path.exists(yaml_path):
            print(f"   ✗ FAILED: YAML file not found at {yaml_path}")
            return False

        print(f"   ✓ YAML file created: {expected_yaml_filename}")

        # Verify YAML content
        with open(yaml_path, 'r') as f:
            yaml_content = f.read()

        if not yaml_content.startswith("#cloud-config"):
            print(f"   ✗ FAILED: YAML doesn't start with #cloud-config header")
            return False

        print(f"   ✓ YAML content is valid cloud-config")

        # Check if content has expected sections
        expected_sections = ["hostname:", "users:", "timezone:"]
        missing_sections = [s for s in expected_sections if s not in yaml_content]

        if missing_sections:
            print(f"   ⚠ Warning: Some expected sections not found: {missing_sections}")
        else:
            print(f"   ✓ All expected sections found in YAML")

        # Print sample of YAML content
        print("\n4. Sample YAML content (first 20 lines):")
        print("-" * 60)
        for i, line in enumerate(yaml_content.split('\n')[:20]):
            print(f"   {line}")
        print("-" * 60)

        print("\n" + "=" * 60)
        print("✓ FULL INTEGRATION TEST PASSED!")
        print("=" * 60)

        return True


if __name__ == "__main__":
    try:
        success = test_full_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
