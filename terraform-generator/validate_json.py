import json
import ipaddress
import os
import subprocess
from jsonschema import validate, ValidationError
from typing import Tuple, List, Dict

# JSON schema to validate topology.json
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
                    "cloud_init": {"type": "string"},
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
                    "keypair": {"type": "string"},
                    "security_groups": {"type": "array", "items": {"type": "string"}},
                    "floating_ip": {"type": ["string", "boolean"]}
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

# Validate IPv4 format
def validate_ip(ip: str) -> bool:
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ValueError:
        return False

# Validate CIDR format
def validate_cidr(cidr: str) -> bool:
    try:
        ipaddress.IPv4Network(cidr, strict=False)
        return True
    except ValueError:
        return False

# Check if an IP belongs to a given CIDR
def check_ip_in_cidr(ip: str, cidr: str) -> bool:
    try:
        return ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(cidr, strict=False)
    except ValueError:
        return False

# Validate a cloud-init file using `cloud-init schema`
def validate_cloud_init_file(cloud_init_path: str, provider: str) -> str:
    path = os.path.join(provider, "cloud_init", cloud_init_path)
    if not os.path.isfile(path):
        return f"Cloud-init file '{path}' not found"
    try:
        result = subprocess.run(
            ["cloud-init", "schema", "--config-file", path, "--annotate"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return f"Schema error in cloud-init '{path}':\n{result.stderr.strip()}"
    except Exception as e:
        return f"Error validating cloud-init file '{path}': {str(e)}"
    return None

# Validate the entire topology.json
def validate_topology_file(file_path: str, provider: str) -> Tuple[bool, List[str]]:
    errors = []

    # Step 1: Load JSON file
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return False, ["File 'topology.json' not found"]
    except json.JSONDecodeError as e:
        return False, [f"JSON syntax error: {str(e)}"]

    # Step 2: Validate schema
    try:
        validate(instance=data, schema=TOPOLOGY_SCHEMA)
    except ValidationError as e:
        errors.append(f"Schema error: {e.message} at {e.json_path}")

    # Step 3: Collect network definitions and track used IPs
    network_info = {net["name"]: net for net in data.get("networks", [])}
    used_ips = {}

    # Step 4: Validate instances
    for instance in data.get("instances", []):
        for net in instance.get("networks", []):
            net_name = net["name"]
            ip = net["ip"]

            if net_name not in network_info:
                errors.append(f"Instance '{instance['name']}': Network '{net_name}' does not exist")
                continue

            if not validate_ip(ip):
                errors.append(f"Instance '{instance['name']}': IP '{ip}' is invalid")
                continue

            cidr = network_info[net_name]["cidr"]
            if not check_ip_in_cidr(ip, cidr):
                errors.append(f"Instance '{instance['name']}': IP '{ip}' is outside CIDR '{cidr}'")

            if net_name not in used_ips:
                used_ips[net_name] = set()
            if ip in used_ips[net_name]:
                errors.append(f"Instance '{instance['name']}': IP '{ip}' is duplicated in network '{net_name}'")
            used_ips[net_name].add(ip)

        # Validate cloud-init if provided
        cloud_init_file = instance.get("cloud_init")
        if cloud_init_file:
            err = validate_cloud_init_file(cloud_init_file, provider)
            if err:
                errors.append(f"Instance '{instance['name']}': {err}")
        # Validate floating IP if provided
        floating_ip = instance.get("floating_ip", None)
        if floating_ip is not None:
            if isinstance(floating_ip, str):
                if not validate_ip(floating_ip):
                    errors.append(f"Instance '{instance['name']}': floating_ip '{floating_ip}' is not a valid IP address")
            elif not isinstance(floating_ip, bool):
                errors.append(f"Instance '{instance['name']}': floating_ip must be an IP address (string) or true/false (boolean)")
    # Step 5: Validate gateway IPs in networks
    for net_name, network in network_info.items():
        gw_ip = network["gateway_ip"]
        if not validate_ip(gw_ip):
            errors.append(f"Network '{net_name}': Gateway IP '{gw_ip}' is invalid")
        elif not check_ip_in_cidr(gw_ip, network["cidr"]):
            errors.append(f"Network '{net_name}': Gateway IP '{gw_ip}' is outside CIDR")

    # Step 6: Validate routers
    for router in data.get("routers", []):
        for net in router.get("networks", []):
            net_name = net["name"]
            ip = net["ip"]

            if net_name not in network_info:
                errors.append(f"Router '{router['name']}': Network '{net_name}' does not exist")
                continue

            if not validate_ip(ip):
                errors.append(f"Router '{router['name']}': IP '{ip}' is invalid")
                continue

            if ip != network_info[net_name]["gateway_ip"]:
                errors.append(f"Router '{router['name']}': IP '{ip}' must match the gateway IP of network '{net_name}'")

            if net_name in used_ips and ip in used_ips[net_name]:
                errors.append(f"Router '{router['name']}': IP '{ip}' is already used in network '{net_name}'")

    return (len(errors) == 0, errors)
