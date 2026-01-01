#!/usr/bin/env python3
"""
Layer C: Model Consistency Check
Compares topology.json specification with terraform.tfstate actual resources
Output: JSON with consistency check results
"""

import json
import sys
import os
import ipaddress
from pathlib import Path
from datetime import datetime

class LayerCConsistencyChecker:
    def __init__(self, topology_file, state_file, cloud_provider):
        self.topology_file = Path(topology_file)
        self.state_file = Path(state_file)
        self.cloud_provider = cloud_provider.lower()
        self.results = {
            "layer": "C_MODEL_CONSISTENCY",
            "timestamp": datetime.utcnow().isoformat(),
            "cloud_provider": cloud_provider,
            "topology_file": str(topology_file),
            "state_file": str(state_file),
            "status": "UNKNOWN",
            "checks": {},
            "mismatches": [],
            "errors": [],
            "summary": {}
        }
        self.topology = None
        self.state = None
    
    def load_files(self):
        """Load topology and state files"""
        try:
            with open(self.topology_file, 'r') as f:
                self.topology = json.load(f)
        except Exception as e:
            self.results["errors"].append(f"Failed to load topology file: {str(e)}")
            return False
        
        try:
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
        except Exception as e:
            self.results["errors"].append(f"Failed to load state file: {str(e)}")
            return False
        
        return True
    
    def extract_state_resources(self):
        """Extract resources from terraform state"""
        resources = {
            "networks": [],
            "instances": [],
            "routers": [],
            "subnets": [],
            "other": []
        }
        
        if not self.state or "resources" not in self.state:
            return resources
        
        for resource in self.state["resources"]:
            res_type = resource.get("type", "")
            instances = resource.get("instances", [])
            
            for instance in instances:
                attributes = instance.get("attributes", {})
                
                if self.cloud_provider == "openstack":
                    if res_type == "openstack_networking_network_v2":
                        resources["networks"].append({
                            "name": attributes.get("name"),
                            "id": attributes.get("id"),
                            "admin_state_up": attributes.get("admin_state_up")
                        })
                    elif res_type == "openstack_networking_subnet_v2":
                        resources["subnets"].append({
                            "name": attributes.get("name"),
                            "cidr": attributes.get("cidr"),
                            "gateway_ip": attributes.get("gateway_ip"),
                            "network_id": attributes.get("network_id"),
                            "enable_dhcp": attributes.get("enable_dhcp")
                        })
                    elif res_type == "openstack_compute_instance_v2":
                        resources["instances"].append({
                            "name": attributes.get("name"),
                            "id": attributes.get("id"),
                            "flavor_name": attributes.get("flavor_name"),
                            "image_name": attributes.get("image_name"),
                            "networks": attributes.get("network", [])
                        })
                    elif res_type == "openstack_networking_router_v2":
                        resources["routers"].append({
                            "name": attributes.get("name"),
                            "id": attributes.get("id"),
                            "external_network_id": attributes.get("external_network_id")
                        })
                
                elif self.cloud_provider == "aws":
                    if res_type == "aws_vpc":
                        resources["networks"].append({
                            "name": attributes.get("tags", {}).get("Name"),
                            "id": attributes.get("id"),
                            "cidr": attributes.get("cidr_block")
                        })
                    elif res_type == "aws_subnet":
                        resources["subnets"].append({
                            "name": attributes.get("tags", {}).get("Name"),
                            "cidr": attributes.get("cidr_block"),
                            "vpc_id": attributes.get("vpc_id"),
                            "availability_zone": attributes.get("availability_zone")
                        })
                    elif res_type == "aws_instance":
                        resources["instances"].append({
                            "name": attributes.get("tags", {}).get("Name"),
                            "id": attributes.get("id"),
                            "instance_type": attributes.get("instance_type"),
                            "ami": attributes.get("ami"),
                            "subnet_id": attributes.get("subnet_id"),
                            "private_ip": attributes.get("private_ip")
                        })
                else:
                    resources["other"].append({
                        "type": res_type,
                        "name": attributes.get("name") or attributes.get("tags", {}).get("Name")
                    })
        
        return resources
    
    def check_networks(self, state_resources):
        """Compare networks/VPCs"""
        check = {
            "resource_type": "networks",
            "status": "PASS",
            "expected_count": 0,
            "actual_count": 0,
            "mismatches": []
        }
        
        if "networks" not in self.topology:
            check["status"] = "SKIP"
            return check
        
        expected_networks = self.topology["networks"]
        actual_networks = state_resources["subnets"]  # In terraform, we check subnets which have CIDR
        
        check["expected_count"] = len(expected_networks)
        check["actual_count"] = len(actual_networks)
        
        # Check count match
        if check["expected_count"] != check["actual_count"]:
            mismatch = {
                "type": "count_mismatch",
                "expected": check["expected_count"],
                "actual": check["actual_count"]
            }
            check["mismatches"].append(mismatch)
            check["status"] = "FAIL"
        
        # Check each network
        for expected_net in expected_networks:
            net_name = expected_net.get("network_name")
            expected_cidr = expected_net.get("cidr")
            
            # Find matching network in state
            found = False
            for actual_net in actual_networks:
                if net_name in actual_net.get("name", ""):
                    found = True
                    
                    # Check CIDR
                    if expected_cidr and actual_net.get("cidr"):
                        if expected_cidr != actual_net["cidr"]:
                            mismatch = {
                                "type": "cidr_mismatch",
                                "network": net_name,
                                "expected": expected_cidr,
                                "actual": actual_net["cidr"]
                            }
                            check["mismatches"].append(mismatch)
                            check["status"] = "FAIL"
                    
                    # Check gateway IP
                    if expected_net.get("gateway_ip") and actual_net.get("gateway_ip"):
                        if expected_net["gateway_ip"] != actual_net["gateway_ip"]:
                            mismatch = {
                                "type": "gateway_mismatch",
                                "network": net_name,
                                "expected": expected_net["gateway_ip"],
                                "actual": actual_net["gateway_ip"]
                            }
                            check["mismatches"].append(mismatch)
                            check["status"] = "FAIL"
                    break
            
            if not found:
                mismatch = {
                    "type": "network_not_found",
                    "network": net_name
                }
                check["mismatches"].append(mismatch)
                check["status"] = "FAIL"
        
        return check
    
    def check_instances(self, state_resources):
        """Compare instances"""
        check = {
            "resource_type": "instances",
            "status": "PASS",
            "expected_count": 0,
            "actual_count": 0,
            "mismatches": []
        }
        
        if "instances" not in self.topology:
            check["status"] = "SKIP"
            return check
        
        expected_instances = self.topology["instances"]
        actual_instances = state_resources["instances"]
        
        check["expected_count"] = len(expected_instances)
        check["actual_count"] = len(actual_instances)
        
        # Check count match
        if check["expected_count"] != check["actual_count"]:
            mismatch = {
                "type": "count_mismatch",
                "expected": check["expected_count"],
                "actual": check["actual_count"]
            }
            check["mismatches"].append(mismatch)
            check["status"] = "FAIL"
        
        # Check each instance
        for expected_inst in expected_instances:
            inst_name = expected_inst.get("instance_name")
            expected_image = expected_inst.get("image")
            expected_flavor = expected_inst.get("flavor")
            
            # Find matching instance in state
            found = False
            for actual_inst in actual_instances:
                if inst_name in actual_inst.get("name", ""):
                    found = True
                    
                    # Check flavor/instance_type
                    if expected_flavor:
                        actual_flavor = actual_inst.get("flavor_name") or actual_inst.get("instance_type")
                        if actual_flavor and expected_flavor not in actual_flavor:
                            mismatch = {
                                "type": "flavor_mismatch",
                                "instance": inst_name,
                                "expected": expected_flavor,
                                "actual": actual_flavor
                            }
                            check["mismatches"].append(mismatch)
                            check["status"] = "FAIL"
                    
                    # Check image
                    if expected_image:
                        actual_image = actual_inst.get("image_name") or actual_inst.get("ami")
                        if actual_image and expected_image not in actual_image and actual_image not in expected_image:
                            # Allow partial match for image names
                            mismatch = {
                                "type": "image_mismatch",
                                "instance": inst_name,
                                "expected": expected_image,
                                "actual": actual_image
                            }
                            check["mismatches"].append(mismatch)
                            check["status"] = "FAIL"
                    
                    break
            
            if not found:
                mismatch = {
                    "type": "instance_not_found",
                    "instance": inst_name
                }
                check["mismatches"].append(mismatch)
                check["status"] = "FAIL"
        
        return check
    
    def check_routers(self, state_resources):
        """Compare routers"""
        check = {
            "resource_type": "routers",
            "status": "PASS",
            "expected_count": 0,
            "actual_count": 0,
            "mismatches": []
        }
        
        if "routers" not in self.topology:
            check["status"] = "SKIP"
            return check
        
        expected_routers = self.topology["routers"]
        actual_routers = state_resources["routers"]
        
        check["expected_count"] = len(expected_routers)
        check["actual_count"] = len(actual_routers)
        
        # Check count match
        if check["expected_count"] != check["actual_count"]:
            mismatch = {
                "type": "count_mismatch",
                "expected": check["expected_count"],
                "actual": check["actual_count"]
            }
            check["mismatches"].append(mismatch)
            check["status"] = "FAIL"
        
        # Check each router exists
        for expected_router in expected_routers:
            router_name = expected_router.get("router_name")
            
            found = any(router_name in r.get("name", "") for r in actual_routers)
            
            if not found:
                mismatch = {
                    "type": "router_not_found",
                    "router": router_name
                }
                check["mismatches"].append(mismatch)
                check["status"] = "FAIL"
        
        return check
    
    def run(self):
        """Run all consistency checks"""
        
        if not self.load_files():
            self.results["status"] = "ERROR"
            return self.results
        
        # Extract state resources
        state_resources = self.extract_state_resources()
        
        # Run checks
        self.results["checks"]["networks"] = self.check_networks(state_resources)
        self.results["checks"]["instances"] = self.check_instances(state_resources)
        self.results["checks"]["routers"] = self.check_routers(state_resources)
        
        # Aggregate mismatches
        for check in self.results["checks"].values():
            self.results["mismatches"].extend(check.get("mismatches", []))
        
        # Calculate summary
        all_checks = list(self.results["checks"].values())
        passed = sum(1 for c in all_checks if c["status"] == "PASS")
        failed = sum(1 for c in all_checks if c["status"] == "FAIL")
        skipped = sum(1 for c in all_checks if c["status"] == "SKIP")
        
        self.results["summary"] = {
            "total_checks": len(all_checks),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total_mismatches": len(self.results["mismatches"]),
            "consistency_rate": f"{(passed / (passed + failed) * 100):.2f}%" if (passed + failed) > 0 else "N/A"
        }
        
        # Set overall status
        if failed > 0:
            self.results["status"] = "INCONSISTENT"
        elif passed > 0:
            self.results["status"] = "CONSISTENT"
        else:
            self.results["status"] = "NO_DATA"
        
        return self.results
    
    def save_results(self, output_file):
        """Save results to JSON file"""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"Layer C results saved to: {output_file}")


def main():
    if len(sys.argv) < 5:
        print("Usage: layer_c_consistency.py <topology.json> <terraform.tfstate> <cloud_provider> <output.json>")
        sys.exit(1)
    
    topology_file = sys.argv[1]
    state_file = sys.argv[2]
    cloud_provider = sys.argv[3]
    output_file = sys.argv[4]
    
    checker = LayerCConsistencyChecker(topology_file, state_file, cloud_provider)
    results = checker.run()
    checker.save_results(output_file)
    
    # Print summary
    print(f"\n=== Layer C: Model Consistency Check ===")
    print(f"Cloud Provider: {results['cloud_provider']}")
    print(f"Status: {results['status']}")
    print(f"Checks: {results['summary']['total_checks']}")
    print(f"Passed: {results['summary']['passed']}")
    print(f"Failed: {results['summary']['failed']}")
    print(f"Consistency Rate: {results['summary']['consistency_rate']}")
    print(f"Total Mismatches: {results['summary']['total_mismatches']}")
    
    if results['mismatches']:
        print(f"\nMismatches ({len(results['mismatches'])}):")
        for mismatch in results['mismatches'][:10]:
            print(f"  - {mismatch['type']}: {mismatch}")
    
    sys.exit(0 if results['status'] == 'CONSISTENT' else 1)


if __name__ == "__main__":
    main()
