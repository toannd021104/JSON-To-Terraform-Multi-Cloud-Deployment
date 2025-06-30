import json
import ipaddress
import os
import subprocess
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
                    "cloud_init": {"type": "string"},  # Trường này không bắt buộc
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
    """Kiểm tra địa chỉ IPv4 hợp lệ"""
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
    """Kiểm tra IP có thuộc dải CIDR không"""
    try:
        return ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(cidr, strict=False)
    except ValueError:
        return False

def validate_cloud_init_file(cloud_init_path: str, provider: str) -> str:
    """
    Kiểm tra file cloud-init hợp lệ bằng lệnh cloud-init schema.
    Trả về None nếu hợp lệ, trả về chuỗi lỗi nếu không hợp lệ hoặc không đọc được file.
    File cloud-init được tìm trong thư mục <provider>/cloud_init
    """
    abs_path = os.path.join(provider, "cloud_init", cloud_init_path)
    if not os.path.isfile(abs_path):
        return f"File cloud-init '{abs_path}' không tồn tại"
    try:
        result = subprocess.run(
            ["cloud-init", "schema", "--config-file", abs_path, "--annotate"],
            capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            return f"File cloud-init '{abs_path}' lỗi schema:\n{result.stderr.strip()}"
    except Exception as e:
        return f"Lỗi khi kiểm tra cloud-init '{abs_path}': {str(e)}"
    return None



def validate_topology_file(file_path: str, provider: str) -> Tuple[bool, List[str]]:
    """
    Kiểm tra hợp lệ file topology.json.
    Trả về (True, []) nếu hợp lệ; (False, [danh sách lỗi]) nếu có lỗi.
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

    # 2. Kiểm tra schema tổng thể
    try:
        validate(instance=data, schema=TOPOLOGY_SCHEMA)
    except ValidationError as e:
        errors.append(f"Lỗi schema: {e.message} tại {e.json_path}")

    # 3. Tạo dict tra cứu thông tin network theo tên
    network_info = {net["name"]: net for net in data.get("networks", [])}
    used_ips = {}  # Dùng để kiểm tra trùng IP trên từng network

    # 4. Kiểm tra từng instance
    for instance in data.get("instances", []):
        # Kiểm tra từng network trong instance
        for net in instance.get("networks", []):
            net_name = net["name"]
            ip = net["ip"]

            # Kiểm tra network tồn tại
            if net_name not in network_info:
                errors.append(f"Instance {instance['name']}: Network '{net_name}' không tồn tại")
                continue

            # Kiểm tra IP hợp lệ
            if not validate_ip(ip):
                errors.append(f"Instance {instance['name']}: IP '{ip}' không hợp lệ")
                continue

            # Kiểm tra IP thuộc dải CIDR
            cidr = network_info[net_name]["cidr"]
            if not check_ip_in_cidr(ip, cidr):
                errors.append(f"Instance {instance['name']}: IP '{ip}' không thuộc dải mạng '{cidr}'")

            # Kiểm tra trùng IP trong cùng network
            if net_name not in used_ips:
                used_ips[net_name] = set()
            if ip in used_ips[net_name]:
                errors.append(f"Instance {instance['name']}: IP '{ip}' trùng lặp trong network '{net_name}'")
            used_ips[net_name].add(ip)

        # Kiểm tra file cloud_init nếu có
        cloud_init_file = instance.get("cloud_init")
        if cloud_init_file:
            err = validate_cloud_init_file(cloud_init_file, provider)
            if err:
                errors.append(f"Instance {instance['name']}: {err}")

    # 5. Kiểm tra network (gateway IP)
    for net_name, network in network_info.items():
        gw_ip = network["gateway_ip"]
        if not validate_ip(gw_ip):
            errors.append(f"Network {net_name}: Gateway IP '{gw_ip}' không hợp lệ")
        elif not check_ip_in_cidr(gw_ip, network["cidr"]):
            errors.append(f"Network {net_name}: Gateway IP '{gw_ip}' không thuộc dải mạng")

    # 6. Kiểm tra router
    for router in data.get("routers", []):
        for net in router.get("networks", []):
            net_name = net["name"]
            ip = net["ip"]

            # Kiểm tra network tồn tại
            if net_name not in network_info:
                errors.append(f"Router {router['name']}: Network '{net_name}' không tồn tại")
                continue

            # Kiểm tra IP hợp lệ
            if not validate_ip(ip):
                errors.append(f"Router {router['name']}: IP '{ip}' không hợp lệ")
                continue

            # Kiểm tra IP trùng với gateway IP
            if ip != network_info[net_name]["gateway_ip"]:
                errors.append(f"Router {router['name']}: IP '{ip}' phải trùng gateway IP của network '{net_name}'")

            # Kiểm tra IP trùng với IP đã dùng trong network
            if net_name in used_ips and ip in used_ips[net_name]:
                errors.append(f"Router {router['name']}: IP '{ip}' trùng với IP đã sử dụng trong network '{net_name}'")

    # Trả về kết quả kiểm tra
    return (len(errors) == 0, errors)
