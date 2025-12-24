import subprocess
import json
import sys
import os
from typing import List, Dict

# Import config manager
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from openstack_config_manager import OpenStackConfigManager
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False

def load_openstack_credentials():
    """Load OpenStack credentials from openstack_config.json"""
    # If already in environment, use that
    if os.environ.get("OS_AUTH_URL"):
        return
    
    # Try to load from config manager
    if not CONFIG_MANAGER_AVAILABLE:
        print("Warning: Config manager not available")
        return
    
    try:
        mgr = OpenStackConfigManager()
        if not mgr.load_config():
            print("Warning: No OpenStack config found")
            return
        
        profile = mgr.get_active_profile()
        if not profile:
            print("Warning: No active profile")
            return
        
        # Set environment variables for OpenStack CLI
        os.environ['OS_AUTH_URL'] = profile['auth_url']
        os.environ['OS_PROJECT_NAME'] = profile['project_name']
        os.environ['OS_USERNAME'] = profile['username']
        os.environ['OS_PASSWORD'] = profile['password']
        os.environ['OS_REGION_NAME'] = profile['region']
        os.environ['OS_USER_DOMAIN_NAME'] = profile.get('user_domain_name', 'Default')
        os.environ['OS_PROJECT_DOMAIN_ID'] = profile.get('project_domain_id', 'default')
        os.environ['OS_IDENTITY_API_VERSION'] = '3'
        
        print(f"Loaded credentials from profile: {mgr.active_profile}")
    except Exception as e:
        print(f"Warning: Could not load config: {e}")

def get_openstack_resources():
    """Fetch available images and flavors from OpenStack (best-effort per resource type)"""
    # Load credentials automatically
    load_openstack_credentials()

    print("\nChecking available OpenStack resources...")

    # Create environment dict with OpenStack credentials
    env = os.environ.copy()

    images = []
    flavors = []

    # Try to fetch images (non-fatal if it fails)
    try:
        images = json.loads(subprocess.check_output(
            "openstack image list -f json", shell=True, text=True, timeout=50, env=env, stderr=subprocess.DEVNULL
        ))
    except subprocess.TimeoutExpired:
        print("Warning: OpenStack image list timed out; skipping image validation.")
    except Exception as e:
        print(f"Warning: OpenStack image list failed ({e}); skipping image validation.")

    # Try to fetch flavors separately
    try:
        flavors = json.loads(subprocess.check_output(
            "openstack flavor list -f json", shell=True, text=True, timeout=50, env=env, stderr=subprocess.DEVNULL
        ))
    except subprocess.TimeoutExpired:
        print("Warning: OpenStack flavor list timed out; cannot match cpu/ram/disk to flavor.")
    except Exception as e:
        print(f"Warning: OpenStack flavor list failed ({e}); cannot match cpu/ram/disk to flavor.")

    if images or flavors:
        print(f"Found {len(images)} images and {len(flavors)} flavors")
    else:
        print("Warning: No OpenStack images or flavors retrieved; will use topology values directly.")

    return images, flavors

def validate_resources(topology: Dict) -> Dict:
    images, flavors = get_openstack_resources()
    validation_result = {
        'valid': True,
        'instances': [],
        'messages': []
    }

    # If no images/flavors fetched (timeout/error), skip validation and use topology values
    images_available = len(images) > 0
    flavors_available = len(flavors) > 0
    skip_validation = not images_available and not flavors_available

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
            if not images_available:
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
        
        # Validate flavor - support both direct "flavor" field and cpu/ram/disk matching
        if 'flavor' in instance:
            # Direct flavor name specified
            if not flavors_available:
                instance_result['flavor'] = instance['flavor']
            else:
                matched_flavor = next((flv for flv in flavors if flv['Name'] == instance['flavor']), None)
                if matched_flavor:
                    instance_result['flavor'] = matched_flavor['Name']
                else:
                    available = [f"{flv['Name']}({flv['VCPUs']}cpu,{flv['RAM']}MB,{flv['Disk']}GB)" for flv in flavors]
                    validation_result['valid'] = False
                    validation_result['messages'].append(
                        f"Flavor '{instance['flavor']}' not found for {instance['name']}. Available: {', '.join(available)}"
                    )
        elif all(k in instance for k in ['cpu', 'ram', 'disk']):
            # Match by CPU/RAM/Disk specs
            required_cpu = instance['cpu']
            required_ram = instance['ram'] * 1024  # GB to MB
            required_disk = instance['disk']  # GB

            if not flavors_available:
                # No flavors available, cannot match automatically
                validation_result['valid'] = False
                validation_result['messages'].append(
                    f"Cannot validate flavor for {instance['name']} - OpenStack flavor API unavailable. "
                    f"Use 'flavor' field directly instead of cpu/ram/disk."
                )
            else:
                # Find best matching flavor
                matched_flavor = next(
                    (flv for flv in flavors
                     if int(flv['VCPUs']) >= required_cpu
                     and int(flv['RAM']) >= required_ram
                     and int(flv['Disk']) >= required_disk),
                    None
                )

                if matched_flavor:
                    instance_result['flavor'] = matched_flavor['Name']
                    print(f"  {instance['name']}: matched flavor '{matched_flavor['Name']}' "
                          f"({matched_flavor['VCPUs']}cpu, {matched_flavor['RAM']}MB, {matched_flavor['Disk']}GB)")
                else:
                    available = [f"{flv['Name']}({flv['VCPUs']}cpu,{flv['RAM']}MB,{flv['Disk']}GB)" for flv in flavors]
                    validation_result['valid'] = False
                    validation_result['messages'].append(
                        f"No flavor matches {instance['name']} specs (cpu={required_cpu}, ram={required_ram}MB, disk={required_disk}GB). "
                        f"Available: {', '.join(available)}"
                    )

        # Add cloud_init (null if not present)
        instance_result['cloud_init'] = instance.get('cloud_init', None)

        validation_result['instances'].append(instance_result)
    
    return validation_result
