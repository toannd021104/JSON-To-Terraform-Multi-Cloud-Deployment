#!/usr/bin/env python3
"""
Layer D: User-Data Execution Verification
SSH into VMs and verify user-data execution using checklists
Output: JSON with verification results per VM
"""

import json
import sys
import os
import time
import subprocess
from pathlib import Path
from datetime import datetime
import socket

class LayerDUserdataVerifier:
    def __init__(self, config_file):
        self.config_file = Path(config_file)
        self.config = None
        self.results = {
            "layer": "D_USERDATA_VERIFICATION",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "UNKNOWN",
            "vms": {},
            "errors": [],
            "summary": {}
        }
    
    def load_config(self):
        """Load verification configuration"""
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            return True
        except Exception as e:
            self.results["errors"].append(f"Failed to load config: {str(e)}")
            return False
    
    def check_ssh_connectivity(self, host, port, username, key_file, timeout=10):
        """Check if SSH is accessible"""
        try:
            # First check if port is open
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result != 0:
                return False, "Port not reachable"
            
            # Try SSH connection
            cmd = [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", f"ConnectTimeout={timeout}",
                "-i", key_file,
                f"{username}@{host}",
                "echo SSH_OK"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5
            )
            
            if result.returncode == 0 and "SSH_OK" in result.stdout:
                return True, "SSH accessible"
            else:
                return False, f"SSH failed: {result.stderr[:200]}"
                
        except subprocess.TimeoutExpired:
            return False, "SSH timeout"
        except Exception as e:
            return False, f"SSH error: {str(e)}"
    
    def ssh_execute(self, host, username, key_file, command, timeout=30):
        """Execute command via SSH"""
        try:
            cmd = [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", f"ConnectTimeout=10",
                "-i", key_file,
                f"{username}@{host}",
                command
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "success": result.returncode == 0
            }
            
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "Command timeout",
                "success": False
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }
    
    def verify_package_installed(self, host, username, key_file, package_name):
        """Check if package is installed"""
        check_result = {
            "check_type": "package_installed",
            "target": package_name,
            "status": "UNKNOWN",
            "details": ""
        }
        
        # Try dpkg (Debian/Ubuntu)
        result = self.ssh_execute(host, username, key_file, f"dpkg -l | grep -w {package_name}")
        
        if result["success"] and result["stdout"]:
            check_result["status"] = "PASS"
            check_result["details"] = f"Package {package_name} is installed"
        else:
            # Try rpm (RHEL/CentOS)
            result = self.ssh_execute(host, username, key_file, f"rpm -qa | grep -w {package_name}")
            
            if result["success"] and result["stdout"]:
                check_result["status"] = "PASS"
                check_result["details"] = f"Package {package_name} is installed"
            else:
                check_result["status"] = "FAIL"
                check_result["details"] = f"Package {package_name} not found"
        
        return check_result
    
    def verify_service_running(self, host, username, key_file, service_name):
        """Check if service is running"""
        check_result = {
            "check_type": "service_running",
            "target": service_name,
            "status": "UNKNOWN",
            "details": ""
        }
        
        result = self.ssh_execute(host, username, key_file, f"systemctl is-active {service_name}")
        
        if result["success"] and result["stdout"].strip() == "active":
            check_result["status"] = "PASS"
            check_result["details"] = f"Service {service_name} is active"
        else:
            check_result["status"] = "FAIL"
            check_result["details"] = f"Service {service_name} is not active: {result['stdout']}"
        
        return check_result
    
    def verify_file_exists(self, host, username, key_file, file_path):
        """Check if file exists"""
        check_result = {
            "check_type": "file_exists",
            "target": file_path,
            "status": "UNKNOWN",
            "details": ""
        }
        
        result = self.ssh_execute(host, username, key_file, f"test -f {file_path} && echo EXISTS || echo MISSING")
        
        if result["success"] and "EXISTS" in result["stdout"]:
            check_result["status"] = "PASS"
            check_result["details"] = f"File {file_path} exists"
        else:
            check_result["status"] = "FAIL"
            check_result["details"] = f"File {file_path} does not exist"
        
        return check_result
    
    def verify_directory_exists(self, host, username, key_file, dir_path):
        """Check if directory exists"""
        check_result = {
            "check_type": "directory_exists",
            "target": dir_path,
            "status": "UNKNOWN",
            "details": ""
        }
        
        result = self.ssh_execute(host, username, key_file, f"test -d {dir_path} && echo EXISTS || echo MISSING")
        
        if result["success"] and "EXISTS" in result["stdout"]:
            check_result["status"] = "PASS"
            check_result["details"] = f"Directory {dir_path} exists"
        else:
            check_result["status"] = "FAIL"
            check_result["details"] = f"Directory {dir_path} does not exist"
        
        return check_result
    
    def verify_user_exists(self, host, username, key_file, target_user):
        """Check if user exists"""
        check_result = {
            "check_type": "user_exists",
            "target": target_user,
            "status": "UNKNOWN",
            "details": ""
        }
        
        result = self.ssh_execute(host, username, key_file, f"id {target_user}")
        
        if result["success"]:
            check_result["status"] = "PASS"
            check_result["details"] = f"User {target_user} exists"
        else:
            check_result["status"] = "FAIL"
            check_result["details"] = f"User {target_user} does not exist"
        
        return check_result
    
    def verify_command_output(self, host, username, key_file, command, expected_output):
        """Check if command produces expected output"""
        check_result = {
            "check_type": "command_output",
            "target": command,
            "status": "UNKNOWN",
            "details": ""
        }
        
        result = self.ssh_execute(host, username, key_file, command)
        
        if result["success"] and expected_output in result["stdout"]:
            check_result["status"] = "PASS"
            check_result["details"] = f"Command output contains: {expected_output}"
        else:
            check_result["status"] = "FAIL"
            check_result["details"] = f"Expected '{expected_output}', got '{result['stdout'][:100]}'"
        
        return check_result
    
    def verify_network_connectivity(self, host, username, key_file, target):
        """Check network connectivity to target"""
        check_result = {
            "check_type": "network_connectivity",
            "target": target,
            "status": "UNKNOWN",
            "details": ""
        }
        
        result = self.ssh_execute(host, username, key_file, f"ping -c 3 -W 2 {target}")
        
        if result["success"]:
            check_result["status"] = "PASS"
            check_result["details"] = f"Can reach {target}"
        else:
            check_result["status"] = "FAIL"
            check_result["details"] = f"Cannot reach {target}"
        
        return check_result
    
    def run_checklist(self, vm_config):
        """Run checklist for a single VM"""
        vm_result = {
            "vm_name": vm_config["name"],
            "host": vm_config["host"],
            "status": "UNKNOWN",
            "ssh_accessible": False,
            "checks": [],
            "errors": []
        }
        
        username = vm_config.get("username", "ubuntu")
        key_file = vm_config.get("ssh_key", "~/.ssh/id_rsa")
        key_file = os.path.expanduser(key_file)
        
        # Check SSH connectivity first
        print(f"  Checking SSH connectivity to {vm_config['host']}...")
        ssh_ok, ssh_msg = self.check_ssh_connectivity(
            vm_config["host"],
            vm_config.get("port", 22),
            username,
            key_file,
            timeout=vm_config.get("ssh_timeout", 10)
        )
        
        vm_result["ssh_accessible"] = ssh_ok
        
        if not ssh_ok:
            vm_result["status"] = "SSH_FAILED"
            vm_result["errors"].append(ssh_msg)
            return vm_result
        
        # Wait for cloud-init to complete
        wait_time = vm_config.get("cloud_init_wait", 0)
        if wait_time > 0:
            print(f"  Waiting {wait_time}s for cloud-init to complete...")
            time.sleep(wait_time)
        
        # Run checks
        checklist = vm_config.get("checklist", [])
        
        for check in checklist:
            check_type = check.get("type")
            
            print(f"    Running check: {check_type} - {check.get('target', '')}")
            
            if check_type == "package_installed":
                result = self.verify_package_installed(vm_config["host"], username, key_file, check["target"])
            elif check_type == "service_running":
                result = self.verify_service_running(vm_config["host"], username, key_file, check["target"])
            elif check_type == "file_exists":
                result = self.verify_file_exists(vm_config["host"], username, key_file, check["target"])
            elif check_type == "directory_exists":
                result = self.verify_directory_exists(vm_config["host"], username, key_file, check["target"])
            elif check_type == "user_exists":
                result = self.verify_user_exists(vm_config["host"], username, key_file, check["target"])
            elif check_type == "command_output":
                result = self.verify_command_output(vm_config["host"], username, key_file, 
                                                   check["command"], check["expected"])
            elif check_type == "network_connectivity":
                result = self.verify_network_connectivity(vm_config["host"], username, key_file, check["target"])
            else:
                result = {
                    "check_type": check_type,
                    "target": check.get("target", ""),
                    "status": "SKIP",
                    "details": f"Unknown check type: {check_type}"
                }
            
            vm_result["checks"].append(result)
        
        # Calculate VM status
        if vm_result["checks"]:
            passed = sum(1 for c in vm_result["checks"] if c["status"] == "PASS")
            failed = sum(1 for c in vm_result["checks"] if c["status"] == "FAIL")
            
            if failed == 0:
                vm_result["status"] = "PASS"
            elif passed > 0:
                vm_result["status"] = "PARTIAL"
            else:
                vm_result["status"] = "FAIL"
        else:
            vm_result["status"] = "NO_CHECKS"
        
        return vm_result
    
    def run(self):
        """Run verification for all VMs"""
        
        if not self.load_config():
            self.results["status"] = "ERROR"
            return self.results
        
        vms = self.config.get("vms", [])
        
        if not vms:
            self.results["errors"].append("No VMs configured for verification")
            self.results["status"] = "ERROR"
            return self.results
        
        print(f"\n=== Verifying {len(vms)} VMs ===\n")
        
        for vm_config in vms:
            print(f"Verifying VM: {vm_config['name']}")
            vm_result = self.run_checklist(vm_config)
            self.results["vms"][vm_config["name"]] = vm_result
        
        # Calculate summary
        all_vms = list(self.results["vms"].values())
        passed_vms = sum(1 for vm in all_vms if vm["status"] == "PASS")
        failed_vms = sum(1 for vm in all_vms if vm["status"] in ["FAIL", "SSH_FAILED"])
        partial_vms = sum(1 for vm in all_vms if vm["status"] == "PARTIAL")
        
        total_checks = sum(len(vm["checks"]) for vm in all_vms)
        passed_checks = sum(sum(1 for c in vm["checks"] if c["status"] == "PASS") for vm in all_vms)
        failed_checks = sum(sum(1 for c in vm["checks"] if c["status"] == "FAIL") for vm in all_vms)
        
        self.results["summary"] = {
            "total_vms": len(all_vms),
            "passed_vms": passed_vms,
            "partial_vms": partial_vms,
            "failed_vms": failed_vms,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "vm_pass_rate": f"{(passed_vms / len(all_vms) * 100):.2f}%" if all_vms else "0%",
            "check_pass_rate": f"{(passed_checks / total_checks * 100):.2f}%" if total_checks > 0 else "0%"
        }
        
        # Set overall status
        if failed_vms == 0 and partial_vms == 0:
            self.results["status"] = "PASS"
        elif passed_vms > 0:
            self.results["status"] = "PARTIAL"
        else:
            self.results["status"] = "FAIL"
        
        return self.results
    
    def save_results(self, output_file):
        """Save results to JSON file"""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\nLayer D results saved to: {output_file}")


def main():
    if len(sys.argv) < 3:
        print("Usage: layer_d_userdata.py <config.json> <output.json>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    output_file = sys.argv[2]
    
    verifier = LayerDUserdataVerifier(config_file)
    results = verifier.run()
    verifier.save_results(output_file)
    
    # Print summary
    print(f"\n=== Layer D: User-Data Verification ===")
    print(f"Status: {results['status']}")
    print(f"VMs: {results['summary']['total_vms']}")
    print(f"Passed VMs: {results['summary']['passed_vms']}")
    print(f"Partial VMs: {results['summary']['partial_vms']}")
    print(f"Failed VMs: {results['summary']['failed_vms']}")
    print(f"VM Pass Rate: {results['summary']['vm_pass_rate']}")
    print(f"Total Checks: {results['summary']['total_checks']}")
    print(f"Passed Checks: {results['summary']['passed_checks']}")
    print(f"Check Pass Rate: {results['summary']['check_pass_rate']}")
    
    sys.exit(0 if results['status'] == 'PASS' else 1)


if __name__ == "__main__":
    main()
