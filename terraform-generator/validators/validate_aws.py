#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
import boto3
from botocore.exceptions import ClientError

class AWSUtils:
    # Default AMIs (updated January 2026)
    DEFAULT_AMIS = {
        'ubuntu': 'ami-0030e4319cbf4dbf2',  # Ubuntu 22.04 LTS x86_64 (us-east-1)
        'windows': 'ami-005148a6a3abb558a',  # Windows Server 2022 Base
    }
    
    def __init__(self):
        try:
            self.ec2_client = boto3.client('ec2')
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
        """Return default AMI based on type"""
        return self.DEFAULT_AMIS.get(ami_type)

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

