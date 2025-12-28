#!/usr/bin/env python3
"""
Layer A: Input Validation Evaluator
Validates topology.json and cloud-init user-data files
Output: JSON with validation results
"""

import json
import sys
import os
import ipaddress
from pathlib import Path
from datetime import datetime
import subprocess

class LayerAValidator:
    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.results = {
            "layer": "A_INPUT_VALIDATION",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "UNKNOWN",
            "validations": {},
            "errors": [],
            "warnings": [],
            "summary": {}
        }
    
    def validate_topology_schema(self, topology_file):
        """Validate topology.json against schema"""
        validation = {
            "test": "topology_schema_validation",
            "status": "PASS",
            "errors": []
        }
        
        try:
            with open(topology_file, 'r') as f:
                topology = json.load(f)
            
            # Check required top-level keys
            required_keys = ["cloud_provider", "topology_name", "networks", "instances"]
            for key in required_keys:
                if key not in topology:
                    validation["errors"].append(f"Missing required key: {key}")
                    validation["status"] = "FAIL"
            
            if "networks" in topology:
                for i, network in enumerate(topology["networks"]):
                    net_errors = self._validate_network(network, i)
                    validation["errors"].extend(net_errors)
            
            if "instances" in topology:
                for i, instance in enumerate(topology["instances"]):
                    inst_errors = self._validate_instance(instance, i)
                    validation["errors"].extend(inst_errors)
            
            if "routers" in topology:
                for i, router in enumerate(topology["routers"]):
                    rtr_errors = self._validate_router(router, i)
                    validation["errors"].extend(rtr_errors)
            
            if validation["errors"]:
                validation["status"] = "FAIL"
                
        except json.JSONDecodeError as e:
            validation["status"] = "FAIL"
            validation["errors"].append(f"Invalid JSON: {str(e)}")
        except FileNotFoundError:
            validation["status"] = "FAIL"
            validation["errors"].append(f"Topology file not found: {topology_file}")
        except Exception as e:
            validation["status"] = "FAIL"
            validation["errors"].append(f"Validation error: {str(e)}")
        
        return validation
    
    def _validate_network(self, network, index):
        """Validate network object"""
        errors = []
        required = ["network_name", "cidr"]
        
        for key in required:
            if key not in network:
                errors.append(f"Network[{index}]: Missing '{key}'")
        
        if "cidr" in network:
            try:
                ipaddress.ip_network(network["cidr"])
            except ValueError as e:
                errors.append(f"Network[{index}]: Invalid CIDR '{network['cidr']}': {e}")
        
        if "gateway_ip" in network:
            try:
                ip = ipaddress.ip_address(network["gateway_ip"])
                if "cidr" in network:
                    net = ipaddress.ip_network(network["cidr"])
                    if ip not in net:
                        errors.append(f"Network[{index}]: Gateway IP {network['gateway_ip']} not in CIDR {network['cidr']}")
            except ValueError as e:
                errors.append(f"Network[{index}]: Invalid gateway IP: {e}")
        
        return errors
    
    def _validate_instance(self, instance, index):
        """Validate instance object"""
        errors = []
        required = ["instance_name", "image", "flavor", "network"]
        
        for key in required:
            if key not in instance:
                errors.append(f"Instance[{index}]: Missing '{key}'")
        
        if "fixed_ip" in instance:
            try:
                ipaddress.ip_address(instance["fixed_ip"])
            except ValueError as e:
                errors.append(f"Instance[{index}]: Invalid fixed_ip: {e}")
        
        return errors
    
    def _validate_router(self, router, index):
        """Validate router object"""
        errors = []
        required = ["router_name"]
        
        for key in required:
            if key not in router:
                errors.append(f"Router[{index}]: Missing '{key}'")
        
        return errors
    
    def validate_network_logic(self, topology_file):
        """Validate network logic (IP conflicts, references)"""
        validation = {
            "test": "network_logic_validation",
            "status": "PASS",
            "errors": []
        }
        
        try:
            with open(topology_file, 'r') as f:
                topology = json.load(f)
            
            # Check for duplicate network names
            if "networks" in topology:
                network_names = [n.get("network_name") for n in topology["networks"]]
                duplicates = [name for name in network_names if network_names.count(name) > 1]
                if duplicates:
                    validation["errors"].append(f"Duplicate network names: {set(duplicates)}")
            
            # Check for IP conflicts
            ip_assignments = {}
            if "instances" in topology:
                for inst in topology["instances"]:
                    if "fixed_ip" in inst:
                        ip = inst["fixed_ip"]
                        if ip in ip_assignments:
                            validation["errors"].append(
                                f"IP conflict: {ip} assigned to both '{ip_assignments[ip]}' and '{inst['instance_name']}'"
                            )
                        ip_assignments[ip] = inst["instance_name"]
            
            # Check network references
            if "networks" in topology and "instances" in topology:
                network_names = {n.get("network_name") for n in topology["networks"]}
                for inst in topology["instances"]:
                    if "network" in inst and inst["network"] not in network_names:
                        validation["errors"].append(
                            f"Instance '{inst['instance_name']}' references non-existent network '{inst['network']}'"
                        )
            
            if validation["errors"]:
                validation["status"] = "FAIL"
                
        except Exception as e:
            validation["status"] = "FAIL"
            validation["errors"].append(f"Logic validation error: {str(e)}")
        
        return validation
    
    def validate_cloudinit(self, cloudinit_file):
        """Validate cloud-init user-data file"""
        validation = {
            "test": "cloudinit_validation",
            "status": "PASS",
            "errors": []
        }
        
        if not os.path.exists(cloudinit_file):
            validation["status"] = "SKIP"
            validation["errors"].append(f"Cloud-init file not found: {cloudinit_file}")
            return validation
        
        try:
            # Try to use cloud-init schema validation if available
            result = subprocess.run(
                ["cloud-init", "schema", "--config-file", cloudinit_file],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                validation["status"] = "FAIL"
                validation["errors"].append(f"Cloud-init schema validation failed: {result.stderr}")
            
        except FileNotFoundError:
            # cloud-init not installed, do basic validation
            try:
                with open(cloudinit_file, 'r') as f:
                    content = f.read()
                    if not content.strip().startswith("#cloud-config"):
                        validation["warnings"] = ["Cloud-init file should start with #cloud-config"]
                    # Try to parse as YAML if pyyaml is available
                    try:
                        import yaml
                        yaml.safe_load(content)
                    except ImportError:
                        pass  # YAML validation skipped
                    except yaml.YAMLError as e:
                        validation["status"] = "FAIL"
                        validation["errors"].append(f"Invalid YAML: {str(e)}")
            except Exception as e:
                validation["status"] = "FAIL"
                validation["errors"].append(f"Cloud-init validation error: {str(e)}")
        except subprocess.TimeoutExpired:
            validation["status"] = "FAIL"
            validation["errors"].append("Cloud-init validation timeout")
        except Exception as e:
            validation["status"] = "FAIL"
            validation["errors"].append(f"Unexpected error: {str(e)}")
        
        return validation
    
    def run(self, topology_file, cloudinit_file=None):
        """Run all Layer A validations"""
        
        # Validate topology schema
        self.results["validations"]["topology_schema"] = self.validate_topology_schema(topology_file)
        
        # Validate network logic
        self.results["validations"]["network_logic"] = self.validate_network_logic(topology_file)
        
        # Validate cloud-init if provided
        if cloudinit_file:
            self.results["validations"]["cloudinit"] = self.validate_cloudinit(cloudinit_file)
        
        # Calculate summary
        all_validations = list(self.results["validations"].values())
        passed = sum(1 for v in all_validations if v["status"] == "PASS")
        failed = sum(1 for v in all_validations if v["status"] == "FAIL")
        skipped = sum(1 for v in all_validations if v["status"] == "SKIP")
        
        self.results["summary"] = {
            "total_tests": len(all_validations),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": f"{(passed / len(all_validations) * 100):.2f}%" if all_validations else "0%"
        }
        
        # Aggregate all errors
        for validation in all_validations:
            self.results["errors"].extend(validation.get("errors", []))
        
        # Set overall status
        if failed > 0:
            self.results["status"] = "FAIL"
        elif passed > 0:
            self.results["status"] = "PASS"
        else:
            self.results["status"] = "SKIP"
        
        return self.results
    
    def save_results(self, output_file):
        """Save results to JSON file"""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"Layer A results saved to: {output_file}")


def main():
    if len(sys.argv) < 3:
        print("Usage: layer_a_validation.py <topology.json> <output.json> [cloudinit_file]")
        sys.exit(1)
    
    topology_file = sys.argv[1]
    output_file = sys.argv[2]
    cloudinit_file = sys.argv[3] if len(sys.argv) > 3 else None
    
    validator = LayerAValidator(os.path.dirname(topology_file))
    results = validator.run(topology_file, cloudinit_file)
    validator.save_results(output_file)
    
    # Print summary to stdout
    print(f"\n=== Layer A: Input Validation ===")
    print(f"Status: {results['status']}")
    print(f"Tests: {results['summary']['total_tests']}")
    print(f"Passed: {results['summary']['passed']}")
    print(f"Failed: {results['summary']['failed']}")
    print(f"Pass Rate: {results['summary']['pass_rate']}")
    
    if results['errors']:
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results['errors'][:10]:  # Show first 10
            print(f"  - {error}")
    
    sys.exit(0 if results['status'] == 'PASS' else 1)


if __name__ == "__main__":
    main()
