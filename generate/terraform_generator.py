#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
TERRAFORM CONFIG GENERATOR - Multi-Cloud Deployment Tool
═══════════════════════════════════════════════════════════════════════════════

CHỨC NĂNG:
- Generate Terraform configurations từ topology.json cho AWS/OpenStack
- Hỗ trợ AI-powered auto-fix validation errors (Gemini)
- Hỗ trợ multi-copy deployment (tạo nhiều bản sao infrastructure)

THỨ TỰ THỰC THI:
1. __init__()        : Khởi tạo với provider (aws/openstack) và số copies
2. run()             : Flow chính
   ├─ load_openstack_config()        : Load config cho OpenStack (nếu dùng)
   ├─ load_and_validate_topology()   : Validate topology.json
   ├─ validate_resources()           : Validate cloud resources (AMI, flavors, etc.)
   └─ generate_configs()             : Generate Terraform files + terraform apply

DEPENDENCIES:
- topology_schema      : JSON schema validation
- topology_ai_fixer    : Gemini AI auto-fix (single AI)
- topology_ai_cross_check: OpenAI + Gemini cross-check (dual AI)
- terraform_templates  : Generate Terraform HCL code
- cloudinit_processor  : Process cloud-init user-data
═══════════════════════════════════════════════════════════════════════════════
"""
import json
import uuid
import sys
import os
import shutil
from datetime import datetime

# Thêm root vào sys.path để import theo cấu trúc module mới
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
PROVIDERS_DIR = os.path.join(ROOT_DIR, "providers")
sys.path.insert(0, ROOT_DIR)

from validate.topology_schema import validate_topology_file

# OpenStack config manager
try:
    from configs.openstack_config_manager import OpenStackConfigManager
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False

# AI-powered fixer using Gemini (single AI)
try:
    from validate.topology_ai_fixer import fix_topology_with_ai, display_fix_preview, apply_fix, GEMINI_AVAILABLE
    AI_FIXER_AVAILABLE = True
except ImportError:
    AI_FIXER_AVAILABLE = False
    GEMINI_AVAILABLE = False

# Dual-AI cross-checker (OpenAI + Gemini)
try:
    from validate.topology_ai_cross_check import fix_with_openai, review_with_gemini, render_diff, load_topology, save_topology
    DUAL_AI_AVAILABLE = True
except ImportError:
    DUAL_AI_AVAILABLE = False

from generate import terraform_templates as tf_tpl
# Các helper nhân bản topology được tách sang module clone
from clone.topology_cloner import (
    calculate_vpc_cidr,
    collect_all_networks_and_routers,
    modify_topology,
)
import subprocess
from generate import cloudinit_processor as cloud_init_processor

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
        self.openstack_config = None
        self.discovered_resources = None
        self.validated_resources = None
        self.run()

    def run(self):
        """
        ═══════════════════════════════════════════════════════════════════════
        MAIN EXECUTION FLOW - Thứ tự thực thi chính
        ═══════════════════════════════════════════════════════════════════════
        
        STEP 0: Load OpenStack config (chỉ cho provider=openstack)
                - Load credentials, endpoints từ openstack_config.json
                - Auto-discover external networks, availability zones
        
        STEP 1: Load & Validate Topology
                - Đọc topology.json
                - Validate JSON schema (instances, networks, routers)
                - Validate network logic (CIDR conflicts, IP assignments)
                - Nếu có lỗi → Offer AI auto-fix (Gemini hoặc OpenAI+Gemini)
        
        STEP 2: Validate Cloud Resources
                - AWS: Validate AMIs, instance types theo region
                - OpenStack: Validate images, flavors theo cloud
        
        STEP 3: Generate Terraform Configs
                - AWS: Tạo shared VPC + instance folders
                - OpenStack: Tạo per-instance folders
                - Process cloud-init user-data
                - Run terraform init + apply
        ═══════════════════════════════════════════════════════════════════════
        """
        if RICH_AVAILABLE:
            console.print()
            console.print(Panel.fit(
                f"[bold cyan]Generating Terraform for {self.provider.upper()}[/bold cyan]\n"
                f"[dim]Copies: {self.num_copies}[/dim]",
                border_style="cyan"
            ))
        else:
            print(f"\n=== Start generating files for {self.provider.upper()} ===")

        # Step 0: Load OpenStack configuration if using OpenStack provider
        if self.provider == 'openstack':
            if not self.load_openstack_config():
                if RICH_AVAILABLE:
                    console.print("[yellow]! No OpenStack config found, using defaults[/yellow]")
                else:
                    print("! No OpenStack config found, using defaults")

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

    def load_openstack_config(self):
        """
        ═══════════════════════════════════════════════════════════════════════
        LOAD OPENSTACK CONFIGURATION (Chỉ cho provider=openstack)
        ═══════════════════════════════════════════════════════════════════════
        
        CHỨC NĂNG:
        - Load credentials từ openstack_config.json (auth_url, username, password, project)
        - Get active profile (default hoặc chỉ định)
        - Auto-discover resources từ OpenStack cloud:
          + External networks (cho floating IPs)
          + Availability zones
          + Quotas
        
        RETURN:
        - True: Thành công load config
        - False: Không tìm thấy config (sẽ dùng defaults)
        ═══════════════════════════════════════════════════════════════════════
        """
        if not CONFIG_MANAGER_AVAILABLE:
            return False
        
        try:
            manager = OpenStackConfigManager()
            config = manager.load_config()
            
            if not config:
                # No config file, try to create from environment or use defaults
                if RICH_AVAILABLE:
                    console.print("[dim]No config file found, checking environment...[/dim]")
                return False
            
            profile = manager.get_active_profile()
            if not profile:
                if RICH_AVAILABLE:
                    console.print("[yellow]! No active profile found[/yellow]")
                return False
            
            self.openstack_config = profile
            
            # Auto-discover resources
            if RICH_AVAILABLE:
                with console.status("[dim]Discovering OpenStack resources...[/dim]", spinner="dots"):
                    self.discovered_resources = manager.discover_resources()
            else:
                self.discovered_resources = manager.discover_resources()
            
            if self.discovered_resources:
                if RICH_AVAILABLE:
                    console.print("[green]✓[/green] OpenStack config loaded")
                    if 'external_network' in self.discovered_resources:
                        ext_net = self.discovered_resources['external_network']
                        console.print(f"  External network: [cyan]{ext_net['name']}[/cyan]")
                else:
                    print("OpenStack config loaded")
            
            return True
            
        except Exception as e:
            if RICH_AVAILABLE:
                console.print(f"[yellow]! Error loading config: {e}[/yellow]")
            return False

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
        Attempt to fix topology errors using Dual-AI (OpenAI fix + Gemini review)
        Requires BOTH to pass before applying changes
        Falls back to single-AI (Gemini) if OpenAI not available
        """
        # Load current topology for AI analysis
        try:
            with open("topology.json", "r") as f:
                current_topology = json.load(f)
        except Exception as e:
            if RICH_AVAILABLE:
                console.print(f"[red]Error reading topology:[/red] {str(e)}")
            return False

        # Check for API keys
        openai_key = os.getenv("OPENAI_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")
        
        # Try Dual-AI mode first (OpenAI + Gemini cross-check)
        if DUAL_AI_AVAILABLE and openai_key and gemini_key:
            return self._dual_ai_fix(current_topology, errors)
        
        # Fall back to single-AI mode (Gemini only)
        if AI_FIXER_AVAILABLE and GEMINI_AVAILABLE and gemini_key:
            return self._single_ai_fix(current_topology, errors, gemini_key)
        
        # No AI available
        if RICH_AVAILABLE:
            console.print("\n[dim]AI auto-fix not available[/dim]")
            console.print("[dim]Set OPENAI_API_KEY + GEMINI_API_KEY for Dual-AI mode[/dim]")
            console.print("[dim]Or set GEMINI_API_KEY for Single-AI mode[/dim]")
        return False

    def _dual_ai_fix(self, current_topology: dict, errors: list) -> bool:
        """
        Dual-AI fix: OpenAI proposes fix, Gemini reviews
        Only applies if BOTH pass
        """
        if RICH_AVAILABLE:
            console.print()
            console.print(Panel.fit(
                "[bold yellow]Dual-AI Auto-Fix[/bold yellow]\n"
                "[dim]OpenAI (fix) + Gemini (review)[/dim]",
                border_style="yellow"
            ))
        
        # Step 1: OpenAI fix
        if RICH_AVAILABLE:
            console.print("\n[cyan]Step 1/3:[/cyan] Requesting OpenAI fix...")
        
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        success, fixed_topology, fix_errors = fix_with_openai(current_topology, errors, openai_model)
        
        if not success:
            if RICH_AVAILABLE:
                console.print(f"[red]✗ OpenAI fix failed:[/red] {fix_errors[0] if fix_errors else 'Unknown error'}")
            return False
        
        if RICH_AVAILABLE:
            console.print("[green]✓[/green] OpenAI proposed a fix")
        
        # Show diff
        from rich.syntax import Syntax
        diff_text = render_diff(current_topology, fixed_topology)
        if diff_text and RICH_AVAILABLE:
            console.print(Panel.fit(Syntax(diff_text, "diff", theme="ansi_dark"), title="Proposed Changes", border_style="yellow"))
        
        # Step 2: Re-validate
        if RICH_AVAILABLE:
            console.print("\n[cyan]Step 2/3:[/cyan] Re-validating fixed topology...")
        
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(fixed_topology, tmp)
            tmp_path = tmp.name
        
        post_valid, post_errors = validate_topology_file(tmp_path, self.provider)
        os.unlink(tmp_path)
        
        if post_valid:
            if RICH_AVAILABLE:
                console.print("[green]✓[/green] Re-validation passed")
        else:
            if RICH_AVAILABLE:
                console.print("[yellow]![/yellow] Re-validation has warnings:")
                for err in post_errors[:3]:
                    console.print(f"  [dim]• {err}[/dim]")
        
        # Step 3: Gemini review
        if RICH_AVAILABLE:
            console.print("\n[cyan]Step 3/3:[/cyan] Requesting Gemini review...")
        
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        review_ok, review, review_errors = review_with_gemini(fixed_topology, errors, post_errors, gemini_model)
        
        gemini_approved = False
        if review_ok:
            gemini_status = review.get("status", "").lower()
            gemini_approved = gemini_status in ["pass", "warn"]
            
            if RICH_AVAILABLE:
                status_color = "green" if gemini_status == "pass" else ("yellow" if gemini_status == "warn" else "red")
                console.print(f"[{status_color}]Gemini status: {gemini_status.upper()}[/{status_color}]")
                
                if review.get("critical"):
                    console.print("[red]Critical issues:[/red]")
                    for c in review["critical"]:
                        console.print(f"  • {c}")
                if review.get("warnings"):
                    console.print("[yellow]Warnings:[/yellow]")
                    for w in review["warnings"][:3]:
                        console.print(f"  • {w}")
        else:
            if RICH_AVAILABLE:
                console.print(f"[red]✗ Gemini review failed:[/red] {review_errors[0] if review_errors else 'Unknown'}")
        
        # Dual-AI approval check
        dual_approved = post_valid and gemini_approved
        
        if RICH_AVAILABLE:
            console.print()
            console.print("─" * 40)
            console.print("[bold]Dual-AI Approval:[/bold]")
            console.print(f"  Re-validation: {'[green]✓ PASS[/green]' if post_valid else '[red]✗ FAIL[/red]'}")
            console.print(f"  Gemini Review: {'[green]✓ PASS[/green]' if gemini_approved else '[red]✗ FAIL[/red]'}")
            console.print("─" * 40)
        
        if not dual_approved:
            if RICH_AVAILABLE:
                console.print("[red]✗ Cannot apply: Both validations must pass[/red]")
            return False
        
        # Apply
        if RICH_AVAILABLE:
            console.print("[green]✓ Both validations passed![/green]")
        
        save_topology("topology.json", fixed_topology)
        if RICH_AVAILABLE:
            console.print("[green]✓ Applied Dual-AI fix to topology.json[/green]")
        return True

    def _single_ai_fix(self, current_topology: dict, errors: list, api_key: str) -> bool:
        """
        Single-AI fix using Gemini only (fallback mode)
        """
        if RICH_AVAILABLE:
            console.print()
            console.print(Panel.fit(
                "[bold yellow]AI Auto-Fix[/bold yellow]\n"
                "[dim]Powered by Gemini (single-AI mode)[/dim]",
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
                    from validate.cloud_resources_aws import AWSUtils
                    self.validated_resources = AWSUtils().validate_resources(self.topology)
                elif self.provider == "openstack":
                    from validate.cloud_resources_openstack import validate_resources
                    self.validated_resources = validate_resources(self.topology)
        else:
            if self.provider == "aws":
                from validate.cloud_resources_aws import AWSUtils
                self.validated_resources = AWSUtils().validate_resources(self.topology)
            elif self.provider == "openstack":
                from validate.cloud_resources_openstack import validate_resources
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

    def create_shared_vpc_folder(self, main_folder, original_topology, suffixes):
        """Create shared VPC folder with all networks for AWS multi-copy deployment"""
        shared_vpc_path = os.path.join(main_folder, "00-shared-vpc")
        os.makedirs(shared_vpc_path, exist_ok=True)

        if RICH_AVAILABLE:
            console.print(f"\n[cyan]Creating shared VPC folder...[/cyan]")
        else:
            print(f"\n Creating shared VPC folder: {shared_vpc_path}")

        # Copy AWS modules to shared VPC folder
        aws_modules_src = os.path.join(PROVIDERS_DIR, self.provider, "modules")
        aws_modules_dst = os.path.join(shared_vpc_path, "modules")
        if os.path.exists(aws_modules_src):
            shutil.copytree(aws_modules_src, aws_modules_dst)

        # Collect all networks/routers from all copies
        all_networks, all_routers = collect_all_networks_and_routers(
            original_topology,
            suffixes,
            self.provider
        )
        
        # Calculate VPC CIDR for AWS (only from networks with gateway_ip)
        vpc_cidr = "192.168.0.0/16"  # Default
        if self.provider == 'aws' and all_networks:
            networks_with_gateway = [net for net in all_networks if net.get('gateway_ip')]
            if networks_with_gateway:
                vpc_cidr = calculate_vpc_cidr(networks_with_gateway)
        
        # Calculate public subnet CIDR from VPC CIDR (avoid conflicts with topology subnets)
        import ipaddress
        vpc_network = ipaddress.ip_network(vpc_cidr, strict=False)
        
        # Get all used /24 networks in topology
        used_networks = set()
        for net in all_networks:
            try:
                net_cidr = ipaddress.ip_network(net['cidr'], strict=False)
                # Get the /24 that contains this subnet
                supernet_24 = ipaddress.ip_network(f"{net_cidr.network_address}/24", strict=False)
                used_networks.add(str(supernet_24))
            except:
                continue
        
        # Find first available /24 subnet in VPC range (start from last to avoid common ranges)
        public_subnet_cidr = None
        for subnet in reversed(list(vpc_network.subnets(new_prefix=24))):
            if str(subnet) not in used_networks:
                public_subnet_cidr = str(subnet)
                break
        
        if not public_subnet_cidr:
            # Fallback: use last /24 in VPC range
            public_subnet_cidr = str(list(vpc_network.subnets(new_prefix=24))[-1])

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

        # Generate variables.tf with dynamic VPC CIDR
        variables_content = tf_tpl.aws_shared_vpc_variables_block(vpc_cidr, public_subnet_cidr)
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
            shutil.copytree(os.path.join(PROVIDERS_DIR, self.provider), dir_path)
            
            # Remove outputs.tf if using shared VPC (will create custom one)
            if use_shared_vpc and os.path.exists(os.path.join(dir_path, 'outputs.tf')):
                os.remove(os.path.join(dir_path, 'outputs.tf'))

            # Modify topology with unique suffix
            modified_topology = modify_topology(original_topology, suffix)
            with open(os.path.join(dir_path, 'topology.json'), 'w') as f:
                json.dump(modified_topology, f, indent=2)

            # Process cloud-init JSON -> YAML
            self.process_cloud_init_configs(dir_path)

            # Generate main.tf with validated resources
            validated_map = self.build_validated_map(suffix)
            config_content = self.generate_config_content(validated_map, use_shared_vpc)
            with open(os.path.join(dir_path, 'main.tf'), 'w', encoding='utf-8') as f:
                f.write(config_content)
            
            # Generate outputs.tf for shared VPC mode
            if use_shared_vpc and self.provider == "aws":
                with open(os.path.join(dir_path, 'outputs.tf'), 'w', encoding='utf-8') as f:
                    f.write(tf_tpl.aws_instance_only_outputs_block())

            # Update variables.tf with discovered config for OpenStack
            if self.provider == 'openstack' and self.openstack_config:
                self.update_openstack_variables(dir_path)

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

    def update_openstack_variables(self, dir_path):
        """Update variables.tf with discovered OpenStack configuration"""
        variables_file = os.path.join(dir_path, 'variables.tf')
        if not os.path.exists(variables_file):
            return
        
        # Read current variables.tf
        with open(variables_file, 'r') as f:
            content = f.read()
        
        # Update default values with discovered config
        if self.openstack_config:
            # Update auth_url
            content = content.replace(
                'default     = "http://10.102.192.230:5000"',
                f'default     = "{self.openstack_config["auth_url"]}"'
            )
            # Update region
            content = content.replace(
                'default     = "RegionOne"',
                f'default     = "{self.openstack_config["region"]}"'
            )
            # Update tenant/project name
            content = content.replace(
                'default     = "dacn"',
                f'default     = "{self.openstack_config["project_name"]}"'
            )
            # Update username
            if 'openstack_user_name' in content:
                import re
                content = re.sub(
                    r'(variable "openstack_user_name".*?default\s*=\s*)"[^"]*"',
                    f'\\1"{self.openstack_config["username"]}"',
                    content,
                    flags=re.DOTALL
                )
            # Update password
            if 'openstack_password' in content:
                content = re.sub(
                    r'(variable "openstack_password".*?default\s*=\s*)"[^"]*"',
                    f'\\1"{self.openstack_config["password"]}"',
                    content,
                    flags=re.DOTALL
                )
        
        # Update external network info if discovered
        ext_net_name = None
        ext_net_id = None
        
        # Priority 1: Use from profile config
        if self.openstack_config and 'external_network_name' in self.openstack_config:
            ext_net_name = self.openstack_config['external_network_name']
        
        # Priority 2: Use from discovered resources
        if self.discovered_resources and 'external_network' in self.discovered_resources:
            ext_net = self.discovered_resources['external_network']
            ext_net_id = ext_net["id"]
            if not ext_net_name:  # Only override if not set in profile
                ext_net_name = ext_net["name"]
        
        # Apply external network config
        if ext_net_id:
            content = re.sub(
                r'(variable "external_network_id".*?default\s*=\s*)"[^"]*"',
                f'\\1"{ext_net_id}"',
                content,
                flags=re.DOTALL
            )
        if ext_net_name:
            content = re.sub(
                r'(variable "external_network_name".*?default\s*=\s*)"[^"]*"',
                f'\\1"{ext_net_name}"',
                content,
                flags=re.DOTALL
            )
        
        # Write updated content
        with open(variables_file, 'w') as f:
            f.write(content)


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
            console.print("[dim]Usage: python3 terraform_generator.py [aws|openstack] [num_copies][/dim]")
        else:
            print("\n[ERROR] Usage: python3 terraform_generator.py [aws|openstack] [num_copies]")
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
