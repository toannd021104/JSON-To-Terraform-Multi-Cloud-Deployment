#!/usr/bin/env python3
"""
Result Aggregator
Merges all layer results into a final evaluation summary
Output: Comprehensive JSON report and text table
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List

class ResultAggregator:
    def __init__(self):
        self.layers = {}
        self.final_report = {
            "evaluation_framework": "JSON-To-Terraform Multi-Cloud Deployment",
            "timestamp": datetime.utcnow().isoformat(),
            "layers": {},
            "summary": {},
            "overall_status": "UNKNOWN"
        }
    
    def load_layer_result(self, layer_name, result_file):
        """Load a layer result JSON file"""
        try:
            with open(result_file, 'r') as f:
                data = json.load(f)
                self.layers[layer_name] = data
                return True
        except FileNotFoundError:
            print(f"Warning: Result file not found: {result_file}")
            return False
        except Exception as e:
            print(f"Error loading {result_file}: {str(e)}")
            return False
    
    def aggregate(self):
        """Aggregate all layer results"""
        
        # Layer A: Input Validation
        if "layer_a" in self.layers:
            layer_a = self.layers["layer_a"]
            self.final_report["layers"]["A_INPUT_VALIDATION"] = {
                "status": layer_a.get("status"),
                "tests": layer_a.get("summary", {}).get("total_tests", 0),
                "passed": layer_a.get("summary", {}).get("passed", 0),
                "failed": layer_a.get("summary", {}).get("failed", 0),
                "pass_rate": layer_a.get("summary", {}).get("pass_rate", "0%"),
                "errors": len(layer_a.get("errors", []))
            }
        
        # Layer B: Terraform Deployment
        if "layer_b" in self.layers:
            layer_b = self.layers["layer_b"]
            self.final_report["layers"]["B_TERRAFORM_DEPLOYMENT"] = {
                "status": layer_b.get("status"),
                "cloud_provider": layer_b.get("cloud_provider"),
                "duration_seconds": layer_b.get("metrics", {}).get("total_duration_seconds", 0),
                "resources_planned": layer_b.get("metrics", {}).get("resources_planned", 0),
                "resources_created": layer_b.get("metrics", {}).get("resources_created", 0),
                "resources_in_state": layer_b.get("metrics", {}).get("resources_in_state", 0),
                "success_rate": layer_b.get("summary", {}).get("success_rate", "0%"),
                "errors": len(layer_b.get("errors", []))
            }
        
        # Layer C: Model Consistency
        if "layer_c" in self.layers:
            layer_c = self.layers["layer_c"]
            self.final_report["layers"]["C_MODEL_CONSISTENCY"] = {
                "status": layer_c.get("status"),
                "checks": layer_c.get("summary", {}).get("total_checks", 0),
                "passed": layer_c.get("summary", {}).get("passed", 0),
                "failed": layer_c.get("summary", {}).get("failed", 0),
                "mismatches": layer_c.get("summary", {}).get("total_mismatches", 0),
                "consistency_rate": layer_c.get("summary", {}).get("consistency_rate", "0%")
            }
        
        # Layer D: User-Data Verification
        if "layer_d" in self.layers:
            layer_d = self.layers["layer_d"]
            self.final_report["layers"]["D_USERDATA_VERIFICATION"] = {
                "status": layer_d.get("status"),
                "total_vms": layer_d.get("summary", {}).get("total_vms", 0),
                "passed_vms": layer_d.get("summary", {}).get("passed_vms", 0),
                "failed_vms": layer_d.get("summary", {}).get("failed_vms", 0),
                "total_checks": layer_d.get("summary", {}).get("total_checks", 0),
                "passed_checks": layer_d.get("summary", {}).get("passed_checks", 0),
                "vm_pass_rate": layer_d.get("summary", {}).get("vm_pass_rate", "0%"),
                "check_pass_rate": layer_d.get("summary", {}).get("check_pass_rate", "0%")
            }
        
        # Calculate overall summary
        self._calculate_overall_summary()
    
    def _calculate_overall_summary(self):
        """Calculate overall evaluation summary"""
        
        layers_completed = len(self.final_report["layers"])
        layers_passed = 0
        layers_failed = 0
        layers_partial = 0
        
        for layer_name, layer_data in self.final_report["layers"].items():
            status = layer_data.get("status", "UNKNOWN")
            
            if status in ["PASS", "SUCCESS", "CONSISTENT"]:
                layers_passed += 1
            elif status in ["FAIL", "FAILED", "INCONSISTENT", "ERROR"]:
                layers_failed += 1
            elif status in ["PARTIAL", "PARTIAL_SUCCESS"]:
                layers_partial += 1
        
        self.final_report["summary"] = {
            "total_layers": layers_completed,
            "layers_passed": layers_passed,
            "layers_failed": layers_failed,
            "layers_partial": layers_partial,
            "overall_success_rate": f"{(layers_passed / layers_completed * 100):.2f}%" if layers_completed > 0 else "0%"
        }
        
        # Determine overall status
        if layers_failed == 0 and layers_partial == 0 and layers_passed > 0:
            self.final_report["overall_status"] = "SUCCESS"
        elif layers_failed > 0:
            self.final_report["overall_status"] = "FAILED"
        elif layers_partial > 0:
            self.final_report["overall_status"] = "PARTIAL_SUCCESS"
        else:
            self.final_report["overall_status"] = "INCOMPLETE"
    
    def generate_text_table(self):
        """Generate human-readable text table"""
        
        lines = []
        lines.append("\n" + "="*80)
        lines.append("EVALUATION FRAMEWORK - FINAL REPORT")
        lines.append("JSON-To-Terraform Multi-Cloud Deployment Pipeline")
        lines.append("="*80)
        lines.append(f"Timestamp: {self.final_report['timestamp']}")
        lines.append(f"Overall Status: {self.final_report['overall_status']}")
        lines.append(f"Success Rate: {self.final_report['summary']['overall_success_rate']}")
        lines.append("="*80)
        
        # Layer A
        if "A_INPUT_VALIDATION" in self.final_report["layers"]:
            layer = self.final_report["layers"]["A_INPUT_VALIDATION"]
            lines.append("\n[Layer A] INPUT VALIDATION")
            lines.append("-" * 80)
            lines.append(f"  Status:         {layer['status']}")
            lines.append(f"  Tests:          {layer['tests']}")
            lines.append(f"  Passed:         {layer['passed']}")
            lines.append(f"  Failed:         {layer['failed']}")
            lines.append(f"  Pass Rate:      {layer['pass_rate']}")
            lines.append(f"  Errors:         {layer['errors']}")
        
        # Layer B
        if "B_TERRAFORM_DEPLOYMENT" in self.final_report["layers"]:
            layer = self.final_report["layers"]["B_TERRAFORM_DEPLOYMENT"]
            lines.append("\n[Layer B] TERRAFORM DEPLOYMENT")
            lines.append("-" * 80)
            lines.append(f"  Status:             {layer['status']}")
            lines.append(f"  Cloud Provider:     {layer['cloud_provider']}")
            lines.append(f"  Duration:           {layer['duration_seconds']:.2f}s")
            lines.append(f"  Resources Planned:  {layer['resources_planned']}")
            lines.append(f"  Resources Created:  {layer['resources_created']}")
            lines.append(f"  Resources in State: {layer['resources_in_state']}")
            lines.append(f"  Success Rate:       {layer['success_rate']}")
        
        # Layer C
        if "C_MODEL_CONSISTENCY" in self.final_report["layers"]:
            layer = self.final_report["layers"]["C_MODEL_CONSISTENCY"]
            lines.append("\n[Layer C] MODEL CONSISTENCY CHECK")
            lines.append("-" * 80)
            lines.append(f"  Status:           {layer['status']}")
            lines.append(f"  Checks:           {layer['checks']}")
            lines.append(f"  Passed:           {layer['passed']}")
            lines.append(f"  Failed:           {layer['failed']}")
            lines.append(f"  Mismatches:       {layer['mismatches']}")
            lines.append(f"  Consistency Rate: {layer['consistency_rate']}")
        
        # Layer D
        if "D_USERDATA_VERIFICATION" in self.final_report["layers"]:
            layer = self.final_report["layers"]["D_USERDATA_VERIFICATION"]
            lines.append("\n[Layer D] USER-DATA VERIFICATION")
            lines.append("-" * 80)
            lines.append(f"  Status:              {layer['status']}")
            lines.append(f"  Total VMs:           {layer['total_vms']}")
            lines.append(f"  Passed VMs:          {layer['passed_vms']}")
            lines.append(f"  Failed VMs:          {layer['failed_vms']}")
            lines.append(f"  VM Pass Rate:        {layer['vm_pass_rate']}")
            lines.append(f"  Total Checks:        {layer['total_checks']}")
            lines.append(f"  Passed Checks:       {layer['passed_checks']}")
            lines.append(f"  Check Pass Rate:     {layer['check_pass_rate']}")
        
        lines.append("\n" + "="*80)
        lines.append("SUMMARY")
        lines.append("="*80)
        lines.append(f"  Total Layers:     {self.final_report['summary']['total_layers']}")
        lines.append(f"  Layers Passed:    {self.final_report['summary']['layers_passed']}")
        lines.append(f"  Layers Failed:    {self.final_report['summary']['layers_failed']}")
        lines.append(f"  Layers Partial:   {self.final_report['summary']['layers_partial']}")
        lines.append(f"  Success Rate:     {self.final_report['summary']['overall_success_rate']}")
        lines.append(f"  Overall Status:   {self.final_report['overall_status']}")
        lines.append("="*80 + "\n")
        
        return "\n".join(lines)
    
    def generate_csv_table(self):
        """Generate CSV format for spreadsheet import"""
        
        lines = []
        lines.append("Layer,Metric,Value")
        
        for layer_name, layer_data in self.final_report["layers"].items():
            for metric, value in layer_data.items():
                lines.append(f"{layer_name},{metric},{value}")
        
        lines.append("")
        lines.append("Summary,Metric,Value")
        for metric, value in self.final_report["summary"].items():
            lines.append(f"Overall,{metric},{value}")
        
        return "\n".join(lines)
    
    def save_report(self, output_json, output_text=None, output_csv=None):
        """Save aggregated report to files"""
        
        # Save JSON
        with open(output_json, 'w') as f:
            json.dump(self.final_report, f, indent=2)
        print(f"Final report saved to: {output_json}")
        
        # Save text table
        if output_text:
            text_report = self.generate_text_table()
            with open(output_text, 'w') as f:
                f.write(text_report)
            print(f"Text report saved to: {output_text}")
            print(text_report)
        
        # Save CSV
        if output_csv:
            csv_report = self.generate_csv_table()
            with open(output_csv, 'w') as f:
                f.write(csv_report)
            print(f"CSV report saved to: {output_csv}")


def main():
    if len(sys.argv) < 2:
        print("Usage: aggregator.py <results_dir> [--output <output.json>] [--text <output.txt>] [--csv <output.csv>]")
        print("\nExample:")
        print("  aggregator.py evaluation/results/")
        print("  aggregator.py evaluation/results/ --output final_report.json --text final_report.txt")
        sys.exit(1)
    
    results_dir = Path(sys.argv[1])
    
    # Parse optional arguments
    output_json = "final_report.json"
    output_text = None
    output_csv = None
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--output" and i + 1 < len(sys.argv):
            output_json = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--text" and i + 1 < len(sys.argv):
            output_text = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--csv" and i + 1 < len(sys.argv):
            output_csv = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    
    aggregator = ResultAggregator()
    
    # Load layer results
    print("\nLoading layer results...")
    aggregator.load_layer_result("layer_a", results_dir / "layer_a_result.json")
    aggregator.load_layer_result("layer_b", results_dir / "layer_b_result.json")
    aggregator.load_layer_result("layer_c", results_dir / "layer_c_result.json")
    aggregator.load_layer_result("layer_d", results_dir / "layer_d_result.json")
    
    # Aggregate
    print("Aggregating results...")
    aggregator.aggregate()
    
    # Save report
    aggregator.save_report(output_json, output_text, output_csv)
    
    # Exit with appropriate code
    overall_status = aggregator.final_report["overall_status"]
    sys.exit(0 if overall_status == "SUCCESS" else 1)


if __name__ == "__main__":
    main()
