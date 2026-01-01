#!/usr/bin/env python3
"""
Kiểm tra trùng lặp tên, CIDR, IP giữa các bản sao Terraform
"""

import json
import os
import sys
import glob
import re

def extract_resources_from_state(state_file):
    """Trích xuất tên, CIDR, IP từ terraform.tfstate"""
    resources = {
        'names': [],
        'cidrs': [],
        'ips': []
    }
    
    try:
        with open(state_file) as f:
            state = json.load(f)
        
        for resource in state.get('resources', []):
            res_type = resource.get('type', '')
            
            for instance in resource.get('instances', []):
                attrs = instance.get('attributes', {})
                
                # Lấy tên
                if 'name' in attrs:
                    resources['names'].append(attrs['name'])
                
                # Lấy CIDR
                if 'cidr' in attrs:
                    resources['cidrs'].append(attrs['cidr'])
                
                # Lấy IP
                if 'fixed_ip_v4' in attrs:
                    resources['ips'].append(attrs['fixed_ip_v4'])
                if 'access_ip_v4' in attrs and attrs['access_ip_v4']:
                    resources['ips'].append(attrs['access_ip_v4'])
                    
    except Exception as e:
        pass
    
    return resources

def extract_resources_from_tf(tf_file):
    """Trích xuất từ file main.tf"""
    resources = {
        'names': [],
        'cidrs': [],
        'ips': []
    }
    
    try:
        with open(tf_file) as f:
            content = f.read()
        
        # Tìm tên resource
        name_pattern = r'name\s*=\s*"([^"]+)"'
        resources['names'] = re.findall(name_pattern, content)
        
        # Tìm CIDR
        cidr_pattern = r'cidr\s*=\s*"([0-9./]+)"'
        resources['cidrs'] = re.findall(cidr_pattern, content)
        
        # Tìm IP
        ip_pattern = r'ip_address\s*=\s*"([0-9.]+)"'
        resources['ips'] = re.findall(ip_pattern, content)
        
    except Exception as e:
        pass
    
    return resources

def find_duplicates(items):
    """Tìm các phần tử trùng lặp"""
    seen = set()
    duplicates = []
    for item in items:
        if item in seen:
            duplicates.append(item)
        seen.add(item)
    return duplicates

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: scenario2_check_duplicates.py <test_dir>"}))
        sys.exit(1)
    
    test_dir = sys.argv[1]
    
    all_names = []
    all_cidrs = []
    all_ips = []
    
    # Tìm tất cả state files
    state_files = glob.glob(f"{test_dir}/**/terraform.tfstate", recursive=True)
    
    for state_file in state_files:
        resources = extract_resources_from_state(state_file)
        all_names.extend(resources['names'])
        all_cidrs.extend(resources['cidrs'])
        all_ips.extend(resources['ips'])
    
    # Nếu không có state files, thử đọc từ main.tf
    if not state_files:
        tf_files = glob.glob(f"{test_dir}/**/main.tf", recursive=True)
        for tf_file in tf_files:
            resources = extract_resources_from_tf(tf_file)
            all_names.extend(resources['names'])
            all_cidrs.extend(resources['cidrs'])
            all_ips.extend(resources['ips'])
    
    # Tìm trùng lặp
    dup_names = find_duplicates(all_names)
    dup_cidrs = find_duplicates(all_cidrs)
    dup_ips = find_duplicates(all_ips)
    
    result = {
        'names': len(dup_names),
        'cidrs': len(dup_cidrs),
        'ips': len(dup_ips),
        'details': {
            'duplicate_names': list(set(dup_names)),
            'duplicate_cidrs': list(set(dup_cidrs)),
            'duplicate_ips': list(set(dup_ips))
        },
        'total_checked': {
            'names': len(all_names),
            'cidrs': len(all_cidrs),
            'ips': len(all_ips)
        }
    }
    
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
