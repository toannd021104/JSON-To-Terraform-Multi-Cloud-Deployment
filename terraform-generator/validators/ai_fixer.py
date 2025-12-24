#!/usr/bin/env python3
"""
AI-powered Topology Fixer
Uses Google Gemini to analyze and fix validation errors in topology.json
Provides diff preview before applying changes
"""
import os
import json
from typing import Tuple, List, Optional

# Gemini library for AI-powered fixes
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

# Default model (can override with GEMINI_MODEL env var)
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

# Rich library for colored terminal output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    console = None


# =============================================================================
# AI System Prompt - Instructions for Gemini
# =============================================================================
FIXER_PROMPT = """You are a cloud infrastructure expert. Your task is to FIX the topology.json file based on the validation errors provided.

TOPOLOGY STRUCTURE:
- instances[]: name, image, cpu, ram, disk, networks[], keypair, security_groups[], floating_ip (optional: true/false/"x.x.x.x"), cloud_init (optional)
- networks[]: name, cidr, gateway_ip, enable_dhcp
- routers[]: name, networks[], external, routes[]

VALIDATION RULES:
1. All IPs in instances and routers must be within their network's CIDR
2. No duplicate IPs in the same network
3. All referenced networks must exist (check for typos in network names!)
4. floating_ip can be: true (allocate new), false (none), or "x.x.x.x" (specific IP)
5. Static routes nexthop must be reachable from router's connected networks
6. Internal routers (external: false) should have default route to edge router

CRITICAL - GATEWAY IP MATCHING:
The network's "gateway_ip" and router's interface IP MUST be the SAME!
- networks[].gateway_ip = The IP that VMs use as their default gateway
- routers[].networks[].ip = The IP that router actually listens on

If they don't match, VMs will send traffic to gateway_ip but router won't receive it!

Example of CORRECT configuration:
{
  "networks": [{"name": "net1", "cidr": "192.168.1.0/24", "gateway_ip": "192.168.1.1", ...}],
  "routers": [{"name": "R1", "networks": [{"name": "net1", "ip": "192.168.1.1"}], ...}]
}
                                                              ^ MUST MATCH ^

FIXING GUIDELINES:
- Fix IP addresses to be within the correct CIDR range
- Fix duplicate IPs by incrementing them
- Add missing networks if referenced
- Fix typos in network names (e.g., "test-t" -> "test-net", "tet-net" -> "test-net")
- IMPORTANT: Ensure gateway_ip matches the router interface IP for each network
- Prefer using .1 as gateway (e.g., 192.168.1.1 for 192.168.1.0/24)
- Keep the original structure and intent as much as possible

IMPORTANT: Return ONLY valid JSON. No explanations, no markdown, no code blocks, no comments. Just the raw JSON object."""


def fix_topology_with_ai(topology: dict, errors: List[str], api_key: Optional[str] = None) -> Tuple[bool, dict, List[str]]:
    """
    Use Gemini to fix topology.json based on validation errors

    Args:
        topology: Current topology dict
        errors: List of validation error messages
        api_key: Gemini API key (optional, uses env var if not provided)

    Returns:
        (success, fixed_topology, fixes_made)
    """
    # Check prerequisites
    if not GEMINI_AVAILABLE:
        return False, topology, ["google-generativeai not installed. Run: pip install google-generativeai"]

    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return False, topology, ["GEMINI_API_KEY not set"]

    try:
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=FIXER_PROMPT,
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": 8000
            }
        )

        # Build user prompt with topology and errors
        user_prompt = f"""Fix this topology.json based on the validation errors below.

CURRENT TOPOLOGY:
{json.dumps(topology, indent=2)}

VALIDATION ERRORS:
{chr(10).join(f"- {error}" for error in errors)}

Return the FIXED topology.json only."""

        # Call Gemini API with loading spinner
        if RICH_AVAILABLE:
            with console.status("[dim]AI is analyzing and fixing errors...[/dim]", spinner="dots"):
                response = model.generate_content(user_prompt)
        else:
            response = model.generate_content(user_prompt)

        result = (response.text or "").strip()
        if not result:
            return False, topology, ["Gemini returned empty response"]

        # Strip markdown code blocks if AI included them
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0].strip()
        elif "```" in result:
            result = result.split("```")[1].split("```")[0].strip()
        
        # Clean up common JSON issues from AI response
        # Remove trailing commas before closing brackets
        import re
        result = re.sub(r',(\s*[}\]])', r'\1', result)
        # Remove comments if any
        result = re.sub(r'//.*?\n', '\n', result)
        result = re.sub(r'/\*.*?\*/', '', result, flags=re.DOTALL)

        # Parse AI response as JSON
        try:
            fixed_topology = json.loads(result)
        except json.JSONDecodeError as e:
            # If still fails, show full response for debugging
            if RICH_AVAILABLE:
                console.print(f"[yellow]Full AI Response:[/yellow]\n{result}")
                console.print(f"[red]JSON Error: {str(e)}[/red]")
            raise

        # Compare original vs fixed to generate human-readable report
        fixes_made = _compare_and_report_fixes(topology, fixed_topology, errors)

        return True, fixed_topology, fixes_made

    except json.JSONDecodeError as e:
        return False, topology, [f"AI returned invalid JSON: {str(e)}"]
    except Exception as e:
        return False, topology, [f"AI fix failed: {str(e)}"]


def _compare_and_report_fixes(original: dict, fixed: dict, errors: List[str]) -> List[str]:
    """
    Compare original vs fixed topology and generate human-readable fix report
    Detects: IP changes, network name typos, gateway changes, route changes
    """
    fixes = []

    # Compare instances
    orig_instances = {i['name']: i for i in original.get('instances', [])}
    fixed_instances = {i['name']: i for i in fixed.get('instances', [])}

    for name, fixed_inst in fixed_instances.items():
        if name in orig_instances:
            orig_inst = orig_instances[name]

            # Check for IP changes in networks
            orig_nets = {n['name']: n.get('ip') for n in orig_inst.get('networks', [])}
            fixed_nets = {n['name']: n.get('ip') for n in fixed_inst.get('networks', [])}
            for net_name, fixed_ip in fixed_nets.items():
                orig_ip = orig_nets.get(net_name)
                if orig_ip and orig_ip != fixed_ip:
                    fixes.append(f"Instance '{name}': IP changed {orig_ip} -> {fixed_ip}")

            # Check for floating_ip changes
            if orig_inst.get('floating_ip') != fixed_inst.get('floating_ip'):
                fixes.append(f"Instance '{name}': floating_ip changed")
        else:
            fixes.append(f"Instance '{name}': added")

    # Compare networks
    orig_networks = {n['name']: n for n in original.get('networks', [])}
    fixed_networks = {n['name']: n for n in fixed.get('networks', [])}

    for name, fixed_net in fixed_networks.items():
        if name in orig_networks:
            orig_net = orig_networks[name]

            # Check CIDR changes
            if orig_net.get('cidr') != fixed_net.get('cidr'):
                fixes.append(f"Network '{name}': CIDR changed {orig_net.get('cidr')} -> {fixed_net.get('cidr')}")

            # Check gateway_ip changes
            if orig_net.get('gateway_ip') != fixed_net.get('gateway_ip'):
                fixes.append(f"Network '{name}': gateway_ip changed {orig_net.get('gateway_ip')} -> {fixed_net.get('gateway_ip')}")
        else:
            fixes.append(f"Network '{name}': added")

    # Check for network name typo fixes in instances
    for orig_inst in original.get('instances', []):
        for fixed_inst in fixed.get('instances', []):
            if orig_inst['name'] == fixed_inst['name']:
                orig_net_names = [n['name'] for n in orig_inst.get('networks', [])]
                fixed_net_names = [n['name'] for n in fixed_inst.get('networks', [])]
                for i, (orig_name, fixed_name) in enumerate(zip(orig_net_names, fixed_net_names)):
                    if orig_name != fixed_name:
                        fixes.append(f"Instance '{orig_inst['name']}': network name fixed '{orig_name}' -> '{fixed_name}'")

    # Compare routers
    orig_routers = {r['name']: r for r in original.get('routers', [])}
    fixed_routers = {r['name']: r for r in fixed.get('routers', [])}

    for name, fixed_router in fixed_routers.items():
        if name in orig_routers:
            orig_router = orig_routers[name]

            # Check for network name typo fixes
            orig_net_names = [n['name'] for n in orig_router.get('networks', [])]
            fixed_net_names = [n['name'] for n in fixed_router.get('networks', [])]
            for orig_name, fixed_name in zip(orig_net_names, fixed_net_names):
                if orig_name != fixed_name:
                    fixes.append(f"Router '{name}': network name fixed '{orig_name}' -> '{fixed_name}'")

            # Check for IP changes on router interfaces
            orig_nets = {n['name']: n.get('ip') for n in orig_router.get('networks', [])}
            fixed_nets = {n['name']: n.get('ip') for n in fixed_router.get('networks', [])}
            for net_name, fixed_ip in fixed_nets.items():
                orig_ip = orig_nets.get(net_name)
                if orig_ip and orig_ip != fixed_ip:
                    fixes.append(f"Router '{name}': IP on '{net_name}' changed {orig_ip} -> {fixed_ip}")

            # Check route count changes
            orig_routes = len(orig_router.get('routes', []))
            fixed_routes = len(fixed_router.get('routes', []))
            if orig_routes != fixed_routes:
                fixes.append(f"Router '{name}': routes changed ({orig_routes} -> {fixed_routes})")
        else:
            fixes.append(f"Router '{name}': added")

    # Default message if no specific fixes detected
    if not fixes:
        fixes.append("Minor structural fixes applied")

    return fixes


def _generate_diff_view(original: dict, fixed: dict) -> str:
    """
    Generate colored diff view using Rich markup
    - Red strikethrough: removed/changed lines
    - Green bold: new/changed lines
    """
    import difflib

    orig_lines = json.dumps(original, indent=2).splitlines()
    fixed_lines = json.dumps(fixed, indent=2).splitlines()

    diff_output = []
    matcher = difflib.SequenceMatcher(None, orig_lines, fixed_lines)

    # Process each diff operation
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Unchanged lines
            for line in orig_lines[i1:i2]:
                diff_output.append(f"  {line}")
        elif tag == 'replace':
            # Changed lines: show old (red) then new (green)
            for line in orig_lines[i1:i2]:
                diff_output.append(f"[red strike]- {line}[/red strike]")
            for line in fixed_lines[j1:j2]:
                diff_output.append(f"[green bold]+ {line}[/green bold]")
        elif tag == 'delete':
            # Deleted lines (red)
            for line in orig_lines[i1:i2]:
                diff_output.append(f"[red strike]- {line}[/red strike]")
        elif tag == 'insert':
            # Inserted lines (green)
            for line in fixed_lines[j1:j2]:
                diff_output.append(f"[green bold]+ {line}[/green bold]")

    return "\n".join(diff_output)


def display_fix_preview(original: dict, fixed: dict, fixes: List[str]):
    """
    Show preview of AI fixes before applying:
    1. Human-readable list of changes
    2. Colored diff view
    """
    if not RICH_AVAILABLE:
        # Fallback for non-Rich environments
        print("\n=== AI FIXES TO BE APPLIED ===")
        for fix in fixes:
            print(f"  * {fix}")
        print("\n=== DIFF VIEW ===")
        import difflib
        orig_lines = json.dumps(original, indent=2).splitlines()
        fixed_lines = json.dumps(fixed, indent=2).splitlines()
        for line in difflib.unified_diff(orig_lines, fixed_lines, lineterm=''):
            print(line)
        return

    # Rich output with panels and colors
    console.print()
    console.print(Panel.fit(
        "[bold yellow]AI Auto-Fix Preview[/bold yellow]",
        border_style="yellow"
    ))

    # List of changes
    console.print("\n[bold]Changes to be applied:[/bold]")
    for fix in fixes:
        console.print(f"  [green]*[/green] {fix}")

    # Diff view
    console.print()
    diff_view = _generate_diff_view(original, fixed)
    console.print(Panel(
        diff_view,
        title="[bold]Diff View[/bold] [dim](red=removed, green=added)[/dim]",
        border_style="yellow"
    ))


def apply_fix(fixed_topology: dict, file_path: str = "topology.json") -> bool:
    """Save the AI-fixed topology to file"""
    try:
        with open(file_path, 'w') as f:
            json.dump(fixed_topology, f, indent=2)
        return True
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[red]Error saving:[/red] {str(e)}")
        else:
            print(f"Error saving: {str(e)}")
        return False
