#!/usr/bin/env python3
"""
Layer B: Terraform Deployment Evaluator
Runs terraform init/plan/apply and captures metrics
Output: JSON with deployment results
"""

import json
import sys
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime

class LayerBTerraformEvaluator:
    def __init__(self, terraform_project_dir, cloud_provider):
        self.terraform_dir = Path(terraform_project_dir)
        self.cloud_provider = cloud_provider.lower()
        self.results = {
            "layer": "B_TERRAFORM_DEPLOYMENT",
            "timestamp": datetime.utcnow().isoformat(),
            "cloud_provider": cloud_provider,
            "project_dir": str(terraform_project_dir),
            "status": "UNKNOWN",
            "phases": {},
            "metrics": {},
            "errors": [],
            "summary": {}
        }
    
    def run_terraform_command(self, command, phase_name):
        """Execute terraform command and capture results"""
        phase_result = {
            "phase": phase_name,
            "command": command,
            "status": "UNKNOWN",
            "exit_code": None,
            "duration_seconds": 0,
            "stdout": "",
            "stderr": "",
            "errors": []
        }
        
        start_time = time.time()
        
        try:
            print(f"Running: {command} in {self.terraform_dir}")
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.terraform_dir,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )
            
            phase_result["exit_code"] = result.returncode
            phase_result["stdout"] = result.stdout
            phase_result["stderr"] = result.stderr
            phase_result["duration_seconds"] = time.time() - start_time
            
            if result.returncode == 0:
                phase_result["status"] = "SUCCESS"
            else:
                phase_result["status"] = "FAILED"
                phase_result["errors"].append(f"Exit code: {result.returncode}")
                if result.stderr:
                    phase_result["errors"].append(result.stderr[:500])  # First 500 chars
            
        except subprocess.TimeoutExpired:
            phase_result["status"] = "TIMEOUT"
            phase_result["duration_seconds"] = time.time() - start_time
            phase_result["errors"].append(f"Command timeout after {phase_result['duration_seconds']:.2f}s")
        except Exception as e:
            phase_result["status"] = "ERROR"
            phase_result["duration_seconds"] = time.time() - start_time
            phase_result["errors"].append(f"Execution error: {str(e)}")
        
        return phase_result
    
    def terraform_init(self):
        """Run terraform init"""
        return self.run_terraform_command("terraform init -no-color", "init")
    
    def terraform_validate(self):
        """Run terraform validate"""
        return self.run_terraform_command("terraform validate -no-color", "validate")
    
    def terraform_plan(self):
        """Run terraform plan"""
        phase_result = self.run_terraform_command(
            "terraform plan -no-color -detailed-exitcode -out=tfplan", 
            "plan"
        )
        
        # Parse plan output for resource counts
        if phase_result["status"] in ["SUCCESS", "FAILED"]:
            phase_result["resources_to_create"] = self._count_resources(phase_result["stdout"], "to create")
            phase_result["resources_to_change"] = self._count_resources(phase_result["stdout"], "to change")
            phase_result["resources_to_destroy"] = self._count_resources(phase_result["stdout"], "to destroy")
        
        return phase_result
    
    def terraform_apply(self):
        """Run terraform apply"""
        phase_result = self.run_terraform_command(
            "terraform apply -no-color -auto-approve tfplan",
            "apply"
        )
        
        # Parse apply output for created resources
        if phase_result["status"] == "SUCCESS":
            phase_result["resources_created"] = self._count_resources(phase_result["stdout"], "complete")
            phase_result["resources_failed"] = self._count_resources(phase_result["stdout"], "error")
        
        return phase_result
    
    def _count_resources(self, output, keyword):
        """Extract resource count from terraform output"""
        try:
            for line in output.split('\n'):
                if keyword in line.lower() and 'resource' in line.lower():
                    # Try to extract number
                    words = line.split()
                    for word in words:
                        if word.isdigit():
                            return int(word)
        except:
            pass
        return 0
    
    def get_state_info(self):
        """Get information from terraform.tfstate"""
        state_info = {
            "state_file_exists": False,
            "resources_in_state": 0,
            "resource_types": {}
        }
        
        state_file = self.terraform_dir / "terraform.tfstate"
        
        if state_file.exists():
            state_info["state_file_exists"] = True
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                
                if "resources" in state:
                    state_info["resources_in_state"] = len(state["resources"])
                    
                    # Count by type
                    for resource in state["resources"]:
                        res_type = resource.get("type", "unknown")
                        state_info["resource_types"][res_type] = state_info["resource_types"].get(res_type, 0) + 1
                
            except Exception as e:
                state_info["error"] = f"Failed to parse state file: {str(e)}"
        
        return state_info
    
    def run(self, skip_apply=False):
        """Run all terraform phases"""
        
        # Phase 1: Init
        print("\n=== Phase 1: terraform init ===")
        self.results["phases"]["init"] = self.terraform_init()
        if self.results["phases"]["init"]["status"] != "SUCCESS":
            self.results["status"] = "FAILED_INIT"
            return self.results
        
        # Phase 2: Validate
        print("\n=== Phase 2: terraform validate ===")
        self.results["phases"]["validate"] = self.terraform_validate()
        if self.results["phases"]["validate"]["status"] != "SUCCESS":
            self.results["status"] = "FAILED_VALIDATE"
            return self.results
        
        # Phase 3: Plan
        print("\n=== Phase 3: terraform plan ===")
        self.results["phases"]["plan"] = self.terraform_plan()
        if self.results["phases"]["plan"]["status"] == "ERROR" or self.results["phases"]["plan"]["status"] == "TIMEOUT":
            self.results["status"] = "FAILED_PLAN"
            return self.results
        
        # Phase 4: Apply (optional)
        if not skip_apply:
            print("\n=== Phase 4: terraform apply ===")
            self.results["phases"]["apply"] = self.terraform_apply()
            
            if self.results["phases"]["apply"]["status"] == "SUCCESS":
                self.results["status"] = "SUCCESS"
            else:
                self.results["status"] = "FAILED_APPLY"
        else:
            self.results["status"] = "SUCCESS_PLAN_ONLY"
        
        # Get state info
        self.results["state_info"] = self.get_state_info()
        
        # Calculate metrics
        self._calculate_metrics()
        
        # Aggregate errors
        for phase in self.results["phases"].values():
            self.results["errors"].extend(phase.get("errors", []))
        
        return self.results
    
    def _calculate_metrics(self):
        """Calculate deployment metrics"""
        phases = self.results["phases"]
        
        self.results["metrics"] = {
            "total_duration_seconds": sum(p.get("duration_seconds", 0) for p in phases.values()),
            "init_duration": phases.get("init", {}).get("duration_seconds", 0),
            "plan_duration": phases.get("plan", {}).get("duration_seconds", 0),
            "apply_duration": phases.get("apply", {}).get("duration_seconds", 0),
            "resources_planned": phases.get("plan", {}).get("resources_to_create", 0),
            "resources_created": phases.get("apply", {}).get("resources_created", 0),
            "resources_in_state": self.results.get("state_info", {}).get("resources_in_state", 0)
        }
        
        # Calculate success rates
        successful_phases = sum(1 for p in phases.values() if p["status"] == "SUCCESS")
        total_phases = len(phases)
        
        self.results["summary"] = {
            "phases_total": total_phases,
            "phases_success": successful_phases,
            "phases_failed": total_phases - successful_phases,
            "success_rate": f"{(successful_phases / total_phases * 100):.2f}%" if total_phases > 0 else "0%",
            "overall_status": self.results["status"]
        }
    
    def save_results(self, output_file):
        """Save results to JSON file"""
        # Remove verbose stdout/stderr from phases to reduce file size
        for phase in self.results["phases"].values():
            if len(phase.get("stdout", "")) > 1000:
                phase["stdout"] = phase["stdout"][:1000] + "\n... (truncated)"
            if len(phase.get("stderr", "")) > 1000:
                phase["stderr"] = phase["stderr"][:1000] + "\n... (truncated)"
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\nLayer B results saved to: {output_file}")


def main():
    if len(sys.argv) < 4:
        print("Usage: layer_b_terraform.py <terraform_project_dir> <cloud_provider> <output.json> [--skip-apply]")
        sys.exit(1)
    
    terraform_dir = sys.argv[1]
    cloud_provider = sys.argv[2]
    output_file = sys.argv[3]
    skip_apply = "--skip-apply" in sys.argv
    
    evaluator = LayerBTerraformEvaluator(terraform_dir, cloud_provider)
    results = evaluator.run(skip_apply=skip_apply)
    evaluator.save_results(output_file)
    
    # Print summary
    print(f"\n=== Layer B: Terraform Deployment ===")
    print(f"Cloud Provider: {results['cloud_provider']}")
    print(f"Status: {results['status']}")
    print(f"Total Duration: {results['metrics']['total_duration_seconds']:.2f}s")
    print(f"Resources Planned: {results['metrics']['resources_planned']}")
    print(f"Resources Created: {results['metrics']['resources_created']}")
    print(f"Resources in State: {results['metrics']['resources_in_state']}")
    print(f"Success Rate: {results['summary']['success_rate']}")
    
    if results['errors']:
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results['errors'][:5]:
            print(f"  - {error}")
    
    sys.exit(0 if results['status'] in ['SUCCESS', 'SUCCESS_PLAN_ONLY'] else 1)


if __name__ == "__main__":
    main()
