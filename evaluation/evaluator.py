#!/usr/bin/env python3
"""
Main Evaluation Orchestrator
Runs all evaluation layers sequentially and generates final report
"""

import json
import sys
import os
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

class EvaluationOrchestrator:
    def __init__(self, config_file):
        self.config_file = Path(config_file)
        self.config = None
        self.results_dir = None
        self.evaluation_dir = Path(__file__).parent
        self.results = {
            "layers_executed": [],
            "layers_skipped": [],
            "errors": []
        }
    
    def load_config(self):
        """Load evaluation configuration"""
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            
            # Set results directory
            self.results_dir = Path(self.config.get("results_dir", "evaluation/results"))
            self.results_dir.mkdir(parents=True, exist_ok=True)
            
            return True
        except Exception as e:
            print(f"Error loading config: {str(e)}")
            return False
    
    def run_layer(self, layer_name, script_name, args):
        """Run a single evaluation layer"""
        
        print(f"\n{'='*80}")
        print(f"Running {layer_name}")
        print(f"{'='*80}")
        
        script_path = self.evaluation_dir / script_name
        
        if not script_path.exists():
            print(f"Error: Script not found: {script_path}")
            self.results["errors"].append(f"{layer_name}: Script not found")
            return False
        
        cmd = ["python3", str(script_path)] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=False,  # Show output in real-time
                text=True
            )
            
            if result.returncode == 0:
                print(f"\n✓ {layer_name} completed successfully")
                self.results["layers_executed"].append(layer_name)
                return True
            else:
                print(f"\n✗ {layer_name} failed with exit code {result.returncode}")
                self.results["errors"].append(f"{layer_name}: Exit code {result.returncode}")
                return False
                
        except Exception as e:
            print(f"\n✗ {layer_name} error: {str(e)}")
            self.results["errors"].append(f"{layer_name}: {str(e)}")
            return False
    
    def run_layer_a(self):
        """Run Layer A: Input Validation"""
        
        if not self.config.get("layer_a", {}).get("enabled", True):
            print("Layer A: Skipped (disabled in config)")
            self.results["layers_skipped"].append("Layer A")
            return True
        
        topology_file = self.config["layer_a"]["topology_file"]
        cloudinit_file = self.config["layer_a"].get("cloudinit_file")
        output_file = self.results_dir / "layer_a_result.json"
        
        args = [topology_file, str(output_file)]
        if cloudinit_file:
            args.append(cloudinit_file)
        
        return self.run_layer("Layer A: Input Validation", "layer_a_validation.py", args)
    
    def run_layer_b(self):
        """Run Layer B: Terraform Deployment"""
        
        if not self.config.get("layer_b", {}).get("enabled", True):
            print("Layer B: Skipped (disabled in config)")
            self.results["layers_skipped"].append("Layer B")
            return True
        
        terraform_dir = self.config["layer_b"]["terraform_project_dir"]
        cloud_provider = self.config["layer_b"]["cloud_provider"]
        output_file = self.results_dir / "layer_b_result.json"
        skip_apply = self.config["layer_b"].get("skip_apply", False)
        
        args = [terraform_dir, cloud_provider, str(output_file)]
        if skip_apply:
            args.append("--skip-apply")
        
        return self.run_layer("Layer B: Terraform Deployment", "layer_b_terraform.py", args)
    
    def run_layer_c(self):
        """Run Layer C: Model Consistency Check"""
        
        if not self.config.get("layer_c", {}).get("enabled", True):
            print("Layer C: Skipped (disabled in config)")
            self.results["layers_skipped"].append("Layer C")
            return True
        
        topology_file = self.config["layer_c"]["topology_file"]
        state_file = self.config["layer_c"]["state_file"]
        cloud_provider = self.config["layer_c"]["cloud_provider"]
        output_file = self.results_dir / "layer_c_result.json"
        
        # Check if state file exists
        if not Path(state_file).exists():
            print(f"Warning: State file not found: {state_file}")
            print("Layer C: Skipped (state file missing)")
            self.results["layers_skipped"].append("Layer C")
            return True
        
        args = [topology_file, state_file, cloud_provider, str(output_file)]
        
        return self.run_layer("Layer C: Model Consistency Check", "layer_c_consistency.py", args)
    
    def run_layer_d(self):
        """Run Layer D: User-Data Verification"""
        
        if not self.config.get("layer_d", {}).get("enabled", True):
            print("Layer D: Skipped (disabled in config)")
            self.results["layers_skipped"].append("Layer D")
            return True
        
        vm_config_file = self.config["layer_d"]["vm_config_file"]
        output_file = self.results_dir / "layer_d_result.json"
        
        # Check if VM config exists
        if not Path(vm_config_file).exists():
            print(f"Warning: VM config not found: {vm_config_file}")
            print("Layer D: Skipped (config missing)")
            self.results["layers_skipped"].append("Layer D")
            return True
        
        args = [vm_config_file, str(output_file)]
        
        return self.run_layer("Layer D: User-Data Verification", "layer_d_userdata.py", args)
    
    def run_aggregator(self):
        """Run result aggregator"""
        
        print(f"\n{'='*80}")
        print("Aggregating Results")
        print(f"{'='*80}")
        
        output_json = self.results_dir / "final_report.json"
        output_text = self.results_dir / "final_report.txt"
        output_csv = self.results_dir / "final_report.csv"
        
        args = [
            str(self.results_dir),
            "--output", str(output_json),
            "--text", str(output_text),
            "--csv", str(output_csv)
        ]
        
        return self.run_layer("Result Aggregation", "aggregator.py", args)
    
    def run(self):
        """Run complete evaluation"""
        
        if not self.load_config():
            print("Failed to load configuration")
            return False
        
        print(f"\n{'='*80}")
        print("EVALUATION FRAMEWORK")
        print("JSON-To-Terraform Multi-Cloud Deployment Pipeline")
        print(f"{'='*80}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        print(f"Config: {self.config_file}")
        print(f"Results: {self.results_dir}")
        print(f"{'='*80}")
        
        # Run layers in sequence
        success = True
        
        # Layer A: Input Validation
        if not self.run_layer_a():
            print("\n⚠ Layer A failed, but continuing...")
            success = False
        
        # Layer B: Terraform Deployment
        layer_b_result = self.run_layer_b()
        if not layer_b_result:
            print("\n⚠ Layer B failed, subsequent layers may be affected...")
            success = False
        
        # Layer C: Model Consistency (depends on Layer B)
        if layer_b_result or self.config.get("continue_on_error", False):
            if not self.run_layer_c():
                print("\n⚠ Layer C failed, but continuing...")
                success = False
        else:
            print("\nLayer C: Skipped (Layer B failed)")
            self.results["layers_skipped"].append("Layer C")
        
        # Layer D: User-Data Verification (depends on Layer B)
        if layer_b_result or self.config.get("continue_on_error", False):
            if not self.run_layer_d():
                print("\n⚠ Layer D failed, but continuing...")
                success = False
        else:
            print("\nLayer D: Skipped (Layer B failed)")
            self.results["layers_skipped"].append("Layer D")
        
        # Aggregate results
        self.run_aggregator()
        
        # Print summary
        print(f"\n{'='*80}")
        print("EVALUATION COMPLETE")
        print(f"{'='*80}")
        print(f"Layers Executed: {len(self.results['layers_executed'])}")
        print(f"Layers Skipped: {len(self.results['layers_skipped'])}")
        print(f"Errors: {len(self.results['errors'])}")
        
        if self.results['errors']:
            print("\nErrors:")
            for error in self.results['errors']:
                print(f"  - {error}")
        
        print(f"\nResults saved to: {self.results_dir}")
        print(f"{'='*80}\n")
        
        return success


def main():
    parser = argparse.ArgumentParser(
        description="Evaluation Framework for JSON-To-Terraform Multi-Cloud Deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full evaluation
  ./evaluator.py evaluation_config.json
  
  # Run with custom config
  ./evaluator.py my_config.json
        """
    )
    
    parser.add_argument(
        "config",
        help="Path to evaluation configuration JSON file"
    )
    
    args = parser.parse_args()
    
    orchestrator = EvaluationOrchestrator(args.config)
    success = orchestrator.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
