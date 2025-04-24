import json
import ipaddress
from jsonschema import validate, ValidationError
from typing import Tuple, List, Dict

# Định nghĩa schema cho topology.json
TOPOLOGY_SCHEMA = {
    "type": "object",
    "required": ["instances", "networks", "routers"],
    "properties": {
        "instances": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "image", "cpu", "ram", "disk", "networks"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "image": {"type": "string", "minLength": 1},
                    "cpu": {"type": "integer", "minimum": 1},
                    "ram": {"type": "integer", "minimum": 1},
                    "disk": {"type": "integer", "minimum": 1},
                    "networks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name", "ip"],
                            "properties": {
                                "name": {"type": "string", "minLength": 1},
                                "ip": {"type": "string", "pattern": "^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}$"}
                            }
                        }
                    }
                }
            }
        },
        "networks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "cidr", "gateway_ip"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "cidr": {"type": "string", "pattern": "^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}/[0-9]{1,2}$"},
                    "gateway_ip": {"type": "string", "pattern": "^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}$"},
                    "enable_dhcp": {"type": "boolean"},
                    "pool": {"type": "array"}
                }
            }
        },
        "routers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "networks", "external"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "networks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name", "ip"],
                            "properties": {
                                "name": {"type": "string", "minLength": 1},
                                "ip": {"type": "string", "pattern": "^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}$"}
                            }
                        }
                    },
                    "external": {"type": "boolean"},
                    "routes": {"type": "array"}
                }
            }
        }
    }
}

def validate_ip(ip: str) -> bool:
    """Kiểm tra IPv4 hợp lệ"""
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ValueError:
        return False

def validate_cidr(cidr: str) -> bool:
    """Kiểm tra CIDR hợp lệ"""
    try:
        ipaddress.IPv4Network(cidr, strict=False)
        return True
    except ValueError:
        return False

def check_ip_in_cidr(ip: str, cidr: str) -> bool:
    """Kiểm tra IP thuộc dải CIDR"""
    try:
        return ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(cidr, strict=False)
    except ValueError:
        return False

def validate_topology_file(file_path: str) -> Tuple[bool, List[str]]:
    """
    Validate topology.json file
    Returns:
        Tuple[bool, List[str]]: (True nếu valid, False nếu có lỗi), Danh sách lỗi
    """
    errors = []
    
    # 1. Kiểm tra file tồn tại và đọc được
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return False, ["File topology.json không tồn tại"]
    except json.JSONDecodeError as e:
        return False, [f"Lỗi cú pháp JSON: {str(e)}"]
    
    # 2. Validate schema
    try:
        validate(instance=data, schema=TOPOLOGY_SCHEMA)
    except ValidationError as e:
        errors.append(f"Lỗi schema: {e.message} tại {e.json_path}")
    
    # 3. Validate logic
    network_info = {net["name"]: net for net in data.get("networks", [])}
    used_ips = {}  # {"network_name": set(["ip1", "ip2"])}

    # Validate instances
    for instance in data.get("instances", []):
        for net in instance.get("networks", []):
            net_name = net["name"]
            ip = net["ip"]
            
            # Check network exists
            if net_name not in network_info:
                errors.append(f"Instance {instance['name']}: Network '{net_name}' không tồn tại")
                continue
                
            # Check IP valid
            if not validate_ip(ip):
                errors.append(f"Instance {instance['name']}: IP '{ip}' không hợp lệ")
                continue
                
            # Check IP in CIDR
            cidr = network_info[net_name]["cidr"]
            if not check_ip_in_cidr(ip, cidr):
                errors.append(f"Instance {instance['name']}: IP '{ip}' không thuộc dải mạng '{cidr}'")
            
            # Check IP duplication
            if net_name not in used_ips:
                used_ips[net_name] = set()
            if ip in used_ips[net_name]:
                errors.append(f"Instance {instance['name']}: IP '{ip}' trùng lặp trong network '{net_name}'")
            used_ips[net_name].add(ip)
    
    # Validate networks
    for net_name, network in network_info.items():
        # Validate gateway IP
        gw_ip = network["gateway_ip"]
        if not validate_ip(gw_ip):
            errors.append(f"Network {net_name}: Gateway IP '{gw_ip}' không hợp lệ")
        elif not check_ip_in_cidr(gw_ip, network["cidr"]):
            errors.append(f"Network {net_name}: Gateway IP '{gw_ip}' không thuộc dải mạng")
    
    # Validate routers
    for router in data.get("routers", []):
        for net in router.get("networks", []):
            net_name = net["name"]
            ip = net["ip"]
            
            # Check network exists
            if net_name not in network_info:
                errors.append(f"Router {router['name']}: Network '{net_name}' không tồn tại")
                continue
                
            # Check IP valid
            if not validate_ip(ip):
                errors.append(f"Router {router['name']}: IP '{ip}' không hợp lệ")
                continue
                
            # Check IP matches gateway
            if ip != network_info[net_name]["gateway_ip"]:
                errors.append(f"Router {router['name']}: IP '{ip}' phải trùng gateway IP của network '{net_name}'")
            
            # Check IP duplication
            if net_name in used_ips and ip in used_ips[net_name]:
                errors.append(f"Router {router['name']}: IP '{ip}' trùng với IP đã sử dụng trong network '{net_name}'")

    return (len(errors) == 0, errors)