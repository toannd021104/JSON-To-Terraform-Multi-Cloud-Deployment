#!/usr/bin/env python3
"""
Kiểm tra tính đồng nhất cấu trúc giữa các bản sao Terraform
"""

import json
import os
import sys
import glob
import re

def extract_structure_from_state(state_file):
    """Trích xuất cấu trúc từ terraform.tfstate"""
    structure = {
        'resource_types': {},
        'network_count': 0,
        'subnet_count': 0,
        'router_count': 0,
        'instance_count': 0,
        'router_interface_count': 0
    }
    
    try:
        with open(state_file) as f:
            state = json.load(f)
        
        for resource in state.get('resources', []):
            res_type = resource.get('type', '')
            instance_count = len(resource.get('instances', []))
            
            if res_type not in structure['resource_types']:
                structure['resource_types'][res_type] = 0
            structure['resource_types'][res_type] += instance_count
            
            # Đếm theo loại
            if 'network' in res_type.lower() and 'subnet' not in res_type.lower():
                structure['network_count'] += instance_count
            elif 'subnet' in res_type.lower():
                structure['subnet_count'] += instance_count
            elif 'router' in res_type.lower() and 'interface' not in res_type.lower():
                structure['router_count'] += instance_count
            elif 'interface' in res_type.lower():
                structure['router_interface_count'] += instance_count
            elif 'instance' in res_type.lower() or 'compute' in res_type.lower():
                structure['instance_count'] += instance_count
                
    except Exception as e:
        pass
    
    return structure

def extract_structure_from_tf(tf_file):
    """Trích xuất cấu trúc từ main.tf"""
    structure = {
        'resource_types': {},
        'network_count': 0,
        'subnet_count': 0,
        'router_count': 0,
        'instance_count': 0,
        'router_interface_count': 0
    }
    
    try:
        with open(tf_file) as f:
            content = f.read()
        
        # Đếm resource blocks
        resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"'
        resources = re.findall(resource_pattern, content)
        
        for res_type, res_name in resources:
            if res_type not in structure['resource_types']:
                structure['resource_types'][res_type] = 0
            structure['resource_types'][res_type] += 1
            
            # Đếm theo loại
            if 'network' in res_type.lower() and 'subnet' not in res_type.lower():
                structure['network_count'] += 1
            elif 'subnet' in res_type.lower():
                structure['subnet_count'] += 1
            elif 'router' in res_type.lower() and 'interface' not in res_type.lower():
                structure['router_count'] += 1
            elif 'interface' in res_type.lower():
                structure['router_interface_count'] += 1
            elif 'instance' in res_type.lower() or 'compute' in res_type.lower():
                structure['instance_count'] += 1
                
    except Exception as e:
        pass
    
    return structure

def compare_structures(structures):
    """So sánh cấu trúc giữa các bản sao"""
    if not structures:
        return True, []
    
    reference = structures[0]
    differences = []
    
    for i, struct in enumerate(structures[1:], 2):
        # So sánh số lượng resource types
        if struct['resource_types'] != reference['resource_types']:
            differences.append({
                'copy': i,
                'type': 'resource_types_mismatch',
                'expected': reference['resource_types'],
                'actual': struct['resource_types']
            })
        
        # So sánh từng loại
        for key in ['network_count', 'subnet_count', 'router_count', 'instance_count', 'router_interface_count']:
            if struct[key] != reference[key]:
                differences.append({
                    'copy': i,
                    'type': f'{key}_mismatch',
                    'expected': reference[key],
                    'actual': struct[key]
                })
    
    return len(differences) == 0, differences

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: scenario2_check_consistency.py <test_dir>"}))
        sys.exit(1)
    
    test_dir = sys.argv[1]
    structures = []
    folder_names = []
    
    # Tìm tất cả state files
    state_files = sorted(glob.glob(f"{test_dir}/**/terraform.tfstate", recursive=True))
    
    for state_file in state_files:
        structure = extract_structure_from_state(state_file)
        structures.append(structure)
        folder_names.append(os.path.dirname(state_file))
    
    # Nếu không có state files, thử đọc từ main.tf
    if not state_files:
        tf_files = sorted(glob.glob(f"{test_dir}/**/main.tf", recursive=True))
        for tf_file in tf_files:
            structure = extract_structure_from_tf(tf_file)
            structures.append(structure)
            folder_names.append(os.path.dirname(tf_file))
    
    # So sánh cấu trúc
    consistent, differences = compare_structures(structures)
    
    result = {
        'consistent': consistent,
        'copies_checked': len(structures),
        'folders': folder_names,
        'differences': differences,
        'reference_structure': structures[0] if structures else {},
        'all_structures': structures
    }
    
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
