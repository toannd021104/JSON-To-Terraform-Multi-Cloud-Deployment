import subprocess
import json
import sys
from typing import List, Dict

def get_openstack_resources():
    """Fetch available images and flavors from OpenStack"""
    try:
        print("\nChecking available OpenStack resources...")
        
        # Get list of available images
        cmd = "openstack image list -f json"
        images = json.loads(subprocess.check_output(cmd, shell=True, text=True))
        
        # Get list of available flavors
        cmd = "openstack flavor list -f json"
        flavors = json.loads(subprocess.check_output(cmd, shell=True, text=True))
        
        return images, flavors
        
    except Exception as e:
        print(f"\nCritical OpenStack connection error: {e}")
        print("Please ensure you have:")
        print("- Sourced your openrc file")
        print("- Installed OpenStack CLI")
        sys.exit(1)

def validate_resources(topology: Dict) -> Dict:
    images, flavors = get_openstack_resources()
    validation_result = {
        'valid': True,
        'instances': [],
        'messages': []
    }

    print("\nValidating resources...")
    
    for instance in topology.get('instances', []):
        instance_result = {
            'name': instance['name'],
            'original_spec': instance
        }
        
        # Validate image
        if 'image' in instance:
            matched_image = next((img for img in images if img['Name'] == instance['image']), None)
            if matched_image:
                instance_result['image'] = matched_image['Name']
            else:
                validation_result['valid'] = False
                validation_result['messages'].append(f"Image '{instance['image']}' not found")
        
        # Validate flavor (CPU, RAM, Disk)
        if all(k in instance for k in ['cpu', 'ram', 'disk']):
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
        
        validation_result['instances'].append(instance_result)
    
    return validation_result