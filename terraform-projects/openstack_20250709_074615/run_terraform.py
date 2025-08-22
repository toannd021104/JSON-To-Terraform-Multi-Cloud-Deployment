import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Run a Terraform command inside a specific folder
def run_command(folder, command):
    try:
        print(f"\nProcessing {folder.name}...")

        # Change directory to the Terraform module folder
        os.chdir(str(folder.absolute()))

        # Run the terraform command
        if command == "init":
            exit_code = os.system(f"terraform {command}")
        else:
            exit_code = os.system(f"terraform {command} -auto-approve")

        # Print error message if command failed
        if exit_code != 0:
            print(f"Error in {folder.name}")

        return exit_code

    except Exception as e:
        print(f"Error processing {folder}: {str(e)}")
        return 1

# Run the command in parallel for all matching folders
def run_parallel(command):

    current_dir = Path.cwd()

    # Find all subdirectories that start with 'openstack_' or 'aws_'
    folders = [
        d for d in current_dir.iterdir()
        if d.is_dir() and (d.name.startswith("openstack_") or d.name.startswith("aws_"))
    ]

    # If no valid folders are found, exit early
    if not folders:
        print(f"No folders starting with 'openstack_' or 'aws_' found in {current_dir}")
        return

    # List all matching folders
    print(f"Found {len(folders)} folder(s) to process:")
    for folder in folders:
        print(f" - {folder.name}")

    # Run commands in parallel using threads
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(lambda f: run_command(f, command), folders))

    # Count how many folders completed successfully
    success = results.count(0)
    print(f"\nSummary: {success}/{len(folders)} succeeded")

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
