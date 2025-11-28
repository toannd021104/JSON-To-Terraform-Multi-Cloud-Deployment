#!/usr/bin/env python3
"""
Terraform Config Generator
Generates Terraform configurations from topology.json for AWS/OpenStack
Supports AI-powered auto-fix for validation errors using GPT-4o-mini
"""
import json
import uuid
import sys
import os
import shutil
from datetime import datetime

# Add validators directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'validators'))

from validate_json import validate_topology_file

# AI-powered fixer using OpenAI GPT-4o-mini
try:
    from ai_fixer import fix_topology_with_ai, display_fix_preview, apply_fix, OPENAI_AVAILABLE
    AI_FIXER_AVAILABLE = True
except ImportError:
    AI_FIXER_AVAILABLE = False
    OPENAI_AVAILABLE = False

import terraform_templates as tf_tpl
import subprocess
import cloud_init_processor

# Rich library for colored terminal output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    console = None


class TerraformGenerator:
    """Main class for generating Terraform configurations from topology.json"""

    def __init__(self, provider, num_copies=1):
        """Initialize generator with provider (aws/openstack) and number of copies"""
        self.provider = provider.lower()
        self.num_copies = num_copies
        self.topology = None
        self.validated_resources = None
        self.run()

    def run(self):
        """Main execution flow: validate -> check resources -> generate configs"""
        if RICH_AVAILABLE:
            console.print()
            console.print(Panel.fit(
                f"[bold cyan]Generating Terraform for {self.provider.upper()}[/bold cyan]\n"
                f"[dim]Copies: {self.num_copies}[/dim]",
                border_style="cyan"
            ))
        else:
            print(f"\n=== Start generating files for {self.provider.upper()} ===")

        # Step 1: Load and validate topology.json
        if not self.load_and_validate_topology():
            sys.exit(1)

        # Step 2: Validate cloud resources (images, flavors, etc.)
        self.validate_resources()

        # Step 3: Generate Terraform configs
        self.generate_configs()

        if RICH_AVAILABLE:
            console.print()
            console.print(Panel.fit(
                "[bold green]✓ Generation Complete[/bold green]",
                border_style="green"
            ))
        else:
            print("\n=== COMPLETED ===")

    def load_and_validate_topology(self):
        """Load topology.json and validate against schema + network logic"""
        if RICH_AVAILABLE:
            with console.status("[dim]Validating topology.json...[/dim]", spinner="dots"):
                is_valid, errors = validate_topology_file("topology.json", self.provider)
        else:
            print("\nChecking topology.json...")
            is_valid, errors = validate_topology_file("topology.json", self.provider)

        # Handle validation errors
        if not is_valid:
            if RICH_AVAILABLE:
                console.print("\n[red bold]✗ Validation Failed[/red bold]")
                for error in errors:
                    console.print(f"  [red]•[/red] {error}")
            else:
                print("\n=== VALIDATION ERROR ===")
                for error in errors:
                    print(f"- {error}")

            # Attempt AI auto-fix if available
            if self._try_ai_autofix(errors):
                # Re-validate after AI fix
                if RICH_AVAILABLE:
                    with console.status("[dim]Re-validating topology.json...[/dim]", spinner="dots"):
                        is_valid, errors = validate_topology_file("topology.json", self.provider)
                else:
                    is_valid, errors = validate_topology_file("topology.json", self.provider)

                if is_valid:
                    if RICH_AVAILABLE:
                        console.print("[green]✓[/green] Topology validated after AI fix")
                    else:
                        print("Topology file is valid after AI fix")
                else:
                    # Still has errors after AI fix
                    if RICH_AVAILABLE:
                        console.print("\n[red bold]✗ Still has errors after AI fix[/red bold]")
                        for error in errors:
                            console.print(f"  [red]•[/red] {error}")
                    return False
            else:
                return False

        # Load validated topology into memory
        try:
            with open("topology.json", "r") as f:
                self.topology = json.load(f)
            if RICH_AVAILABLE and is_valid:
                console.print("[green]✓[/green] Topology validated")
            elif not RICH_AVAILABLE and is_valid:
                print("Topology file is valid")
            return True
        except Exception as e:
            if RICH_AVAILABLE:
                console.print(f"[red]✗[/red] Error reading file: {str(e)}")
            else:
                print(f"\nError reading file: {str(e)}")
            return False

    def _try_ai_autofix(self, errors: list) -> bool:
        """
        Attempt to fix topology errors using AI (GPT-4o-mini)
        Shows diff preview and asks for user confirmation before applying
        """
        # Load current topology for AI analysis
        try:
            with open("topology.json", "r") as f:
                current_topology = json.load(f)
        except Exception as e:
            if RICH_AVAILABLE:
                console.print(f"[red]Error reading topology:[/red] {str(e)}")
            return False

        # Check if AI fixer dependencies are available
        if not AI_FIXER_AVAILABLE or not OPENAI_AVAILABLE:
            if RICH_AVAILABLE:
                console.print("\n[dim]AI auto-fix not available (install openai: pip install openai)[/dim]")
            return False

        # Check for OpenAI API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            if RICH_AVAILABLE:
                console.print("\n[dim]AI auto-fix not available (OPENAI_API_KEY not set)[/dim]")
            return False

        # Prompt user for AI fix
        if RICH_AVAILABLE:
            console.print()
            console.print(Panel.fit(
                "[bold yellow]AI Auto-Fix[/bold yellow]\n"
                "[dim]Powered by GPT-4o-mini[/dim]",
                border_style="yellow"
            ))
            try:
                response = input("Do you want AI to fix these errors? [Y/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return False
        else:
            try:
                response = input("\nAI Auto-Fix available. Fix errors? [Y/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return False

        if response and response not in ['y', 'yes', '']:
            return False

        # Call AI to analyze and fix topology
        success, fixed_topology, fixes = fix_topology_with_ai(current_topology, errors, api_key)

        if not success:
            if RICH_AVAILABLE:
                console.print(f"\n[red]AI fix failed:[/red] {fixes[0] if fixes else 'Unknown error'}")
            else:
                print(f"\nAI fix failed: {fixes[0] if fixes else 'Unknown error'}")
            return False

        # Show diff preview of proposed changes
        display_fix_preview(current_topology, fixed_topology, fixes)

        # Confirm before applying
        if RICH_AVAILABLE:
            try:
                confirm = input("\nApply AI fixes? [Y/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return False
        else:
            try:
                confirm = input("Apply AI fixes? [Y/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return False

        if confirm and confirm not in ['y', 'yes', '']:
            if RICH_AVAILABLE:
                console.print("[dim]AI fixes not applied[/dim]")
            return False

        # Apply AI-generated fix to topology.json
        if apply_fix(fixed_topology, "topology.json"):
            if RICH_AVAILABLE:
                console.print("\n[green]✓[/green] AI fixes applied successfully!")
            else:
                print("\nAI fixes applied successfully!")
            return True
        return False

    def validate_resources(self):
        """Validate cloud-specific resources (images, flavors, AMIs, etc.)"""
        if RICH_AVAILABLE:
            with console.status(f"[dim]Validating {self.provider.upper()} resources...[/dim]", spinner="dots"):
                if self.provider == "aws":
                    from validate_aws import AWSUtils
                    self.validated_resources = AWSUtils().validate_resources(self.topology)
                elif self.provider == "openstack":
                    from validate_openstack import validate_resources
                    self.validated_resources = validate_resources(self.topology)
        else:
            if self.provider == "aws":
                from validate_aws import AWSUtils
                self.validated_resources = AWSUtils().validate_resources(self.topology)
            elif self.provider == "openstack":
                from validate_openstack import validate_resources
                self.validated_resources = validate_resources(self.topology)

        # Exit on resource validation failure
        if self.provider == "openstack" and not self.validated_resources.get('valid', False):
            if RICH_AVAILABLE:
                console.print("\n[red bold]✗ Resource Validation Failed[/red bold]")
                for msg in self.validated_resources.get('messages', []):
                    console.print(f"  [red]•[/red] {msg}")
            else:
                print("\n=== RESOURCE VALIDATION FAILED ===")
                for msg in self.validated_resources.get('messages', []):
                    print(f"- {msg}")
            sys.exit(1)

        if RICH_AVAILABLE:
            console.print(f"[green]✓[/green] Resources validated")
            self._display_topology_summary()

    def _display_topology_summary(self):
        """Display topology summary tables (instances, networks, routers)"""
        if not RICH_AVAILABLE or not self.topology:
            return

        # Instances table
        if self.topology.get("instances"):
            console.print()
            table = Table(
                title="[bold]Instances[/bold]",
                show_header=True,
                header_style="bold cyan",
                border_style="dim"
            )
            table.add_column("Name", style="cyan")
            table.add_column("Image")
            table.add_column("CPU", justify="right")
            table.add_column("RAM", justify="right")
            table.add_column("Networks")

            for inst in self.topology["instances"]:
                networks = ", ".join([n["name"] for n in inst.get("networks", [])])
                table.add_row(
                    inst["name"],
                    inst.get("image", "-"),
                    str(inst.get("cpu", "-")),
                    f"{inst.get('ram', '-')}G",
                    networks
                )
            console.print(table)

        # Networks table
        if self.topology.get("networks"):
            console.print()
            table = Table(
                title="[bold]Networks[/bold]",
                show_header=True,
                header_style="bold cyan",
                border_style="dim"
            )
            table.add_column("Name", style="cyan")
            table.add_column("CIDR")
            table.add_column("Gateway")

            for net in self.topology["networks"]:
                table.add_row(
                    net["name"],
                    net.get("cidr", "-"),
                    net.get("gateway_ip", "-")
                )
            console.print(table)

        # Routers table
        if self.topology.get("routers"):
            console.print()
            table = Table(
                title="[bold]Routers[/bold]",
                show_header=True,
                header_style="bold cyan",
                border_style="dim"
            )
            table.add_column("Name", style="cyan")
            table.add_column("External", justify="center")
            table.add_column("Networks")

            for router in self.topology["routers"]:
                networks = ", ".join([f"{n['name']}({n['ip']})" for n in router.get("networks", [])])
                external = "[green]Yes[/green]" if router.get("external") else "[dim]No[/dim]"
                table.add_row(router["name"], external, networks)
            console.print(table)

    def build_validated_map(self, suffix=""):
        """Build map of instance names to validated cloud resources (image, flavor)"""
        validated_map = {}
        if self.validated_resources and 'instances' in self.validated_resources:
            for inst in self.validated_resources['instances']:
                orig_name = inst['original_spec']['name']
                full_name = f"{orig_name}_{suffix}" if suffix else orig_name

                if self.provider == "openstack":
                    validated_map[full_name] = {
                        "image": inst['image'],
                        "flavor": inst['flavor'],
                        "cloud_init": inst.get('cloud_init', None)
                    }
                elif self.provider == "aws":
                    validated_map[full_name] = {
                        "ami": inst['ami'],
                        "instance_type": inst['instance_type']
                    }
        return validated_map

    def generate_config_content(self, validated_map, use_shared_vpc=False):
        """Generate main.tf content based on provider and VPC mode"""
        if self.provider == "aws":
            if use_shared_vpc:
                # Instance-only config (uses remote state for VPC)
                return (
                    tf_tpl.aws_terraform_block() + "\n" +
                    tf_tpl.aws_provider_block() + "\n" +
                    tf_tpl.aws_locals_block() + "\n" +
                    tf_tpl.aws_instance_with_remote_state_block(validated_map)
                )
            else:
                # Full config with VPC creation
                return (
                    tf_tpl.aws_terraform_block() + "\n" +
                    tf_tpl.aws_provider_block() + "\n" +
                    tf_tpl.aws_locals_block() + "\n" +
                    tf_tpl.aws_network_module_block() + "\n" +
                    tf_tpl.aws_security_group_block() + "\n" +
                    tf_tpl.aws_instance_module_block(validated_map) + "\n" +
                    tf_tpl.aws_bastion_block()
                )
        elif self.provider == "openstack":
            return (
                tf_tpl.os_terraform_block() + "\n" +
                tf_tpl.os_provider_block() + "\n" +
                tf_tpl.os_locals_block() + "\n" +
                tf_tpl.os_network_module_block() + "\n" +
                tf_tpl.os_instance_module_block(validated_map)
            )

    def collect_all_networks_and_routers(self, original_topology, suffixes):
        """Collect networks/routers from all copies with unique suffixes"""
        all_networks = []
        all_routers = []

        for suffix in suffixes:
            # Clone networks with suffix
            for net in original_topology.get('networks', []):
                modified_net = net.copy()
                modified_net['name'] = f"{net['name']}_{suffix}"
                all_networks.append(modified_net)

            # Clone routers with suffix and update network references
            for router in original_topology.get('routers', []):
                modified_router = router.copy()
                modified_router['name'] = f"{router['name']}_{suffix}"
                modified_router['networks'] = [
                    {**net_ref, 'name': f"{net_ref['name']}_{suffix}"}
                    for net_ref in router.get('networks', [])
                ]
                all_routers.append(modified_router)

        return all_networks, all_routers

    def create_shared_vpc_folder(self, main_folder, original_topology, suffixes):
        """Create shared VPC folder with all networks for AWS multi-copy deployment"""
        shared_vpc_path = os.path.join(main_folder, "00-shared-vpc")
        os.makedirs(shared_vpc_path, exist_ok=True)

        if RICH_AVAILABLE:
            console.print(f"\n[cyan]Creating shared VPC folder...[/cyan]")
        else:
            print(f"\n Creating shared VPC folder: {shared_vpc_path}")

        # Collect all networks/routers from all copies
        all_networks, all_routers = self.collect_all_networks_and_routers(original_topology, suffixes)

        # Generate main.tf with all shared resources
        main_tf_content = (
            tf_tpl.aws_shared_vpc_terraform_block() + "\n" +
            tf_tpl.aws_shared_vpc_provider_block() + "\n" +
            tf_tpl.aws_shared_vpc_locals_block(all_networks, all_routers) + "\n" +
            tf_tpl.aws_shared_vpc_network_module_block() + "\n" +
            tf_tpl.aws_shared_vpc_security_group_block() + "\n" +
            tf_tpl.aws_shared_vpc_bastion_block() + "\n" +
            tf_tpl.aws_shared_vpc_outputs_block()
        )

        with open(os.path.join(shared_vpc_path, 'main.tf'), 'w', encoding='utf-8') as f:
            f.write(main_tf_content)

        # Generate variables.tf
        variables_content = tf_tpl.aws_shared_vpc_variables_block()
        with open(os.path.join(shared_vpc_path, 'variables.tf'), 'w', encoding='utf-8') as f:
            f.write(variables_content)

        if RICH_AVAILABLE:
            console.print(f"[green]✓[/green] Shared VPC: {len(all_networks)} subnets for {self.num_copies} copies")
        else:
            print(f" Shared VPC folder created with {len(all_networks)} subnets for {self.num_copies} copies")
        return all_networks, all_routers

    def generate_configs(self):
        """Generate Terraform project folders and run terraform apply"""
        with open('topology.json', 'r') as f:
            original_topology = json.load(f)

        # Create timestamped project folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        main_folder = os.path.join("../terraform-projects", f"{self.provider}_{timestamp}")
        os.makedirs(main_folder, exist_ok=True)

        # Copy terraform runner script
        if os.path.exists("run_terraform.py"):
            shutil.copy("run_terraform.py", os.path.join(main_folder, "run_terraform.py"))

        # Generate unique suffixes for each copy
        suffixes = [str(uuid.uuid4())[:6] for _ in range(self.num_copies)]

        # Create shared VPC for AWS (all copies share one VPC)
        use_shared_vpc = False
        if self.provider == "aws":
            self.create_shared_vpc_folder(main_folder, original_topology, suffixes)
            use_shared_vpc = True

        # Create individual instance folders
        if RICH_AVAILABLE:
            console.print(f"\n[cyan]Creating {len(suffixes)} instance folder(s)...[/cyan]")

        for suffix in suffixes:
            dir_name = f"{self.provider}_{suffix}"
            full_path = os.path.join(main_folder, dir_name)
            self.create_provider_directory(full_path, original_topology, suffix, use_shared_vpc)

        # Execute terraform apply
        if RICH_AVAILABLE:
            console.print(f"\n[cyan]Running Terraform...[/cyan]")

        subprocess.run(
            ["python3", "run_terraform.py", "apply"],
            cwd=main_folder,
            check=True
        )

    def create_provider_directory(self, dir_path, original_topology, suffix, use_shared_vpc=False):
        """Create a single Terraform folder with modified topology"""
        try:
            # Copy provider template folder
            shutil.copytree(self.provider, dir_path)

            # Modify topology with unique suffix
            modified_topology = self.modify_topology(original_topology, suffix)
            with open(os.path.join(dir_path, 'topology.json'), 'w') as f:
                json.dump(modified_topology, f, indent=2)

            # Process cloud-init JSON -> YAML
            self.process_cloud_init_configs(dir_path)

            # Generate main.tf with validated resources
            validated_map = self.build_validated_map(suffix)
            config_content = self.generate_config_content(validated_map, use_shared_vpc)
            with open(os.path.join(dir_path, 'main.tf'), 'w', encoding='utf-8') as f:
                f.write(config_content)

            folder_name = os.path.basename(dir_path)
            if RICH_AVAILABLE:
                console.print(f"  [green]✓[/green] {folder_name}")
            else:
                print(f" Successfully created: {dir_path}")
        except Exception as e:
            folder_name = os.path.basename(dir_path)
            if RICH_AVAILABLE:
                console.print(f"  [red]✗[/red] {folder_name}: {str(e)}")
            else:
                print(f" Error creating {dir_path}: {str(e)}")
            # Cleanup on failure
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)

    def process_cloud_init_configs(self, dir_path):
        """Convert cloud-init JSON to YAML and attach to instances"""
        try:
            topology_path = os.path.join(dir_path, 'topology.json')
            with open(topology_path, 'r') as f:
                topology = json.load(f)

            # Process all instances, returns {instance_name: yaml_filename}
            cloud_init_map = cloud_init_processor.process_all_instances(
                topology,
                self.validated_resources,
                dir_path
            )

            # Update topology to reference YAML files
            if cloud_init_map:
                for instance in topology.get('instances', []):
                    if instance['name'] in cloud_init_map:
                        instance['cloud_init'] = cloud_init_map[instance['name']]

                with open(topology_path, 'w') as f:
                    json.dump(topology, f, indent=2)

        except Exception as e:
            print(f"  Warning: Could not process cloud-init configs: {e}")

    def modify_topology(self, topology, suffix):
        """Add unique suffix to all resource names in topology"""
        modified = json.loads(json.dumps(topology))  # Deep copy

        # Add suffix to instance names and their network references
        for inst in modified.get('instances', []):
            inst['name'] = f"{inst['name']}_{suffix}"
            for net in inst.get('networks', []):
                net['name'] = f"{net['name']}_{suffix}"

        # Add suffix to network names
        for net in modified.get('networks', []):
            net['name'] = f"{net['name']}_{suffix}"

        # Add suffix to router names and their network references
        for router in modified.get('routers', []):
            router['name'] = f"{router['name']}_{suffix}"
            for net in router.get('networks', []):
                net['name'] = f"{net['name']}_{suffix}"

        return modified


# =============================================================================
# Entry Point
# =============================================================================
if __name__ == "__main__":
    # Display header
    if RICH_AVAILABLE:
        console.print()
        console.print(Panel.fit(
            "[bold blue]Terraform Config Generator[/bold blue]\n"
            "[dim]Multi-Cloud Deployment Tool[/dim]",
            border_style="blue"
        ))
    else:
        print("""
========================
TERRAFORM CONFIG GENERATOR
========================""")

    # Validate command-line arguments
    if len(sys.argv) < 2 or sys.argv[1].lower() not in ["aws", "openstack"]:
        if RICH_AVAILABLE:
            console.print("\n[red]Error:[/red] Invalid usage")
            console.print("[dim]Usage: python3 generate.py [aws|openstack] [num_copies][/dim]")
        else:
            print("\n[ERROR] Usage: python3 generate.py [aws|openstack] [num_copies]")
        sys.exit(1)

    provider = sys.argv[1].lower()
    num_copies = 1

    # Parse optional num_copies argument
    if len(sys.argv) > 2:
        try:
            num_copies = int(sys.argv[2])
            if num_copies < 1:
                raise ValueError
        except ValueError:
            if RICH_AVAILABLE:
                console.print("[red]Error:[/red] Number of copies must be a positive integer")
            else:
                print("\n[ERROR] Number of copies must be a positive integer")
            sys.exit(1)

    # Run generator
    try:
        TerraformGenerator(provider, num_copies)
    except KeyboardInterrupt:
        if RICH_AVAILABLE:
            console.print("\n[yellow]Interrupted[/yellow]")
        else:
            print("\n=== PROGRAM TERMINATED ===")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"\n[red bold]Error:[/red bold] {str(e)}")
        else:
            print(f"\n=== UNEXPECTED ERROR ===\n{str(e)}")
        sys.exit(1)
