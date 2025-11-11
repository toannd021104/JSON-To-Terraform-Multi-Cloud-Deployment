import subprocess
import json
import sys
import os
from typing import List, Dict

def load_openstack_credentials():
    """Load OpenStack credentials from dacn-openrc.sh"""
    openrc_path = os.path.join(os.path.dirname(__file__), "dacn-openrc.sh")
    if not os.path.exists(openrc_path):
        print(f"\nWarning: {openrc_path} not found")
        return

    # Source the file and extract environment variables
    cmd = f"bash -c 'source {openrc_path} && env'"
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
        stdout, stderr = proc.communicate()

        if proc.returncode != 0:
            print(f"Warning: Failed to source openrc file: {stderr}")
            return

        os_vars_found = 0
        for line in stdout.split('\n'):
            if '=' in line:
                key, value = line.strip().split('=', 1)
                if key.startswith('OS_'):
                    os.environ[key] = value
                    os_vars_found += 1

        if os_vars_found > 0:
            print(f"Loaded {os_vars_found} OpenStack environment variables")
        else:
            print("Warning: No OpenStack credentials found in openrc file")

    except Exception as e:
        print(f"Warning: Could not load credentials from {openrc_path}: {e}")

def get_openstack_resources():
    """Fetch available images and flavors from OpenStack"""
    try:
        # Load credentials automatically
        load_openstack_credentials()

        print("\nChecking available OpenStack resources...")

        # Create environment dict with OpenStack credentials
        env = os.environ.copy()

        # Get list of available images with timeout
        cmd = "openstack image list -f json"
        images = json.loads(subprocess.check_output(
            cmd, shell=True, text=True, timeout=10, env=env, stderr=subprocess.DEVNULL
        ))

        # Get list of available flavors with timeout
        cmd = "openstack flavor list -f json"
        flavors = json.loads(subprocess.check_output(
            cmd, shell=True, text=True, timeout=10, env=env, stderr=subprocess.DEVNULL
        ))

        print(f"Found {len(images)} images and {len(flavors)} flavors")
        return images, flavors

    except subprocess.TimeoutExpired:
        print(f"\nWarning: OpenStack API timeout. Skipping resource validation.")
        print("Will use image/flavor names from topology.json directly.")
        return [], []
    except Exception as e:
        print(f"\nWarning: OpenStack connection error: {e}")
        print("Skipping resource validation. Will use values from topology.json directly.")
        return [], []

def validate_resources(topology: Dict) -> Dict:
    images, flavors = get_openstack_resources()
    validation_result = {
        'valid': True,
        'instances': [],
        'messages': []
    }

    # If no images/flavors fetched (timeout/error), skip validation and use topology values
    skip_validation = len(images) == 0 and len(flavors) == 0

    if skip_validation:
        print("\nSkipping validation - using values from topology.json directly")
    else:
        print("\nValidating resources...")

    for instance in topology.get('instances', []):
        instance_result = {
            'name': instance['name'],
            'original_spec': instance
        }

        # Validate or use image directly
        if 'image' in instance:
            if skip_validation:
                # Use image name directly from topology
                instance_result['image'] = instance['image']
            else:
                # Validate against available images
                matched_image = next((img for img in images if img['Name'] == instance['image']), None)
                if matched_image:
                    instance_result['image'] = matched_image['Name']
                else:
                    validation_result['valid'] = False
                    validation_result['messages'].append(f"Image '{instance['image']}' not found")
        
        # Validate or generate flavor name
        if all(k in instance for k in ['cpu', 'ram', 'disk']):
            if skip_validation:
                # Generate a simple flavor name from specs
                cpu = instance['cpu']
                ram = int(instance['ram'] * 1024)  # GB to MB
                disk = instance['disk']
                instance_result['flavor'] = f"m1.{cpu}cpu-{ram}mb-{disk}gb"
            else:
                # Validate against available flavors
                required_ram = instance['ram'] * 1024  # GB to MB
                required_disk = instance['disk']  # GB

                matched_flavor = next(
                    (flv for flv in flavors
                     if int(flv['VCPUs']) == instance['cpu']
                     and abs(int(flv['RAM']) - required_ram) <= 512
                     and int(flv['Disk']) >= required_disk),
                    None
                )

                if matched_flavor:
                    instance_result['flavor'] = matched_flavor['Name']
                else:
                    validation_result['valid'] = False
                    validation_result['messages'].append(f"No suitable flavor found for {instance['name']}")

        # Add cloud_init (null if not present)
        instance_result['cloud_init'] = instance.get('cloud_init', None)

        validation_result['instances'].append(instance_result)
    
    return validation_result