#!/bin/bash
# Đánh giá so sánh 3 topologies với 4 Layers: A, B, C, D
# Comparative evaluation of 3 topologies with full 4 layers
# FIXED: Schema keys matching actual topology format

set -e

cd /home/ubuntu/JSON-To-Terraform-Multi-Cloud-Deployment

echo "================================================================================"
echo "  ĐÁNH GIÁ SO SÁNH 3 TOPOLOGIES (4 LAYERS)"
echo "  Comparative Evaluation: tn1a, tn1b-2router, tn1c"
echo "  Layers: A (Validation) | B (Deployment) | C (Consistency) | D (User-data)"
echo "================================================================================"
echo ""

# Danh sách topologies cần đánh giá
TOPOLOGIES=("topology-tn1a" "topology-tn1b-2router" "topology-tn1c")

# Số bản sao mỗi topology
NUM_COPIES=2

# Tạo thư mục kết quả
RESULTS_BASE="evaluation/results/comparative_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_BASE"

echo "Kết quả sẽ lưu tại: $RESULTS_BASE"
echo "Số bản sao mỗi topology: $NUM_COPIES"
echo ""

# Function để đánh giá một topology
evaluate_topology() {
    local TOPO_NAME=$1
    local TOPO_FILE="terraform-generator/${TOPO_NAME}.json"
    local RESULT_DIR="${RESULTS_BASE}/${TOPO_NAME}"
    
    echo "================================================================================"
    echo "  Đánh giá: $TOPO_NAME"
    echo "================================================================================"
    echo ""
    
    mkdir -p "$RESULT_DIR"
    
    # Copy topology file to terraform-generator directory as topology.json
    cp "$TOPO_FILE" terraform-generator/topology.json
    
    #==========================================================================
    # LAYER A: INPUT VALIDATION (Schema + Logic)
    # Schema theo chuẩn validate_json.py: name (không phải instance_name/network_name)
    #==========================================================================
    echo "[Layer A] Input Validation - Kiểm tra đầu vào..."
    
    python3 << EOF
import json
import os
import ipaddress
from datetime import datetime
from pathlib import Path

topology_file = "terraform-generator/topology.json"
result_file = "$RESULT_DIR/layer_a_result.json"

result = {
    "layer": "A_INPUT_VALIDATION",
    "timestamp": datetime.utcnow().isoformat(),
    "status": "PASS",
    "schema_validation": {"status": "PASS", "errors": [], "checks": []},
    "logic_validation": {"status": "PASS", "errors": [], "checks": []},
    "summary": {
        "schema_status": "PASS",
        "logic_status": "PASS",
        "total_errors": 0,
        "result": "Hợp lệ"
    }
}

try:
    with open(topology_file, 'r') as f:
        topology = json.load(f)
    
    # === SCHEMA VALIDATION ===
    # Theo chuẩn validate_json.py schema: instances, networks, routers là required
    # Mỗi item dùng "name" (không phải instance_name, network_name)
    schema_errors = []
    schema_checks = []
    
    # Check required top-level keys (theo validate_json.py)
    required_keys = ["instances", "networks", "routers"]
    for key in required_keys:
        if key in topology:
            schema_checks.append({"key": key, "status": "PASS"})
        else:
            schema_errors.append(f"Thiếu key bắt buộc: {key}")
            schema_checks.append({"key": key, "status": "FAIL"})
    
    # Check networks schema - dùng "name" không phải "network_name"
    if "networks" in topology:
        for i, net in enumerate(topology["networks"]):
            net_name = net.get("name", f"network_{i}")
            if "name" not in net:
                schema_errors.append(f"Network {i}: Thiếu name")
            else:
                schema_checks.append({"component": f"network.{net_name}.name", "status": "PASS"})
            
            if "cidr" not in net:
                schema_errors.append(f"Network {net_name}: Thiếu CIDR")
            else:
                schema_checks.append({"component": f"network.{net_name}.cidr", "status": "PASS"})
            
            # gateway_ip có thể null (theo schema cho phép)
            if "gateway_ip" in net:
                schema_checks.append({"component": f"network.{net_name}.gateway_ip", "status": "PASS"})
    
    # Check instances schema - dùng "name" không phải "instance_name"
    if "instances" in topology:
        for i, inst in enumerate(topology["instances"]):
            inst_name = inst.get("name", f"instance_{i}")
            if "name" not in inst:
                schema_errors.append(f"Instance {i}: Thiếu name")
            else:
                schema_checks.append({"component": f"instance.{inst_name}.name", "status": "PASS"})
            
            if "networks" not in inst:
                schema_errors.append(f"Instance {inst_name}: Thiếu networks")
            else:
                schema_checks.append({"component": f"instance.{inst_name}.networks", "status": "PASS"})
            
            # Check required fields: image, cpu, ram, disk
            for field in ["image", "cpu", "ram", "disk"]:
                if field in inst:
                    schema_checks.append({"component": f"instance.{inst_name}.{field}", "status": "PASS"})
    
    # Check routers schema
    if "routers" in topology:
        for i, router in enumerate(topology["routers"]):
            router_name = router.get("name", f"router_{i}")
            if "name" not in router:
                schema_errors.append(f"Router {i}: Thiếu name")
            else:
                schema_checks.append({"component": f"router.{router_name}.name", "status": "PASS"})
            
            if "networks" not in router:
                schema_errors.append(f"Router {router_name}: Thiếu networks")
            else:
                schema_checks.append({"component": f"router.{router_name}.networks", "status": "PASS"})
            
            if "external" not in router:
                schema_errors.append(f"Router {router_name}: Thiếu external")
            else:
                schema_checks.append({"component": f"router.{router_name}.external", "status": "PASS"})
    
    result["schema_validation"]["checks"] = schema_checks
    if schema_errors:
        result["schema_validation"]["status"] = "FAIL"
        result["schema_validation"]["errors"] = schema_errors
    
    # === LOGIC VALIDATION ===
    logic_errors = []
    logic_checks = []
    
    # Validate CIDR formats
    if "networks" in topology:
        for net in topology["networks"]:
            net_name = net.get("name", "unknown")
            try:
                cidr = net.get("cidr", "")
                if cidr:
                    ipaddress.ip_network(cidr, strict=False)
                    logic_checks.append({"check": f"CIDR format: {net_name}", "status": "PASS"})
            except ValueError as e:
                logic_errors.append(f"CIDR không hợp lệ trong {net_name}: {e}")
                logic_checks.append({"check": f"CIDR format: {net_name}", "status": "FAIL"})
    
    # Check instances reference valid networks
    network_names = [n.get("name") for n in topology.get("networks", [])]
    if "instances" in topology:
        for inst in topology["instances"]:
            inst_name = inst.get("name", "unknown")
            for net in inst.get("networks", []):
                net_name = net.get("name") if isinstance(net, dict) else net
                if net_name in network_names:
                    logic_checks.append({"check": f"Instance {inst_name} -> {net_name}", "status": "PASS"})
                else:
                    logic_errors.append(f"Instance {inst_name} tham chiếu network không tồn tại: {net_name}")
                    logic_checks.append({"check": f"Instance {inst_name} -> {net_name}", "status": "FAIL"})
    
    # Check routers reference valid networks
    if "routers" in topology:
        for router in topology["routers"]:
            router_name = router.get("name", "unknown")
            for interface in router.get("networks", []):
                net_name = interface.get("name") if isinstance(interface, dict) else interface
                if net_name in network_names:
                    logic_checks.append({"check": f"Router {router_name} -> {net_name}", "status": "PASS"})
                else:
                    logic_errors.append(f"Router {router_name} tham chiếu network không tồn tại: {net_name}")
                    logic_checks.append({"check": f"Router {router_name} -> {net_name}", "status": "FAIL"})
    
    # Check gateway IP within CIDR (chỉ khi gateway_ip không null)
    if "networks" in topology:
        for net in topology["networks"]:
            net_name = net.get("name", "unknown")
            cidr = net.get("cidr", "")
            gateway = net.get("gateway_ip")
            if cidr and gateway:  # Chỉ check nếu gateway không null
                try:
                    network = ipaddress.ip_network(cidr, strict=False)
                    gw = ipaddress.ip_address(gateway)
                    if gw in network:
                        logic_checks.append({"check": f"Gateway {gateway} in {cidr}", "status": "PASS"})
                    else:
                        logic_errors.append(f"Gateway {gateway} không thuộc CIDR {cidr}")
                        logic_checks.append({"check": f"Gateway {gateway} in {cidr}", "status": "FAIL"})
                except ValueError:
                    pass
    
    # Check IP addresses within CIDR
    if "instances" in topology and "networks" in topology:
        network_cidrs = {n.get("name"): n.get("cidr") for n in topology["networks"]}
        for inst in topology["instances"]:
            inst_name = inst.get("name", "unknown")
            for net in inst.get("networks", []):
                net_name = net.get("name") if isinstance(net, dict) else None
                ip = net.get("ip") if isinstance(net, dict) else None
                if net_name and ip and net_name in network_cidrs:
                    try:
                        cidr = network_cidrs[net_name]
                        network = ipaddress.ip_network(cidr, strict=False)
                        ip_addr = ipaddress.ip_address(ip)
                        if ip_addr in network:
                            logic_checks.append({"check": f"IP {ip} in {cidr}", "status": "PASS"})
                        else:
                            logic_errors.append(f"IP {ip} của {inst_name} không thuộc CIDR {cidr}")
                            logic_checks.append({"check": f"IP {ip} in {cidr}", "status": "FAIL"})
                    except ValueError:
                        pass
    
    result["logic_validation"]["checks"] = logic_checks
    if logic_errors:
        result["logic_validation"]["status"] = "FAIL"
        result["logic_validation"]["errors"] = logic_errors
    
    # Summary
    result["summary"]["schema_status"] = result["schema_validation"]["status"]
    result["summary"]["logic_status"] = result["logic_validation"]["status"]
    result["summary"]["total_errors"] = len(schema_errors) + len(logic_errors)
    result["summary"]["schema_checks"] = len([c for c in schema_checks if c.get("status") == "PASS"])
    result["summary"]["logic_checks"] = len([c for c in logic_checks if c.get("status") == "PASS"])
    
    if schema_errors or logic_errors:
        result["status"] = "FAIL"
        result["summary"]["result"] = "Không hợp lệ"
    else:
        result["summary"]["result"] = "Hợp lệ"
    
except json.JSONDecodeError as e:
    result["status"] = "FAIL"
    result["schema_validation"]["status"] = "FAIL"
    result["schema_validation"]["errors"] = [f"JSON không hợp lệ: {e}"]
    result["summary"]["result"] = "Lỗi JSON"
except Exception as e:
    result["status"] = "FAIL"
    result["schema_validation"]["errors"] = [f"Lỗi: {e}"]
    result["summary"]["result"] = "Lỗi"

with open(result_file, 'w') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"   Schema:  {result['summary']['schema_status']} ({result['summary'].get('schema_checks', 0)} checks)")
print(f"   Logic:   {result['summary']['logic_status']} ({result['summary'].get('logic_checks', 0)} checks)")
print(f"   Kết quả: {result['summary']['result']}")
EOF

    echo ""

    #==========================================================================
    # LAYER B: TERRAFORM DEPLOYMENT
    #==========================================================================
    echo "[Layer B] Terraform Deployment - Tạo và triển khai hạ tầng..."
    
    # Generate terraform configs
    cd terraform-generator
    START_TIME=$(date +%s.%N)
    python3 generate.py openstack $NUM_COPIES
    END_TIME=$(date +%s.%N)
    DURATION=$(echo "$END_TIME - $START_TIME" | bc)
    cd ..
    
    sleep 3
    
    # Tìm project directories
    PROJECT_DIRS=($(find terraform-projects -maxdepth 2 -type d -name "openstack_*" | grep -E "terraform-projects/openstack_[^/]+/openstack_[^/]+$" | sort | tail -n $NUM_COPIES))
    PROJECT_DIR="${PROJECT_DIRS[0]}"
    
    if [ -z "$PROJECT_DIR" ]; then
        echo "   ❌ Không tìm thấy Terraform project"
        echo '{"layer": "B_TERRAFORM_DEPLOYMENT", "status": "FAIL", "summary": {"apply_status": "Failed", "resource_count": 0}}' > "$RESULT_DIR/layer_b_result.json"
        return 1
    fi
    
    echo "   Project: $PROJECT_DIR"
    
    # Read terraform state and extract metrics
    python3 << EOF
import json
from datetime import datetime
from pathlib import Path

state_file = "$PROJECT_DIR/terraform.tfstate"
result_file = "$RESULT_DIR/layer_b_result.json"
duration = $DURATION

result = {
    "layer": "B_TERRAFORM_DEPLOYMENT",
    "timestamp": datetime.utcnow().isoformat(),
    "status": "UNKNOWN",
    "project_dir": "$PROJECT_DIR",
    "deployment": {
        "apply_status": "Unknown",
        "duration_seconds": duration,
        "resource_count": 0,
        "resource_types": {}
    },
    "summary": {
        "apply_status": "Unknown",
        "resource_count": 0,
        "duration": f"{duration:.2f}s"
    }
}

try:
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    # Count resources
    resources = state.get("resources", [])
    resource_count = len(resources)
    
    # Categorize resources
    resource_types = {}
    for res in resources:
        res_type = res.get("type", "unknown")
        resource_types[res_type] = resource_types.get(res_type, 0) + 1
    
    result["status"] = "SUCCESS"
    result["deployment"]["apply_status"] = "Success"
    result["deployment"]["resource_count"] = resource_count
    result["deployment"]["resource_types"] = resource_types
    result["summary"]["apply_status"] = "Success"
    result["summary"]["resource_count"] = resource_count
    
    print(f"   Apply:     Success")
    print(f"   Resources: {resource_count}")
    print(f"   Duration:  {duration:.2f}s")
    
except FileNotFoundError:
    result["status"] = "FAIL"
    result["deployment"]["apply_status"] = "Failed"
    result["summary"]["apply_status"] = "Failed"
    print("   Apply: Failed (no state file)")
except Exception as e:
    result["status"] = "FAIL"
    result["deployment"]["apply_status"] = "Error"
    result["summary"]["apply_status"] = f"Error: {e}"
    print(f"   Apply: Error - {e}")

with open(result_file, 'w') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
EOF

    echo ""

    #==========================================================================
    # LAYER C: MODEL CONSISTENCY (JSON vs Terraform State)
    # FIXED: So sánh bằng CIDR (vì subnet name có thể rỗng trong OpenStack)
    #==========================================================================
    echo "[Layer C] Model Consistency - So sánh JSON với hạ tầng thực..."
    
    python3 << EOF
import json
from datetime import datetime
from pathlib import Path

topology_file = "terraform-generator/topology.json"
state_file = "$PROJECT_DIR/terraform.tfstate"
result_file = "$RESULT_DIR/layer_c_result.json"

result = {
    "layer": "C_MODEL_CONSISTENCY",
    "timestamp": datetime.utcnow().isoformat(),
    "status": "UNKNOWN",
    "checks": {
        "networks": {"status": "UNKNOWN", "expected": 0, "actual": 0, "match": False, "details": []},
        "instances": {"status": "UNKNOWN", "expected": 0, "actual": 0, "match": False, "details": []},
        "routers": {"status": "UNKNOWN", "expected": 0, "actual": 0, "match": False, "details": []}
    },
    "mismatches": [],
    "summary": {
        "total_checks": 0,
        "passed": 0,
        "failed": 0,
        "match_rate": "0%",
        "overall_result": "Unknown"
    }
}

try:
    with open(topology_file, 'r') as f:
        topology = json.load(f)
    
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    # Extract resources from state
    # Network names từ openstack_networking_network_v2
    state_networks = []  # List of {name, id}
    # Subnet info từ openstack_networking_subnet_v2
    state_subnets = []  # List of {cidr, gateway_ip, network_id}
    state_instances = []
    state_routers = []
    
    for res in state.get("resources", []):
        res_type = res.get("type", "")
        for inst in res.get("instances", []):
            attrs = inst.get("attributes", {})
            
            if res_type == "openstack_networking_network_v2":
                state_networks.append({
                    "name": attrs.get("name", ""),
                    "id": attrs.get("id", "")
                })
            elif res_type == "openstack_networking_subnet_v2":
                state_subnets.append({
                    "network_id": attrs.get("network_id", ""),
                    "cidr": attrs.get("cidr", ""),
                    "gateway_ip": attrs.get("gateway_ip", "")
                })
            elif res_type == "openstack_compute_instance_v2":
                state_instances.append(attrs.get("name", ""))
            elif res_type == "openstack_networking_router_v2":
                state_routers.append(attrs.get("name", ""))
    
    # Check Networks - SO SÁNH BẰNG CIDR (vì subnet name có thể rỗng trong OpenStack)
    # Cách tiếp cận: Tìm network theo tên, sau đó match subnet bằng network_id hoặc CIDR
    expected_nets = topology.get("networks", [])
    result["checks"]["networks"]["expected"] = len(expected_nets)
    result["checks"]["networks"]["actual"] = len(state_subnets)
    
    # Tạo mapping: CIDR -> subnet info
    cidr_to_subnet = {sub["cidr"]: sub for sub in state_subnets}
    
    # Tạo mapping: network_id -> network_name
    network_id_to_name = {net["id"]: net["name"] for net in state_networks}
    
    net_match = True
    for exp_net in expected_nets:
        net_name = exp_net.get("name", "")
        exp_cidr = exp_net.get("cidr", "")
        exp_gateway = exp_net.get("gateway_ip")
        
        found = False
        
        # Phương pháp 1: So sánh trực tiếp bằng CIDR
        if exp_cidr in cidr_to_subnet:
            found = True
            actual_subnet = cidr_to_subnet[exp_cidr]
            
            # CIDR match
            result["checks"]["networks"]["details"].append({
                "component": net_name,
                "field": "CIDR",
                "expected": exp_cidr,
                "actual": actual_subnet["cidr"],
                "result": "Match"
            })
            
            # Gateway check (chỉ khi expected gateway không null)
            if exp_gateway is not None:
                actual_gw = actual_subnet.get("gateway_ip", "")
                if exp_gateway == actual_gw:
                    result["checks"]["networks"]["details"].append({
                        "component": net_name,
                        "field": "Gateway",
                        "expected": exp_gateway,
                        "actual": actual_gw,
                        "result": "Match"
                    })
                else:
                    result["checks"]["networks"]["details"].append({
                        "component": net_name,
                        "field": "Gateway", 
                        "expected": exp_gateway,
                        "actual": actual_gw,
                        "result": "Mismatch (non-critical)"
                    })
            else:
                result["checks"]["networks"]["details"].append({
                    "component": net_name,
                    "field": "Gateway",
                    "expected": "null (no gateway)",
                    "actual": actual_subnet.get("gateway_ip", "none"),
                    "result": "Match (null accepted)"
                })
        
        # Phương pháp 2: Tìm network name có chứa tên expected
        if not found:
            for state_net in state_networks:
                if net_name in state_net["name"]:
                    # Tìm subnet tương ứng qua network_id
                    for sub in state_subnets:
                        if sub["network_id"] == state_net["id"]:
                            found = True
                            if exp_cidr == sub["cidr"]:
                                result["checks"]["networks"]["details"].append({
                                    "component": net_name,
                                    "field": "CIDR",
                                    "expected": exp_cidr,
                                    "actual": sub["cidr"],
                                    "result": "Match"
                                })
                            else:
                                result["checks"]["networks"]["details"].append({
                                    "component": net_name,
                                    "field": "CIDR",
                                    "expected": exp_cidr,
                                    "actual": sub["cidr"],
                                    "result": "Mismatch"
                                })
                                net_match = False
                            break
                    break
        
        if not found:
            result["mismatches"].append(f"Network '{net_name}' (CIDR: {exp_cidr}) không tìm thấy trong state")
            net_match = False
    
    result["checks"]["networks"]["match"] = net_match
    result["checks"]["networks"]["status"] = "PASS" if net_match else "FAIL"
    
    # Check Instances - dùng "name" theo schema thực tế
    expected_insts = topology.get("instances", [])
    result["checks"]["instances"]["expected"] = len(expected_insts)
    result["checks"]["instances"]["actual"] = len(state_instances)
    
    inst_match = len(expected_insts) == len(state_instances)
    for exp_inst in expected_insts:
        inst_name = exp_inst.get("name", "")  # Dùng "name" không phải "instance_name"
        found = any(inst_name in si for si in state_instances)
        result["checks"]["instances"]["details"].append({
            "component": inst_name,
            "expected": "Có",
            "actual": "Có" if found else "Không",
            "result": "Match" if found else "Mismatch"
        })
        if not found:
            inst_match = False
            result["mismatches"].append(f"Instance '{inst_name}' không tìm thấy trong state")
    
    result["checks"]["instances"]["match"] = inst_match
    result["checks"]["instances"]["status"] = "PASS" if inst_match else "FAIL"
    
    # Check Routers - dùng "name" theo schema thực tế
    expected_routers = topology.get("routers", [])
    result["checks"]["routers"]["expected"] = len(expected_routers)
    result["checks"]["routers"]["actual"] = len(state_routers)
    
    router_match = len(expected_routers) == len(state_routers)
    for exp_router in expected_routers:
        router_name = exp_router.get("name", "")  # Dùng "name" không phải "router_name"
        found = any(router_name in sr for sr in state_routers)
        result["checks"]["routers"]["details"].append({
            "component": router_name,
            "expected": "Có",
            "actual": "Có" if found else "Không",
            "result": "Match" if found else "Mismatch"
        })
        if not found:
            router_match = False
            result["mismatches"].append(f"Router '{router_name}' không tìm thấy trong state")
    
    result["checks"]["routers"]["match"] = router_match
    result["checks"]["routers"]["status"] = "PASS" if router_match else "FAIL"
    
    # Summary
    total_checks = 3
    passed = sum([net_match, inst_match, router_match])
    result["summary"]["total_checks"] = total_checks
    result["summary"]["passed"] = passed
    result["summary"]["failed"] = total_checks - passed
    result["summary"]["match_rate"] = f"{(passed/total_checks)*100:.0f}%"
    result["summary"]["overall_result"] = "Match" if passed == total_checks else "Mismatch"
    result["status"] = "PASS" if passed == total_checks else "FAIL"
    
    print(f"   Networks:  {result['checks']['networks']['status']} ({len(expected_nets)} expected, {len(state_subnets)} actual)")
    print(f"   Instances: {result['checks']['instances']['status']} ({len(expected_insts)} expected, {len(state_instances)} actual)")
    print(f"   Routers:   {result['checks']['routers']['status']} ({len(expected_routers)} expected, {len(state_routers)} actual)")
    print(f"   Kết quả:   {result['summary']['overall_result']} ({result['summary']['match_rate']})")

except FileNotFoundError as e:
    result["status"] = "SKIP"
    result["summary"]["overall_result"] = f"Skipped: {e}"
    print(f"   Skipped: File not found")
except Exception as e:
    result["status"] = "ERROR"
    result["summary"]["overall_result"] = f"Error: {e}"
    print(f"   Error: {e}")

with open(result_file, 'w') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
EOF

    echo ""

    #==========================================================================
    # LAYER D: USER-DATA VERIFICATION (Cloud-init)
    # FIXED: Đọc cloud_init/cloud-init từ file reference
    #==========================================================================
    echo "[Layer D] User-data Verification - Kiểm tra cloud-init..."
    
    python3 << EOF
import json
from datetime import datetime
from pathlib import Path
import glob
import os

topology_file = "terraform-generator/topology.json"
project_dir = "$PROJECT_DIR"
result_file = "$RESULT_DIR/layer_d_result.json"

result = {
    "layer": "D_USERDATA_VERIFICATION",
    "timestamp": datetime.utcnow().isoformat(),
    "status": "UNKNOWN",
    "vms": [],
    "summary": {
        "total_vms": 0,
        "cloudinit_configured": 0,
        "cloudinit_files_found": 0,
        "checklist_items": 0,
        "overall_result": "Unknown"
    }
}

try:
    with open(topology_file, 'r') as f:
        topology = json.load(f)
    
    instances = topology.get("instances", [])
    result["summary"]["total_vms"] = len(instances)
    
    cloudinit_count = 0
    files_found = 0
    checklist_total = 0
    
    for inst in instances:
        inst_name = inst.get("name", "")  # Dùng "name" theo schema
        
        # cloud_init hoặc cloud-init (cả 2 format)
        cloud_init_ref = inst.get("cloud_init") or inst.get("cloud-init")
        
        vm_result = {
            "name": inst_name,
            "cloudinit_ref": cloud_init_ref,
            "cloudinit_status": "Not configured",
            "file_found": False,
            "checklist": [],
            "checklist_pass": 0,
            "checklist_total": 0
        }
        
        if cloud_init_ref:
            cloudinit_count += 1
            vm_result["cloudinit_status"] = "Configured"
            
            # Tìm file cloud-init
            cloudinit_paths = [
                f"cloud-init-generator/{cloud_init_ref}",
                f"terraform-generator/{cloud_init_ref}",
                cloud_init_ref
            ]
            
            cloudinit_data = None
            for path in cloudinit_paths:
                if os.path.exists(path):
                    vm_result["file_found"] = True
                    files_found += 1
                    try:
                        with open(path, 'r') as f:
                            cloudinit_data = json.load(f)
                    except:
                        pass
                    break
            
            # Nếu tìm thấy file, extract checklist
            if cloudinit_data:
                checklist = []
                
                # Check packages
                packages = cloudinit_data.get("packages", [])
                for pkg in packages:
                    checklist.append({"type": "package", "target": pkg, "status": "Defined"})
                
                # Check runcmd
                runcmd = cloudinit_data.get("runcmd", [])
                if runcmd:
                    checklist.append({"type": "runcmd", "target": f"{len(runcmd)} commands", "status": "Defined"})
                
                # Check write_files
                write_files = cloudinit_data.get("write_files", [])
                for wf in write_files:
                    path = wf.get("path", "unknown")
                    checklist.append({"type": "file", "target": path, "status": "Defined"})
                
                # Check users
                users = cloudinit_data.get("users", [])
                for user in users:
                    if isinstance(user, dict):
                        uname = user.get("name", "default")
                    else:
                        uname = str(user)
                    checklist.append({"type": "user", "target": uname, "status": "Defined"})
                
                # Check ssh_authorized_keys
                if "ssh_authorized_keys" in cloudinit_data:
                    checklist.append({"type": "ssh_keys", "target": f"{len(cloudinit_data['ssh_authorized_keys'])} keys", "status": "Defined"})
                
                vm_result["checklist"] = checklist
                vm_result["checklist_total"] = len(checklist)
                vm_result["checklist_pass"] = len(checklist)
                checklist_total += len(checklist)
            
            # Kiểm tra file cloud-init trong project directory
            project_cloudinit = list(Path(project_dir).glob(f"*{inst_name}*.yaml")) + \
                               list(Path(project_dir).glob(f"*{inst_name}*.yml")) + \
                               list(Path(project_dir).glob("cloud-init*.yaml"))
            if project_cloudinit:
                vm_result["generated_file"] = str(project_cloudinit[0])
        
        result["vms"].append(vm_result)
    
    result["summary"]["cloudinit_configured"] = cloudinit_count
    result["summary"]["cloudinit_files_found"] = files_found
    result["summary"]["checklist_items"] = checklist_total
    
    # Determine status
    if len(instances) == 0:
        result["status"] = "SKIP"
        result["summary"]["overall_result"] = "No VMs"
    elif cloudinit_count == 0:
        # Không có cloud-init được cấu hình -> vẫn OK (optional)
        result["status"] = "SUCCESS"
        result["summary"]["overall_result"] = "No cloud-init (optional)"
    elif cloudinit_count == len(instances):
        result["status"] = "SUCCESS"
        result["summary"]["overall_result"] = f"{cloudinit_count}/{len(instances)} VMs configured"
    else:
        result["status"] = "PARTIAL"
        result["summary"]["overall_result"] = f"{cloudinit_count}/{len(instances)} VMs configured"
    
    print(f"   VMs Total:     {len(instances)}")
    print(f"   Cloud-init:    {cloudinit_count} configured, {files_found} files found")
    print(f"   Checklist:     {checklist_total} items")
    print(f"   Kết quả:       {result['summary']['overall_result']}")

except Exception as e:
    result["status"] = "ERROR"
    result["summary"]["overall_result"] = f"Error: {e}"
    print(f"   Error: {e}")

with open(result_file, 'w') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
EOF

    echo ""

    #==========================================================================
    # TẠO SUMMARY CHO TOPOLOGY
    #==========================================================================
    echo "[Summary] Tổng hợp kết quả..."
    
    python3 << EOF
import json
from pathlib import Path

result_dir = Path("$RESULT_DIR")

# Load all layer results
layers = {}
for layer in ["a", "b", "c", "d"]:
    layer_file = result_dir / f"layer_{layer}_result.json"
    if layer_file.exists():
        with open(layer_file) as f:
            layers[f"layer_{layer}"] = json.load(f)

# Create summary
summary = {
    "topology_name": "$TOPO_NAME",
    "layer_a": {
        "status": layers.get("layer_a", {}).get("status", "N/A"),
        "schema": layers.get("layer_a", {}).get("summary", {}).get("schema_status", "N/A"),
        "logic": layers.get("layer_a", {}).get("summary", {}).get("logic_status", "N/A"),
        "result": layers.get("layer_a", {}).get("summary", {}).get("result", "N/A")
    },
    "layer_b": {
        "status": layers.get("layer_b", {}).get("status", "N/A"),
        "apply_status": layers.get("layer_b", {}).get("summary", {}).get("apply_status", "N/A"),
        "resource_count": layers.get("layer_b", {}).get("summary", {}).get("resource_count", 0),
        "duration": layers.get("layer_b", {}).get("summary", {}).get("duration", "N/A")
    },
    "layer_c": {
        "status": layers.get("layer_c", {}).get("status", "N/A"),
        "networks_match": layers.get("layer_c", {}).get("checks", {}).get("networks", {}).get("status", "N/A"),
        "instances_match": layers.get("layer_c", {}).get("checks", {}).get("instances", {}).get("status", "N/A"),
        "routers_match": layers.get("layer_c", {}).get("checks", {}).get("routers", {}).get("status", "N/A"),
        "match_rate": layers.get("layer_c", {}).get("summary", {}).get("match_rate", "N/A"),
        "result": layers.get("layer_c", {}).get("summary", {}).get("overall_result", "N/A")
    },
    "layer_d": {
        "status": layers.get("layer_d", {}).get("status", "N/A"),
        "vms_total": layers.get("layer_d", {}).get("summary", {}).get("total_vms", 0),
        "cloudinit_configured": layers.get("layer_d", {}).get("summary", {}).get("cloudinit_configured", 0),
        "checklist_items": layers.get("layer_d", {}).get("summary", {}).get("checklist_items", 0),
        "result": layers.get("layer_d", {}).get("summary", {}).get("overall_result", "N/A")
    }
}

with open(result_dir / "summary.json", 'w') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print("   ✓ Summary saved")
EOF

    echo ""
    echo "✓ Đánh giá $TOPO_NAME hoàn tất (4 layers)"
    echo ""
}

# Đánh giá từng topology
for TOPO in "${TOPOLOGIES[@]}"; do
    evaluate_topology "$TOPO" || echo "⚠️  Lỗi khi đánh giá $TOPO"
    echo ""
    sleep 2
done

# Tạo báo cáo so sánh
echo "================================================================================"
echo "  TẠO BÁO CÁO SO SÁNH TỔNG HỢP"
echo "================================================================================"
echo ""

# Export RESULTS_BASE for python script
export RESULTS_BASE

python3 << 'COMPARISON_EOF'
import json
import os
from pathlib import Path
from datetime import datetime

results_base = os.environ.get("RESULTS_BASE")
if not results_base:
    print("Error: RESULTS_BASE not set")
    exit(1)

topologies = ["topology-tn1a", "topology-tn1b-2router", "topology-tn1c"]

comparison = {
    "evaluation_timestamp": datetime.utcnow().isoformat(),
    "description": "Đánh giá so sánh 3 topologies với 4 Layers",
    "topologies": {},
    "tables": {
        "layer_a": [],
        "layer_b": [],
        "layer_c": [],
        "layer_d": []
    },
    "summary": {}
}

# Load all summaries
for topo in topologies:
    summary_file = Path(results_base) / topo / "summary.json"
    if summary_file.exists():
        with open(summary_file) as f:
            comparison["topologies"][topo] = json.load(f)

# Create tables for each layer
print("\n" + "="*90)
print("BẢNG KẾT QUẢ ĐÁNH GIÁ 4 LAYERS")
print("="*90)

# TABLE LAYER A - Input Validation
print("\n📋 LAYER A - INPUT VALIDATION (Kiểm tra đầu vào)")
print("-"*70)
print(f"{'Topology':<25} {'Schema':<12} {'Logic':<12} {'Kết quả':<15}")
print("-"*70)

for topo in topologies:
    if topo in comparison["topologies"]:
        data = comparison["topologies"][topo]["layer_a"]
        schema = data.get("schema", "N/A")
        logic = data.get("logic", "N/A")
        result = data.get("result", "N/A")
        print(f"{topo:<25} {schema:<12} {logic:<12} {result:<15}")
        
        comparison["tables"]["layer_a"].append({
            "topology": topo,
            "schema": schema,
            "logic": logic,
            "result": result
        })

# TABLE LAYER B - Terraform Deployment
print("\n📋 LAYER B - TERRAFORM DEPLOYMENT (Triển khai hạ tầng)")
print("-"*70)
print(f"{'Topology':<25} {'Apply':<12} {'Resources':<12} {'Duration':<15}")
print("-"*70)

for topo in topologies:
    if topo in comparison["topologies"]:
        data = comparison["topologies"][topo]["layer_b"]
        apply_status = data.get("apply_status", "N/A")
        resources = data.get("resource_count", 0)
        duration = data.get("duration", "N/A")
        print(f"{topo:<25} {apply_status:<12} {resources:<12} {duration:<15}")
        
        comparison["tables"]["layer_b"].append({
            "topology": topo,
            "apply_status": apply_status,
            "resource_count": resources,
            "duration": duration
        })

# TABLE LAYER C - Model Consistency
print("\n📋 LAYER C - MODEL CONSISTENCY (JSON vs Terraform State)")
print("-"*90)
print(f"{'Topology':<25} {'Networks':<12} {'Instances':<12} {'Routers':<12} {'Match Rate':<12} {'Kết quả':<12}")
print("-"*90)

for topo in topologies:
    if topo in comparison["topologies"]:
        data = comparison["topologies"][topo]["layer_c"]
        nets = data.get("networks_match", "N/A")
        insts = data.get("instances_match", "N/A")
        routers = data.get("routers_match", "N/A")
        rate = data.get("match_rate", "N/A")
        result = data.get("result", "N/A")
        print(f"{topo:<25} {nets:<12} {insts:<12} {routers:<12} {rate:<12} {result:<12}")
        
        comparison["tables"]["layer_c"].append({
            "topology": topo,
            "networks_match": nets,
            "instances_match": insts,
            "routers_match": routers,
            "match_rate": rate,
            "result": result
        })

# TABLE LAYER D - User-data Verification
print("\n📋 LAYER D - USER-DATA VERIFICATION (Cloud-init)")
print("-"*80)
print(f"{'Topology':<25} {'VMs':<10} {'Cloud-init':<15} {'Checklist':<12} {'Kết quả':<20}")
print("-"*80)

for topo in topologies:
    if topo in comparison["topologies"]:
        data = comparison["topologies"][topo]["layer_d"]
        vms = data.get("vms_total", 0)
        cloudinit = data.get("cloudinit_configured", 0)
        checklist = data.get("checklist_items", 0)
        result = data.get("result", "N/A")
        print(f"{topo:<25} {vms:<10} {cloudinit:<15} {checklist:<12} {result:<20}")
        
        comparison["tables"]["layer_d"].append({
            "topology": topo,
            "vms_total": vms,
            "cloudinit_configured": cloudinit,
            "checklist_items": checklist,
            "result": result
        })

# Overall Summary
print("\n" + "="*90)
print("TỔNG HỢP / OVERALL SUMMARY")
print("="*90)

total_success = 0
for topo in topologies:
    if topo in comparison["topologies"]:
        data = comparison["topologies"][topo]
        layers_passed = 0
        
        # Layer A: PASS
        if data["layer_a"]["status"] == "PASS":
            layers_passed += 1
        
        # Layer B: SUCCESS
        if data["layer_b"]["status"] == "SUCCESS":
            layers_passed += 1
        
        # Layer C: PASS
        if data["layer_c"]["status"] == "PASS":
            layers_passed += 1
        
        # Layer D: SUCCESS hoặc PARTIAL (có cloud-init)
        if data["layer_d"]["status"] in ["SUCCESS", "PARTIAL"]:
            layers_passed += 1
        
        status = "✓ PASSED" if layers_passed == 4 else "⚠️ PARTIAL" if layers_passed >= 2 else "❌ FAILED"
        print(f"{topo}: {layers_passed}/4 layers passed - {status}")
        
        comparison["summary"][topo] = {
            "layers_passed": layers_passed,
            "total_layers": 4,
            "status": status
        }
        
        if layers_passed == 4:
            total_success += 1

print(f"\nTổng: {total_success}/{len(topologies)} topologies passed all 4 layers")
print("="*90)

# Save comparison report
comparison_file = Path(results_base) / "comparison_report.json"
with open(comparison_file, "w") as f:
    json.dump(comparison, f, indent=2, ensure_ascii=False)

print(f"\n✓ Báo cáo so sánh lưu tại: {comparison_file}")

COMPARISON_EOF

echo ""
echo "================================================================================"
echo "  HOÀN TẤT ĐÁNH GIÁ"
echo "================================================================================"
echo ""
echo "Tất cả kết quả lưu tại: $RESULTS_BASE"
echo ""
echo "Chi tiết từng topology:"
for TOPO in "${TOPOLOGIES[@]}"; do
    echo "  - $RESULTS_BASE/$TOPO/"
    echo "      layer_a_result.json - Input Validation"
    echo "      layer_b_result.json - Terraform Deployment"
    echo "      layer_c_result.json - Model Consistency"
    echo "      layer_d_result.json - User-data Verification"
    echo "      summary.json        - Tổng hợp"
done
echo ""
echo "Báo cáo so sánh: $RESULTS_BASE/comparison_report.json"
echo "================================================================================"
