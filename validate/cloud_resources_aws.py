#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
import boto3
from botocore.exceptions import ClientError

class AWSUtils:
    # Default AMIs by region (Ubuntu 22.04 LTS Jammy)
    DEFAULT_AMIS_BY_REGION = {
        'ubuntu': {
            'us-east-1': 'ami-0030e4319cbf4dbf2',
            'us-east-2': 'ami-0862be96e41dcbf74',
            'us-west-1': 'ami-04fdea8e25817cd69',
            'us-west-2': 'ami-0aff18ec83b712f05',
            'ap-south-1': 'ami-0f58b397bc5c1f2e8',
            'ap-northeast-1': 'ami-0d52744d6551d851e',
            'ap-northeast-2': 'ami-0c9c942bd7bf113a2',
            'ap-southeast-1': 'ami-0497a974f8d5dcef8',
            'ap-southeast-2': 'ami-001f2488b35ca8aad',
            'eu-central-1': 'ami-0084a47cc718c111a',
            'eu-west-1': 'ami-0d64bb532e0502c46',
            'eu-west-2': 'ami-0b78e9d8eee5a5c8a',
            'eu-west-3': 'ami-00ac45f3035ff009e',
            'sa-east-1': 'ami-0c820c196a818d66a',
        },
        'windows': {
            'us-east-1': 'ami-005148a6a3abb558a',      # Windows Server 2022 Base
            'us-east-2': 'ami-0552d42eca49fc689',
            'us-west-1': 'ami-0ee5d1b5c2fc79df0',
            'us-west-2': 'ami-0a8b8b29c9e9c8f51',
            'ap-south-1': 'ami-0d9d8b3f1b2c5e9a1',
            'ap-northeast-1': 'ami-0c1e3f5b8d9a7e6f2',
            'ap-northeast-2': 'ami-0a8d9e7f6c5b4a3e2',
            'ap-southeast-1': 'ami-0b9e8d7f6a5c4e3d2',
            'ap-southeast-2': 'ami-0c9f8e7d6b5a4f3e2',
            'eu-central-1': 'ami-0d8f9e7c6b5a4d3f2',
            'eu-west-1': 'ami-0e9f8d7c6a5b4e3d2',
            'eu-west-2': 'ami-0f8e9d7c6b5a4f3e2',
            'eu-west-3': 'ami-089e8f7d6c5b4a3f2',
            'sa-east-1': 'ami-0b8e9f7d6c5a4e3f2',
        }
    }
    
    def __init__(self, target_region='us-west-2'):
        try:
            self.ec2_client = boto3.client('ec2', region_name=target_region)
            self.region = target_region
        except Exception as e:
            print(f"\n Unable to connect to AWS: {e}")
            print(" Make sure you have:")
            print("- Installed and configured AWS CLI (aws configure)")
            print("- EC2 access permissions")
            print("- Installed boto3 (pip install boto3)")
            sys.exit(1)

    def detect_ami_type(self, image_name):
        """Automatically detect AMI type from name"""
        image_name_lower = image_name.lower()
        if 'ubuntu' in image_name_lower:
            return 'ubuntu'
        elif 'windows' in image_name_lower or 'win' in image_name_lower:
            return 'windows'
        return None

    def get_default_ami(self, ami_type):
        """Return default AMI based on type and current region"""
        ami_map = self.DEFAULT_AMIS_BY_REGION.get(ami_type, {})
        return ami_map.get(self.region, ami_map.get('us-west-2'))

    def check_ami_exists(self, ami_id):
        """Check if a specific AMI exists"""
        try:
            self.ec2_client.describe_images(ImageIds=[ami_id])
            return True
        except ClientError as e:
            if 'InvalidAMIID' in str(e):
                return False
            print(f" Error checking AMI {ami_id}: {e}")
            return False

    def validate_ami(self, image_name):
        """Validate AMI, fallback to default if needed"""
        ami_type = self.detect_ami_type(image_name)

        # If AMI type is not detected, check directly
        if not ami_type:
            if self.check_ami_exists(image_name):
                return image_name, True
            return None, False

        # Check user-specified AMI
        if self.check_ami_exists(image_name):
            return image_name, True

        # If not found, fallback to default
        default_ami = self.get_default_ami(ami_type)
        if default_ami and self.check_ami_exists(default_ami):
            print(f" Using default AMI for {ami_type}: {default_ami}")
            return default_ami, True

        return None, False

    def find_matching_instance_types(self, cpu, ram):
        """Find instance types matching given CPU and RAM"""
        try:
            ram_mib = ram * 1024  # Convert GB to MiB

            paginator = self.ec2_client.get_paginator('describe_instance_types')
            instances = []

            for page in paginator.paginate(
                Filters=[
                    {'Name': 'vcpu-info.default-vcpus', 'Values': [str(cpu)]},
                    {'Name': 'memory-info.size-in-mib', 'Values': [f"{ram_mib}"]},
                    {'Name': 'current-generation', 'Values': ['true']}
                ]
            ):
                instances.extend([it['InstanceType'] for it in page['InstanceTypes']])

            # Prioritize T-series
            t_series = [it for it in instances if it.startswith(('t2.', 't3'))]
            others = [it for it in instances if not it.startswith(('t2', 't3'))]

            return t_series + others

        except ClientError as e:
            print(f" Error retrieving instance types: {e}")
            return []

    def validate_resources(self, topology):
        """Validate resources defined in topology.json"""
        print("\n Validating AWS resources...")
        has_error = False

        result = {
            'instances': []
        }

        for instance in topology.get('instances', []):
            print(f"\n Instance: {instance['name']}")

            instance_result = {
                'name': instance['name'],
                'original_spec': instance
            }

            # AMI check
            if 'image' in instance:
                ami_id, is_valid = self.validate_ami(instance['image'])

                if is_valid:
                    print(f" Valid AMI: {ami_id}")
                    instance_result['ami'] = ami_id
                else:
                    detected_type = self.detect_ami_type(instance['image'])
                    if detected_type:
                        print(f" ERROR: No valid AMI found for type '{detected_type}'")
                    else:
                        print(f" ERROR: AMI '{instance['image']}' does not exist")
                    has_error = True

            # Instance type check
            if 'cpu' in instance and 'ram' in instance:
                matching_types = self.find_matching_instance_types(
                    instance['cpu'],
                    instance['ram']
                )

                if matching_types:
                    print(f" Valid configuration: {instance['cpu']} vCPU / {instance['ram']} GB RAM")
                    print(f"   Matching instance types (top 3): {', '.join(matching_types[:3])}")
                    if len(matching_types) > 3:
                        print(f"   (Total {len(matching_types)} options)")
                    instance_result['instance_type'] = matching_types[0]
                else:
                    print(f" ERROR: No instance types found matching requirements")
                    print(f"   Requested: {instance['cpu']} vCPU / {instance['ram']} GB RAM")
                    has_error = True

            result['instances'].append(instance_result)

        if has_error:
            print("\n Errors detected in topology.json! Please fix before proceeding.")
            sys.exit(1)
        else:
            print("\n All resources are valid!")

        return result

