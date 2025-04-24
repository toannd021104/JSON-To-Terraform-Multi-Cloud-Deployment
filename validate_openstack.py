#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import json
import sys
from typing import List, Dict

def get_openstack_resources():
    """Lấy danh sách images và flavors từ OpenStack"""
    try:
        print("\n Đang kiểm tra resources trong OpenStack...")
        
        # Lấy danh sách images
        cmd = "openstack image list -f json"
        images = json.loads(subprocess.check_output(cmd, shell=True, text=True))
        
        # Lấy danh sách flavors
        cmd = "openstack flavor list -f json"
        flavors = json.loads(subprocess.check_output(cmd, shell=True, text=True))
        
        return images, flavors
        
    except Exception as e:
        print(f"\Lỗi nghiêm trọng khi kết nối OpenStack: {e}")
        print("Hãy chắc chắn bạn đã:")
        print("- Source file openrc")
        print("- Cài đặt OpenStack CLI")
        sys.exit(1)

def validate_resources(topology: Dict) -> Dict:
    """Kiểm tra resources và trả về kết quả chi tiết"""
    images, flavors = get_openstack_resources()
    validation_result = {
        'valid': True,
        'instances': [],
        'messages': []
    }

    print("\n Kiểm tra topology.json:")
    
    for instance in topology.get('instances', []):
        instance_result = {
            'name': instance['name'],
            'valid': True,
            'image_status': None,
            'flavor_status': None,
            'issues': [],
            'original_spec': instance  # Lưu thông tin gốc của instance
        }
        
        # Kiểm tra image
        if 'image' in instance:
            matched_image = next((img for img in images if img['Name'] == instance['image']), None)
            if matched_image:
                instance_result['image_status'] = {
                    'id': matched_image['ID'],
                    'name': matched_image['Name'],
                    'status': 'VALID'
                }
                # Thêm trường image vào kết quả
                instance_result['image'] = matched_image['Name']
            else:
                instance_result['valid'] = False
                instance_result['issues'].append(f"Image '{instance['image']}' không tồn tại")
        
        # Kiểm tra flavor
        if 'cpu' in instance and 'ram' in instance:
            required_ram = instance['ram'] * 1024
            matched_flavor = next(
                (flv for flv in flavors 
                 if int(flv['VCPUs']) == instance['cpu'] 
                 and abs(int(flv['RAM']) - required_ram) <= 512),
                None
            )
            
            if matched_flavor:
                instance_result['flavor_status'] = {
                    'name': matched_flavor['Name'],
                    'vcpus': matched_flavor['VCPUs'],
                    'ram_mb': matched_flavor['RAM'],
                    'status': 'VALID'
                }
                # Thêm trường flavor vào kết quả
                instance_result['flavor'] = matched_flavor['Name']
            else:
                instance_result['valid'] = False
                instance_result['issues'].append(
                    f"Không có flavor phù hợp cho {instance['cpu']}vCPU/{instance['ram']}GB RAM"
                )
        
        if not instance_result['valid']:
            validation_result['valid'] = False
            validation_result['messages'].extend(instance_result['issues'])
        
        validation_result['instances'].append(instance_result)
    
    return validation_result