import os
import sys
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Run a Terraform command inside a specific folder (thread-safe version)
def run_command_safe(folder, command):
    try:
        print(f"\nProcessing {folder.name}...")

        # Use subprocess with cwd instead of os.chdir to avoid race condition
        if command == "init":
            cmd = ["terraform", command]
        else:
            cmd = ["terraform", command, "-auto-approve"]

        result = subprocess.run(
            cmd,
            cwd=str(folder.absolute()),
            capture_output=False,
            text=True
        )

        exit_code = result.returncode

        # Print error message if command failed
        if exit_code != 0:
            print(f"Error in {folder.name}")

        return exit_code

    except Exception as e:
        print(f"Error processing {folder}: {str(e)}")
        return 1

# Legacy function for backwards compatibility
def run_command(folder, command):
    return run_command_safe(folder, command)

# Run the command in parallel for all matching folders
def run_parallel(command):

    current_dir = Path.cwd()

    # Check if shared VPC folder exists
    shared_vpc = current_dir / "00-shared-vpc"

    # Find all subdirectories that start with 'openstack_' or 'aws_'
    folders = [
        d for d in current_dir.iterdir()
        if d.is_dir() and (d.name.startswith("openstack_") or d.name.startswith("aws_"))
    ]

    # If no valid folders are found, exit early
    if not folders and not shared_vpc.exists():
        print(f"No folders starting with 'openstack_' or 'aws_' found in {current_dir}")
        return

    # Apply shared VPC first if it exists
    if shared_vpc.exists() and command in ["init", "apply"]:
        print("\n=== Processing Shared VPC First ===")
        print(f"Running terraform {command} in 00-shared-vpc...")

        # Run terraform init first if command is apply
        if command == "apply":
            init_result = subprocess.run(
                ["terraform", "init"],
                cwd=str(shared_vpc.absolute()),
                capture_output=False
            )
            if init_result.returncode != 0:
                print(f"\nERROR: terraform init failed in 00-shared-vpc")
                return

        # Run the actual command
        if command == "init":
            cmd = ["terraform", command]
        else:
            cmd = ["terraform", command, "-auto-approve"]

        result = subprocess.run(
            cmd,
            cwd=str(shared_vpc.absolute()),
            capture_output=False
        )

        if result.returncode != 0:
            print(f"\nERROR: Shared VPC {command} failed! Stopping execution.")
            return

        print(f"\n✓ Shared VPC {command} completed successfully\n")

    # List all matching folders
    if folders:
        print(f"\n=== Processing Instance Folders ===")
        print(f"Found {len(folders)} folder(s) to process:")
        for folder in folders:
            print(f" - {folder.name}")

        # Run commands in parallel using threads
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(lambda f: run_command_safe(f, command), folders))

        # Count how many folders completed successfully
        success = results.count(0)
        print(f"\nSummary: {success}/{len(folders)} instance folder(s) succeeded")

    # Handle destroy command - destroy instances first, then VPC
    if shared_vpc.exists() and command == "destroy":
        print("\n=== Destroying Shared VPC ===")
        result = subprocess.run(
            ["terraform", "destroy", "-auto-approve"],
            cwd=str(shared_vpc.absolute()),
            capture_output=False
        )
        if result.returncode == 0:
            print("\n✓ Shared VPC destroyed successfully")
        else:
            print("\n✗ Failed to destroy shared VPC")

if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage: python run_terraform.py [init|apply|destroy]")
        sys.exit(1)

    # Get the Terraform command from CLI arguments
    command = sys.argv[1]

    # Validate supported commands
    if command not in ["init", "apply", "destroy"]:
        print("Only supports: init, apply, destroy")
        sys.exit(1)

    # Execute command across all folders
    run_parallel(command)
