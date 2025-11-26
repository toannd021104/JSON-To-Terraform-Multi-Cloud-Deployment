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
                    "ram": {"type": "number", "minimum": 0.5},
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
                    "routes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["destination", "nexthop"],
                            "properties": {
                                "destination": {
                                    "type": "string",
                                    "pattern": "^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}/[0-9]{1,2}$"
                                },
                                "nexthop": {
                                    "type": "string",
                                    "pattern": "^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}$"
                                }
                            }
                        }
                    }
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

# Validate a cloud-init file - check if it exists in cloud-init-generator folder
def validate_cloud_init_file(cloud_init_path: str, provider: str) -> str:
    """
    Check if cloud-init JSON file exists in cloud-init-generator directory.
    The actual validation will be done by cloud_init_processor during generation.
    """
    # Look for the file in cloud-init-generator directory (at project root)
    cloud_init_gen_dir = os.path.join(os.path.dirname(__file__), "..", "..", "cloud-init-generator")

    # Try with the exact filename
    full_path = os.path.join(cloud_init_gen_dir, cloud_init_path)
    if os.path.isfile(full_path):
        return None  # File exists, validation will happen during generation

    # Try with .json extension if not provided
    if not cloud_init_path.endswith('.json'):
        full_path_with_ext = os.path.join(cloud_init_gen_dir, f"{cloud_init_path}.json")
        if os.path.isfile(full_path_with_ext):
            return None

    # File not found
    return f"Cloud-init file '{cloud_init_path}' not found in cloud-init-generator directory"

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
        path = ".".join(str(p) for p in e.path) if e.path else "root"
        errors.append(f"Schema error: {e.message} at {path}")

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
    # Track router IPs per network to detect duplicates
    router_ips = {}  # {network_name: set(ips)}

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

            # Check router IP is within network CIDR
            cidr = network_info[net_name]["cidr"]
            if not check_ip_in_cidr(ip, cidr):
                errors.append(f"Router '{router['name']}': IP '{ip}' is outside network '{net_name}' CIDR '{cidr}'")
                continue

            # Check for duplicate router IPs in same network
            if net_name not in router_ips:
                router_ips[net_name] = set()
            if ip in router_ips[net_name]:
                errors.append(f"Router '{router['name']}': IP '{ip}' is already used by another router in network '{net_name}'")
            router_ips[net_name].add(ip)

            # Check router IP doesn't conflict with instance IPs
            if net_name in used_ips and ip in used_ips[net_name]:
                errors.append(f"Router '{router['name']}': IP '{ip}' conflicts with an instance IP in network '{net_name}'")

    # Step 7: Validate static routes
    for router in data.get("routers", []):
        router_networks = {net["name"]: net["ip"] for net in router.get("networks", [])}

        for route in router.get("routes", []):
            dest = route.get("destination", "")
            nexthop = route.get("nexthop", "")

            # Validate destination CIDR
            if not validate_cidr(dest):
                errors.append(f"Router '{router['name']}': Route destination '{dest}' is not a valid CIDR")
                continue

            # Validate nexthop IP
            if not validate_ip(nexthop):
                errors.append(f"Router '{router['name']}': Route nexthop '{nexthop}' is not a valid IP")
                continue

            # Check nexthop is reachable (must be in one of router's connected networks)
            nexthop_reachable = False
            for net_name in router_networks:
                if net_name in network_info:
                    net_cidr = network_info[net_name]["cidr"]
                    if check_ip_in_cidr(nexthop, net_cidr):
                        nexthop_reachable = True
                        break

            if not nexthop_reachable:
                errors.append(f"Router '{router['name']}': Route nexthop '{nexthop}' is not reachable from any connected network")

    return (len(errors) == 0, errors)
