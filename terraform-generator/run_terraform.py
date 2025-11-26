import os
import sys
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Rich library for beautiful CLI output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.live import Live
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    console = None

# Run a Terraform command inside a specific folder (thread-safe version)
def run_command_safe(folder, command):
    try:
        if not RICH_AVAILABLE:
            print(f"\nProcessing {folder.name}...")

        # Use subprocess with cwd instead of os.chdir to avoid race condition
        # For apply/destroy make sure the folder is initialized first
        if command == "init":
            cmd = ["terraform", "init"]
            result = subprocess.run(cmd, cwd=str(folder.absolute()), capture_output=True, text=True)
            exit_code = result.returncode
            if exit_code != 0 and not RICH_AVAILABLE:
                print(f"Error: terraform init failed in {folder.name}")
            return exit_code

        # For commands that modify state, ensure modules/providers are installed first
        if command in ("apply", "destroy"):
            if not RICH_AVAILABLE:
                print(f"Running 'terraform init' in {folder.name} before '{command}'...")
            init_result = subprocess.run(["terraform", "init"], cwd=str(folder.absolute()), capture_output=True, text=True)
            if init_result.returncode != 0:
                if not RICH_AVAILABLE:
                    print(f"Error: terraform init failed in {folder.name}; skipping {command}.")
                return init_result.returncode

        # Run the actual command (apply/destroy) with auto-approve where appropriate
        if command in ("apply", "destroy"):
            cmd = ["terraform", command, "-auto-approve"]
        else:
            cmd = ["terraform", command]

        result = subprocess.run(
            cmd,
            cwd=str(folder.absolute()),
            capture_output=True,
            text=True
        )

        exit_code = result.returncode

        # Print error message if command failed
        if exit_code != 0 and not RICH_AVAILABLE:
            print(f"Error in {folder.name}")

        return exit_code

    except Exception as e:
        if not RICH_AVAILABLE:
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
        if RICH_AVAILABLE:
            console.print("[yellow]No terraform folders found[/yellow]")
        else:
            print(f"No folders starting with 'openstack_' or 'aws_' found in {current_dir}")
        return

    # Display header
    if RICH_AVAILABLE:
        console.print()
        console.print(Panel.fit(
            f"[bold cyan]Terraform {command.upper()}[/bold cyan]",
            border_style="cyan"
        ))

    # Apply shared VPC first if it exists
    if shared_vpc.exists() and command in ["init", "apply"]:
        if RICH_AVAILABLE:
            console.print(f"\n[cyan]Processing Shared VPC...[/cyan]")
        else:
            print("\n=== Processing Shared VPC First ===")
            print(f"Running terraform {command} in 00-shared-vpc...")

        # Run terraform init first if command is apply
        if command == "apply":
            if RICH_AVAILABLE:
                with console.status("[dim]Running terraform init...[/dim]", spinner="dots"):
                    init_result = subprocess.run(
                        ["terraform", "init"],
                        cwd=str(shared_vpc.absolute()),
                        capture_output=True
                    )
            else:
                init_result = subprocess.run(
                    ["terraform", "init"],
                    cwd=str(shared_vpc.absolute()),
                    capture_output=False
                )
            if init_result.returncode != 0:
                if RICH_AVAILABLE:
                    console.print("[red]✗[/red] terraform init failed in 00-shared-vpc")
                else:
                    print(f"\nERROR: terraform init failed in 00-shared-vpc")
                return

        # Run the actual command
        if command == "init":
            cmd = ["terraform", command]
        else:
            cmd = ["terraform", command, "-auto-approve"]

        if RICH_AVAILABLE:
            with console.status(f"[dim]Running terraform {command}...[/dim]", spinner="dots"):
                result = subprocess.run(
                    cmd,
                    cwd=str(shared_vpc.absolute()),
                    capture_output=True
                )
        else:
            result = subprocess.run(
                cmd,
                cwd=str(shared_vpc.absolute()),
                capture_output=False
            )

        if result.returncode != 0:
            if RICH_AVAILABLE:
                console.print(f"[red]✗[/red] Shared VPC {command} failed")
            else:
                print(f"\nERROR: Shared VPC {command} failed! Stopping execution.")
            return

        if RICH_AVAILABLE:
            console.print(f"[green]✓[/green] Shared VPC {command} completed")
        else:
            print(f"\n✓ Shared VPC {command} completed successfully\n")

    # List all matching folders
    if folders:
        if RICH_AVAILABLE:
            console.print(f"\n[cyan]Processing {len(folders)} instance folder(s)...[/cyan]")

            # Create results table
            results_data = {}
            for folder in folders:
                results_data[folder.name] = "pending"

            # Run commands in parallel and track progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                console=console
            ) as progress:
                task = progress.add_task(f"[cyan]terraform {command}", total=len(folders))

                with ThreadPoolExecutor() as executor:
                    futures = {executor.submit(run_command_safe, f, command): f for f in folders}
                    results = []
                    for future in futures:
                        result = future.result()
                        folder = futures[future]
                        results.append(result)
                        results_data[folder.name] = "success" if result == 0 else "failed"
                        progress.advance(task)

            # Display results table
            console.print()
            table = Table(title="[bold]Results[/bold]", border_style="dim")
            table.add_column("Folder", style="cyan")
            table.add_column("Status", justify="center")

            for folder_name, status in results_data.items():
                if status == "success":
                    table.add_row(folder_name, "[green]✓ Success[/green]")
                else:
                    table.add_row(folder_name, "[red]✗ Failed[/red]")
            console.print(table)

            # Summary
            success = results.count(0)
            if success == len(folders):
                console.print(f"\n[green bold]✓ All {len(folders)} folder(s) succeeded[/green bold]")
            else:
                console.print(f"\n[yellow]{success}/{len(folders)} folder(s) succeeded[/yellow]")
        else:
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
        if RICH_AVAILABLE:
            console.print(f"\n[cyan]Destroying Shared VPC...[/cyan]")
            with console.status("[dim]Running terraform destroy...[/dim]", spinner="dots"):
                result = subprocess.run(
                    ["terraform", "destroy", "-auto-approve"],
                    cwd=str(shared_vpc.absolute()),
                    capture_output=True
                )
            if result.returncode == 0:
                console.print("[green]✓[/green] Shared VPC destroyed")
            else:
                console.print("[red]✗[/red] Failed to destroy shared VPC")
        else:
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
        if RICH_AVAILABLE:
            console.print("[red]Error:[/red] Invalid usage")
            console.print("[dim]Usage: python run_terraform.py [init|apply|destroy][/dim]")
        else:
            print("Usage: python run_terraform.py [init|apply|destroy]")
        sys.exit(1)

    # Get the Terraform command from CLI arguments
    command = sys.argv[1]

    # Validate supported commands
    if command not in ["init", "apply", "destroy"]:
        if RICH_AVAILABLE:
            console.print("[red]Error:[/red] Unsupported command")
            console.print("[dim]Supported: init, apply, destroy[/dim]")
        else:
            print("Only supports: init, apply, destroy")
        sys.exit(1)

    # Execute command across all folders
    run_parallel(command)
