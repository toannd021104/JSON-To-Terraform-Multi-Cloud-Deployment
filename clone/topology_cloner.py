#!/usr/bin/env python3
"""
Tiện ích nhân bản topology và xử lý mạng cho multi-copy deployment.
Giữ nguyên logic gốc từ terraform_generator.py để tránh thay đổi hành vi.
"""
import json
import ipaddress
from typing import List, Tuple, Dict


def calculate_vpc_cidr(networks: List[Dict]) -> str:
    """
    AUTO-DETECT VPC CIDR (AWS Only)

    CHỨC NĂNG:
    - Phân tích tất cả subnets trong topology
    - Tìm dải mạng chung (supernet) bao phủ tất cả subnets

    AWS CONSTRAINTS:
    - VPC CIDR phải từ /16 đến /28
    - Không support /8 → Luôn return /16
    """
    if not networks:
        return "10.0.0.0/16"  # Default fallback

    # Parse all network CIDRs
    subnets = []
    for net in networks:
        try:
            subnet = ipaddress.ip_network(net['cidr'], strict=False)
            subnets.append(subnet)
        except ValueError:
            continue

    if not subnets:
        return "10.0.0.0/16"

    # Find common prefix (supernet)
    first_ip = str(subnets[0].network_address)
    octets = first_ip.split('.')

    # Check if all subnets share first 2 octets (Class B)
    common_prefix = f"{octets[0]}.{octets[1]}"
    for subnet in subnets:
        subnet_ip = str(subnet.network_address)
        if not subnet_ip.startswith(common_prefix):
            # Different ranges, use first octet /16 (AWS requires /16-/28)
            return f"{octets[0]}.0.0.0/16"

    # All subnets in same /16 range
    return f"{common_prefix}.0.0/16"


def collect_all_networks_and_routers(
    original_topology: Dict,
    suffixes: List[str],
    provider: str
) -> Tuple[List[Dict], List[Dict]]:
    """
    COLLECT NETWORKS & ROUTERS (Multi-copy deployment)

    CHỨC NĂNG:
    - Clone networks/routers với unique suffixes cho multi-copy deployment
    - Update network references trong routers
    - Remove OpenStack-specific fields khi generate cho AWS
    """
    all_networks = []
    all_routers = []

    for suffix in suffixes:
        # Clone networks with suffix
        for net in original_topology.get('networks', []):
            modified_net = net.copy()
            modified_net['name'] = f"{net['name']}_{suffix}"
            all_networks.append(modified_net)

        # Clone routers with suffix and update network references
        for router in original_topology.get('routers', []):
            modified_router = router.copy()
            modified_router['name'] = f"{router['name']}_{suffix}"
            modified_router['networks'] = [
                {**net_ref, 'name': f"{net_ref['name']}_{suffix}"}
                for net_ref in router.get('networks', [])
            ]
            # For AWS: remove OpenStack-specific fields (routes)
            if provider == 'aws':
                modified_router['routes'] = []
            all_routers.append(modified_router)

    return all_networks, all_routers


def modify_topology(topology: Dict, suffix: str) -> Dict:
    """Add unique suffix to all resource names in topology"""
    modified = json.loads(json.dumps(topology))  # Deep copy

    # Add suffix to instance names and their network references
    for inst in modified.get('instances', []):
        inst['name'] = f"{inst['name']}_{suffix}"
        for net in inst.get('networks', []):
            net['name'] = f"{net['name']}_{suffix}"

    # Add suffix to network names
    for net in modified.get('networks', []):
        net['name'] = f"{net['name']}_{suffix}"

    # Add suffix to router names and their network references
    for router in modified.get('routers', []):
        router['name'] = f"{router['name']}_{suffix}"
        for net in router.get('networks', []):
            net['name'] = f"{net['name']}_{suffix}"

    return modified
