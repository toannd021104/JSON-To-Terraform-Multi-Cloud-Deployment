#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
import boto3
from botocore.exceptions import ClientError

class AWSUtils:
    # AMI mặc định
    DEFAULT_AMIS = {
        'ubuntu': 'ami-03f8acd418785369b',  # Ubuntu 22.04 LTS x86_64
        'windows': 'ami-005148a6a3abb558a',  # Windows Server 2022 Base
    }
    
    def __init__(self):
        try:
            self.ec2_client = boto3.client('ec2')
        except Exception as e:
            print(f"\n Không thể kết nối đến AWS: {e}")
            print(" Hãy chắc chắn bạn đã:")
            print("- Cài đặt AWS CLI và cấu hình (aws configure)")
            print("- Có quyền truy cập EC2")
            print("- Cài đặt boto3 (pip install boto3)")
            sys.exit(1)

    def detect_ami_type(self, image_name):
        """Tự động phát hiện loại AMI từ tên"""
        image_name_lower = image_name.lower()
        if 'ubuntu' in image_name_lower:
            return 'ubuntu'
        elif 'windows' in image_name_lower or 'win' in image_name_lower:
            return 'windows'
        return None

    def get_default_ami(self, ami_type):
        """Lấy AMI mặc định theo loại"""
        return self.DEFAULT_AMIS.get(ami_type)

    def check_ami_exists(self, ami_id):
        """Kiểm tra AMI cụ thể có tồn tại không"""
        try:
            self.ec2_client.describe_images(ImageIds=[ami_id])
            return True
        except ClientError as e:
            if 'InvalidAMIID' in str(e):
                return False
            print(f" Lỗi khi kiểm tra AMI {ami_id}: {e}")
            return False

    def validate_ami(self, image_name):
        """Kiểm tra AMI với cơ chế fallback"""
        # Phát hiện loại AMI
        ami_type = self.detect_ami_type(image_name)
        
        # Nếu không phát hiện được loại, kiểm tra trực tiếp
        if not ami_type:
            if self.check_ami_exists(image_name):
                return image_name, True
            return None, False
        
        # Kiểm tra AMI được chỉ định
        if self.check_ami_exists(image_name):
            return image_name, True
        
        # Nếu không tìm thấy, sử dụng AMI mặc định
        default_ami = self.get_default_ami(ami_type)
        if default_ami and self.check_ami_exists(default_ami):
            print(f" Sử dụng AMI mặc định cho {ami_type}: {default_ami}")
            return default_ami, True
        
        return None, False

    def find_matching_instance_types(self, cpu, ram):
        """Tìm instance types phù hợp nhanh bằng bộ lọc kết hợp"""
        try:
            ram_mib = ram * 1024  # Chuyển GB sang MiB
            
            # Lấy danh sách instance types phù hợp cả CPU và RAM
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
            
            # Ưu tiên T-series trước
            t_series = [it for it in instances if it.startswith(('t2.', 't3'))]
            others = [it for it in instances if not it.startswith(('t2', 't3'))]
            
            return t_series + others
            
        except ClientError as e:
            print(f" Lỗi khi lấy instance types: {e}")
            return []

    def validate_resources(self, topology):
        """Kiểm tra resources trong topology.json"""
        print("\n🔎 Kiểm tra topology.json (chế độ thông minh):")
        has_error = False
        
        # Kết quả validation
        result = {
            'instances': []
        }
        
        # Kiểm tra từng instance
        for instance in topology.get('instances', []):
            print(f"\n Instance: {instance['name']}")
            
            instance_result = {
                'name': instance['name'],
                'original_spec': instance  # Lưu thông tin gốc của instance
            }
            
            # Kiểm tra AMI
            if 'image' in instance:
                ami_id, is_valid = self.validate_ami(instance['image'])
                
                if is_valid:
                    print(f" AMI hợp lệ: {ami_id}")
                    instance_result['ami'] = ami_id
                else:
                    detected_type = self.detect_ami_type(instance['image'])
                    if detected_type:
                        print(f" LỖI: Không tìm thấy AMI {detected_type} phù hợp")
                    else:
                        print(f" LỖI: AMI '{instance['image']}' không tồn tại")
                    has_error = True
            
            # Kiểm tra instance type
            if 'cpu' in instance and 'ram' in instance:
                matching_types = self.find_matching_instance_types(
                    instance['cpu'], 
                    instance['ram']
                )
                
                if matching_types:
                    print(f" Cấu hình {instance['cpu']}vCPU/{instance['ram']}GB RAM hợp lệ")
                    print(f"   Instance types phù hợp (3 đầu tiên): {', '.join(matching_types[:3])}")
                    if len(matching_types) > 3:
                        print(f"   (Tổng cộng {len(matching_types)} options)")
                    
                    instance_result['instance_type'] = matching_types[0]
                else:
                    print(f" LỖI: Không tìm thấy instance type phù hợp")
                    print(f"   Yêu cầu: {instance['cpu']}vCPU/{instance['ram']}GB RAM")
                    has_error = True

            # Thêm instance vào kết quả
            result['instances'].append(instance_result)

        if has_error:
            print("\n Đã phát hiện lỗi trong topology.json! Vui lòng sửa trước khi tiếp tục.")
            sys.exit(1)
        else:
            print("\n Tất cả resources đều hợp lệ!")
            
        return result

if __name__ == "__main__":
    try:
        with open('topology.json') as f:
            topology = json.load(f)
    except FileNotFoundError:
        print(" Không tìm thấy file topology.json")
        sys.exit(1)
    except json.JSONDecodeError:
        print(" Lỗi định dạng JSON trong file topology.json")
        sys.exit(1)
    
    aws = AWSUtils()
    aws.validate_resources(topology)