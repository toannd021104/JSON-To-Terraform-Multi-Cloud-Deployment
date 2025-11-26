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

# Store error messages for display after parallel execution
error_messages = {}
# Store success summaries (resources added/changed/destroyed)
success_summaries = {}

import re

def parse_terraform_summary(output):
    """Parse terraform output to extract resource summary"""
    summary = {"added": 0, "changed": 0, "destroyed": 0}

    # Match patterns like "Apply complete! Resources: 5 added, 0 changed, 0 destroyed."
    # Or "Destroy complete! Resources: 3 destroyed."
    match = re.search(r'(\d+)\s+added', output)
    if match:
        summary["added"] = int(match.group(1))

    match = re.search(r'(\d+)\s+changed', output)
    if match:
        summary["changed"] = int(match.group(1))

    match = re.search(r'(\d+)\s+destroyed', output)
    if match:
        summary["destroyed"] = int(match.group(1))

    return summary

# Store live logs for display
live_logs = {}

# Run a Terraform command inside a specific folder (thread-safe version)
def run_command_safe(folder, command):
    global error_messages, success_summaries, live_logs
    try:
        if not RICH_AVAILABLE:
            print(f"\nProcessing {folder.name}...")

        # Use subprocess with cwd instead of os.chdir to avoid race condition
        # For apply/destroy make sure the folder is initialized first
        if command == "init":
            cmd = ["terraform", "init"]
            result = subprocess.run(cmd, cwd=str(folder.absolute()), capture_output=True, text=True)
            exit_code = result.returncode
            if exit_code != 0:
                error_messages[folder.name] = result.stderr or result.stdout
                if not RICH_AVAILABLE:
                    print(f"Error: terraform init failed in {folder.name}")
            return exit_code

        # For commands that modify state, ensure modules/providers are installed first
        if command in ("apply", "destroy"):
            if not RICH_AVAILABLE:
                print(f"Running 'terraform init' in {folder.name} before '{command}'...")
            init_result = subprocess.run(["terraform", "init"], cwd=str(folder.absolute()), capture_output=True, text=True)
            if init_result.returncode != 0:
                error_messages[folder.name] = init_result.stderr or init_result.stdout
                if not RICH_AVAILABLE:
                    print(f"Error: terraform init failed in {folder.name}; skipping {command}.")
                return init_result.returncode

        # Run the actual command (apply/destroy) with auto-approve where appropriate
        if command in ("apply", "destroy"):
            cmd = ["terraform", command, "-auto-approve"]
        else:
            cmd = ["terraform", command]

        # Stream output in real-time
        full_output = []
        process = subprocess.Popen(
            cmd,
            cwd=str(folder.absolute()),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Read output line by line
        for line in process.stdout:
            line = line.rstrip()
            full_output.append(line)
            # Store latest lines for live display
            live_logs[folder.name] = full_output[-3:]  # Keep last 3 lines

        process.wait()
        exit_code = process.returncode
        output_text = "\n".join(full_output)

        # Store error message if command failed
        if exit_code != 0:
            error_messages[folder.name] = output_text
            if not RICH_AVAILABLE:
                print(f"Error in {folder.name}")
        else:
            # Parse and store success summary
            success_summaries[folder.name] = parse_terraform_summary(output_text)

        # Clear live log
        live_logs.pop(folder.name, None)

        return exit_code

    except Exception as e:
        error_messages[folder.name] = str(e)
        if not RICH_AVAILABLE:
            print(f"Error processing {folder}: {str(e)}")
        return 1

# Legacy function for backwards compatibility
def run_command(folder, command):
    return run_command_safe(folder, command)

# Run the command in parallel for all matching folders
def run_parallel(command):
    global error_messages, success_summaries, live_logs
    error_messages = {}  # Clear previous errors
    success_summaries = {}  # Clear previous summaries
    live_logs = {}  # Clear live logs

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
                        capture_output=True,
                        text=True
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
                    console.print(f"\n[red]Error:[/red]\n{init_result.stderr or init_result.stdout}")
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
                    capture_output=True,
                    text=True
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
                error_output = result.stderr or result.stdout
                if error_output:
                    console.print(f"\n[red]Error:[/red]")
                    for line in error_output.strip().split('\n')[-20:]:
                        if "Error" in line or "error" in line:
                            console.print(f"[red]{line}[/red]")
                        else:
                            console.print(f"[dim]{line}[/dim]")
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

            # Import for live display
            from rich.layout import Layout
            from rich.text import Text
            import time
            import threading

            # Run commands in parallel with live log display
            results = []
            completed = [0]  # Use list to allow modification in nested function

            def build_live_display():
                """Build the live display with progress and logs"""
                lines = []
                # Progress line
                lines.append(f"[cyan]terraform {command}[/cyan] {completed[0]}/{len(folders)}")
                lines.append("")

                # Show live logs for each running folder
                for folder_name, log_lines in list(live_logs.items()):
                    lines.append(f"[yellow]► {folder_name}[/yellow]")
                    for log_line in log_lines:
                        # Truncate long lines
                        if len(log_line) > 80:
                            log_line = log_line[:77] + "..."
                        lines.append(f"  [dim]{log_line}[/dim]")
                    lines.append("")

                return "\n".join(lines) if lines else "[dim]Starting...[/dim]"

            with Live(build_live_display(), console=console, refresh_per_second=4) as live:
                with ThreadPoolExecutor() as executor:
                    futures = {executor.submit(run_command_safe, f, command): f for f in folders}

                    while futures:
                        # Update display
                        live.update(build_live_display())

                        # Check for completed futures
                        done_futures = [f for f in futures if f.done()]
                        for future in done_futures:
                            folder = futures.pop(future)
                            result = future.result()
                            results.append(result)
                            results_data[folder.name] = "success" if result == 0 else "failed"
                            completed[0] += 1
                            live.update(build_live_display())

                        if futures:
                            time.sleep(0.1)

            # Display results table
            console.print()
            table = Table(title="[bold]Results[/bold]", border_style="dim")
            table.add_column("Folder", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Added", justify="right", style="green")
            table.add_column("Changed", justify="right", style="yellow")
            table.add_column("Destroyed", justify="right", style="red")

            for folder_name, status in results_data.items():
                if status == "success":
                    summary = success_summaries.get(folder_name, {})
                    table.add_row(
                        folder_name,
                        "[green]✓ Success[/green]",
                        str(summary.get("added", 0)),
                        str(summary.get("changed", 0)),
                        str(summary.get("destroyed", 0))
                    )
                else:
                    table.add_row(folder_name, "[red]✗ Failed[/red]", "-", "-", "-")
            console.print(table)

            # Summary
            success = results.count(0)

            # Calculate totals
            total_added = sum(s.get("added", 0) for s in success_summaries.values())
            total_changed = sum(s.get("changed", 0) for s in success_summaries.values())
            total_destroyed = sum(s.get("destroyed", 0) for s in success_summaries.values())

            if success == len(folders):
                console.print(f"\n[green bold]✓ All {len(folders)} folder(s) succeeded[/green bold]")
            else:
                console.print(f"\n[yellow]{success}/{len(folders)} folder(s) succeeded[/yellow]")

            # Show total resources
            if total_added or total_changed or total_destroyed:
                console.print(f"[dim]Total: [green]{total_added} added[/green], [yellow]{total_changed} changed[/yellow], [red]{total_destroyed} destroyed[/red][/dim]")

            # Display error messages for failed folders
            if error_messages:
                console.print("\n[red bold]Error Details:[/red bold]")
                for folder_name, error_msg in error_messages.items():
                    console.print(f"\n[cyan]── {folder_name} ──[/cyan]")
                    # Show last 30 lines of error to avoid flooding
                    error_lines = error_msg.strip().split('\n')
                    if len(error_lines) > 30:
                        console.print("[dim]... (truncated, showing last 30 lines)[/dim]")
                        error_lines = error_lines[-30:]
                    for line in error_lines:
                        if "Error" in line or "error" in line:
                            console.print(f"[red]{line}[/red]")
                        else:
                            console.print(f"[dim]{line}[/dim]")
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
                    capture_output=True,
                    text=True
                )
            if result.returncode == 0:
                console.print("[green]✓[/green] Shared VPC destroyed")
            else:
                console.print("[red]✗[/red] Failed to destroy shared VPC")
                error_output = result.stderr or result.stdout
                if error_output:
                    console.print(f"\n[red]Error:[/red]")
                    for line in error_output.strip().split('\n')[-20:]:
                        if "Error" in line or "error" in line:
                            console.print(f"[red]{line}[/red]")
                        else:
                            console.print(f"[dim]{line}[/dim]")
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
