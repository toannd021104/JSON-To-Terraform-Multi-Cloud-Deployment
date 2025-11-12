#!/usr/bin/env python3
"""
Benchmark and test deployment script
- Creates multiple infrastructure copies
- Tracks resources created
- Measures deployment time
- Option to cleanup resources after testing
"""

import os
import sys
import json
import time
import subprocess
import argparse
from datetime import datetime
from pathlib import Path


class DeploymentBenchmark:
    def __init__(self, provider, num_copies, auto_cleanup=False):
        self.provider = provider
        self.num_copies = num_copies
        self.auto_cleanup = auto_cleanup
        self.results = {
            "provider": provider,
            "num_copies": num_copies,
            "timestamp": datetime.now().isoformat(),
            "stages": {},
            "resources_created": {},
            "total_time": 0
        }
        self.project_folder = None

    def run(self):
        """Main execution flow"""
        print("\n" + "=" * 70)
        print(f"  DEPLOYMENT BENCHMARK - {self.provider.upper()}")
        print("=" * 70)
        print(f"Provider: {self.provider}")
        print(f"Number of copies: {self.num_copies}")
        print(f"Auto cleanup: {self.auto_cleanup}")
        print("=" * 70 + "\n")

        try:
            # Stage 1: Generate Terraform configs
            self._stage_generate()

            # Stage 2: Track resources created
            self._stage_track_resources()

            # Stage 3: Cleanup (optional)
            if self.auto_cleanup:
                self._stage_cleanup()
            else:
                self._prompt_cleanup()

            # Save results
            self._save_results()

            # Print summary
            self._print_summary()

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            self._prompt_cleanup()
        except Exception as e:
            print(f"\n❌ Error: {e}")
            sys.exit(1)

    def _stage_generate(self):
        """Stage 1: Generate and deploy infrastructure"""
        print("\n━━━ Stage 1: Generate & Deploy ━━━")

        start_time = time.time()

        # Run generate.py
        cmd = ["python3", "generate.py", self.provider, str(self.num_copies)]
        print(f"Running: {' '.join(cmd)}")
        print("-" * 70)

        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=False,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Generation failed with exit code {result.returncode}")

        elapsed = time.time() - start_time

        # Find the generated project folder
        self._find_project_folder()

        self.results["stages"]["generate"] = {
            "duration_seconds": round(elapsed, 2),
            "duration_formatted": self._format_duration(elapsed),
            "project_folder": str(self.project_folder) if self.project_folder else None
        }

        print("-" * 70)
        print(f"✓ Generation completed in {self._format_duration(elapsed)}")

    def _stage_track_resources(self):
        """Stage 2: Track resources created"""
        print("\n━━━ Stage 2: Track Resources ━━━")

        if not self.project_folder or not self.project_folder.exists():
            print("⚠️  Project folder not found, skipping resource tracking")
            return

        resources = self._extract_resources()
        self.results["resources_created"] = resources

        # Print resource summary
        print("\n📦 Resources Created:")
        if self.provider == "aws":
            if "00-shared-vpc" in resources:
                print("\n  Shared VPC Resources:")
                for key, value in resources["00-shared-vpc"].items():
                    print(f"    - {key}: {value}")

        total_instances = 0
        for folder, res in resources.items():
            if folder != "00-shared-vpc":
                instances = res.get("instances", 0)
                total_instances += instances
                print(f"\n  {folder}:")
                print(f"    - Instances: {instances}")

        print(f"\n  📊 Total instances across all copies: {total_instances}")

    def _stage_cleanup(self):
        """Stage 3: Cleanup resources"""
        print("\n━━━ Stage 3: Cleanup ━━━")

        if not self.project_folder or not self.project_folder.exists():
            print("⚠️  Project folder not found, skipping cleanup")
            return

        print("🗑️  Destroying all resources...")
        print("-" * 70)

        start_time = time.time()

        result = subprocess.run(
            ["python3", "run_terraform.py", "destroy"],
            cwd=str(self.project_folder),
            capture_output=False,
            text=True
        )

        elapsed = time.time() - start_time

        self.results["stages"]["cleanup"] = {
            "duration_seconds": round(elapsed, 2),
            "duration_formatted": self._format_duration(elapsed),
            "success": result.returncode == 0
        }

        print("-" * 70)
        if result.returncode == 0:
            print(f"✓ Cleanup completed in {self._format_duration(elapsed)}")
        else:
            print(f"❌ Cleanup failed")

    def _prompt_cleanup(self):
        """Prompt user for cleanup"""
        print("\n" + "=" * 70)
        response = input("Do you want to destroy all created resources? (yes/no): ").strip().lower()

        if response in ['yes', 'y']:
            self._stage_cleanup()
        else:
            print("ℹ️  Resources preserved. Manual cleanup required:")
            print(f"   cd {self.project_folder}")
            print(f"   python3 run_terraform.py destroy")

    def _find_project_folder(self):
        """Find the most recently created project folder"""
        projects_dir = Path(__file__).parent.parent / "terraform-projects"

        if not projects_dir.exists():
            return

        # Find folders matching provider pattern
        pattern = f"{self.provider}_*"
        folders = sorted(
            [f for f in projects_dir.glob(pattern) if f.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        if folders:
            self.project_folder = folders[0]

    def _extract_resources(self):
        """Extract resource information from Terraform state"""
        resources = {}

        # Check shared VPC folder
        if self.provider == "aws":
            shared_vpc = self.project_folder / "00-shared-vpc"
            if shared_vpc.exists():
                resources["00-shared-vpc"] = self._count_resources_in_folder(shared_vpc)

        # Check instance folders
        for folder in self.project_folder.iterdir():
            if folder.is_dir() and folder.name.startswith(f"{self.provider}_"):
                resources[folder.name] = self._count_resources_in_folder(folder)

        return resources

    def _count_resources_in_folder(self, folder):
        """Count resources in a Terraform folder"""
        state_file = folder / "terraform.tfstate"

        if not state_file.exists():
            return {"error": "No state file found"}

        try:
            with open(state_file, 'r') as f:
                state = json.load(f)

            resources = state.get("resources", [])

            counts = {}
            for resource in resources:
                resource_type = resource.get("type", "unknown")
                counts[resource_type] = counts.get(resource_type, 0) + 1

            # Add summary
            counts["total"] = len(resources)
            counts["instances"] = sum(1 for r in resources if "instance" in r.get("type", "").lower())

            return counts
        except Exception as e:
            return {"error": str(e)}

    def _save_results(self):
        """Save benchmark results to file"""
        # Calculate total time
        total_time = sum(
            stage["duration_seconds"]
            for stage in self.results["stages"].values()
            if "duration_seconds" in stage
        )
        self.results["total_time"] = round(total_time, 2)
        self.results["total_time_formatted"] = self._format_duration(total_time)

        # Save to JSON file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_{self.provider}_{self.num_copies}copies_{timestamp}.json"

        logs_dir = Path(__file__).parent / "benchmark_logs"
        logs_dir.mkdir(exist_ok=True)

        filepath = logs_dir / filename

        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n💾 Results saved to: {filepath}")

    def _print_summary(self):
        """Print benchmark summary"""
        print("\n" + "=" * 70)
        print("  BENCHMARK SUMMARY")
        print("=" * 70)

        print(f"\nProvider: {self.provider}")
        print(f"Number of copies: {self.num_copies}")
        print(f"Timestamp: {self.results['timestamp']}")

        print("\n⏱️  Timing:")
        for stage_name, stage_data in self.results["stages"].items():
            if "duration_formatted" in stage_data:
                print(f"  - {stage_name.capitalize()}: {stage_data['duration_formatted']}")

        print(f"  - Total: {self.results['total_time_formatted']}")

        if self.results.get("resources_created"):
            print("\n📦 Resources Summary:")
            total_instances = 0
            for folder, res in self.results["resources_created"].items():
                if isinstance(res, dict) and "instances" in res:
                    instances = res["instances"]
                    total_instances += instances
                    if instances > 0:
                        print(f"  - {folder}: {instances} instances")

            print(f"\n  Total instances: {total_instances}")

        print("\n" + "=" * 70)

    @staticmethod
    def _format_duration(seconds):
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.2f}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = seconds % 60
            return f"{mins}m {secs:.2f}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours}h {mins}m {secs:.2f}s"


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark multi-copy infrastructure deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test AWS deployment with 3 copies, prompt for cleanup
  python3 benchmark_deployment.py aws 3

  # Test OpenStack with 2 copies, auto cleanup
  python3 benchmark_deployment.py openstack 2 --auto-cleanup

  # Test AWS with 5 copies, keep resources
  python3 benchmark_deployment.py aws 5 --no-cleanup
        """
    )

    parser.add_argument(
        "provider",
        choices=["aws", "openstack"],
        help="Cloud provider to test"
    )

    parser.add_argument(
        "num_copies",
        type=int,
        help="Number of infrastructure copies to create"
    )

    parser.add_argument(
        "--auto-cleanup",
        action="store_true",
        help="Automatically destroy resources after testing"
    )

    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep resources after testing (no prompt)"
    )

    args = parser.parse_args()

    # Validate
    if args.num_copies < 1:
        print("Error: Number of copies must be at least 1")
        sys.exit(1)

    if args.num_copies > 10:
        print("⚠️  Warning: Creating more than 10 copies may take significant time and cost")
        response = input("Continue? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Cancelled")
            sys.exit(0)

    # Determine cleanup behavior
    auto_cleanup = args.auto_cleanup and not args.no_cleanup

    # Run benchmark
    benchmark = DeploymentBenchmark(
        provider=args.provider,
        num_copies=args.num_copies,
        auto_cleanup=auto_cleanup
    )

    benchmark.run()


if __name__ == "__main__":
    main()
