#!/usr/bin/env python3
"""
AI-powered Topology Generator
Uses OpenAI API to help users create topology.json files
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional

try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.markup import escape
    import questionary
    import google.generativeai as genai
except ImportError as e:
    print(f"Error: Missing required library: {e}")
    print("\nInstall dependencies:")
    print("  pip install typer rich questionary openai")
    sys.exit(1)


app = typer.Typer(help="AI-powered Topology Generator for Multi-Cloud Deployment")
console = Console()

SYSTEM_PROMPT = """You are a cloud infrastructure expert. Help users create valid topology.json files for multi-cloud deployment.

A topology.json file MUST contain ALL three components: instances, networks, and routers.

REQUIRED FIELDS (MUST INCLUDE ALL):
- instances[]: name, image, cpu, ram, disk, networks[], keypair, security_groups[]
- networks[]: name, cidr, gateway_ip, enable_dhcp, pool (always include "pool": [])
- routers[]: name, networks[], external, routes (always include "routes": [])

ROUTING RULES (CRITICAL):
1. Internal routers (external: false) MUST have a default route to edge router:
   "routes": [{"destination": "0.0.0.0/0", "nexthop": "<edge_router_ip>"}]
2. Edge router MUST have routes to reach internal networks:
   "routes": [{"destination": "<internal_network_cidr>", "nexthop": "<internal_router_ip>"}]
3. Routes use IP addresses, not network names

EXAMPLE WITH ROUTES:
{
  "instances": [
    {"name": "web-server", "image": "ubuntu-jammy", "cpu": 2, "ram": 4, "disk": 20,
     "networks": [{"name": "web-net", "ip": "192.168.1.10"}],
     "keypair": "my-keypair", "security_groups": ["default"], "floating_ip": true},
    {"name": "db-server", "image": "ubuntu-jammy", "cpu": 2, "ram": 4, "disk": 20,
     "networks": [{"name": "db-net", "ip": "192.168.2.10"}],
     "keypair": "my-keypair", "security_groups": ["default"], "floating_ip": false}
  ],
  "networks": [
    {"name": "web-net", "cidr": "192.168.1.0/24", "gateway_ip": "192.168.1.1", "enable_dhcp": true, "pool": []},
    {"name": "db-net", "cidr": "192.168.2.0/24", "gateway_ip": "192.168.2.1", "enable_dhcp": true, "pool": []}
  ],
  "routers": [
    {"name": "edge-router", "networks": [{"name": "web-net", "ip": "192.168.1.1"}], "external": true,
     "routes": [{"destination": "192.168.2.0/24", "nexthop": "192.168.1.254"}]},
    {"name": "internal-R1", "networks": [{"name": "web-net", "ip": "192.168.1.254"}, {"name": "db-net", "ip": "192.168.2.1"}], "external": false,
     "routes": [{"destination": "0.0.0.0/0", "nexthop": "192.168.1.1"}]}
  ]
}

CRITICAL RULES:
1. ALWAYS include instances, networks, AND routers sections
2. ALWAYS include "pool": [] in every network
3. ALWAYS include "routes": [] in every router (even if empty for simple topologies)
4. Each instance MUST reference a network that exists in networks section
5. Each router MUST connect to networks defined in networks section
6. Router IP MUST be within the network's CIDR
7. Use private IP ranges: 192.168.x.0/24, 10.x.x.0/24, 172.16-31.x.0/24
8. Default image: "ubuntu-jammy" or "ubuntu-server-noble"
9. Edge router (internet-facing) has "external": true
10. Internal routers have "external": false and NEED default route to edge router
11. For multi-router topology, use a shared/transit network to connect routers

NAMING CONVENTIONS:
- Routers: edge-router, R1, R2, internal-R1, db-router, etc.
- Networks: net1, web-net, db-net, transit-net, etc.
- Instances: vm1, web-server, db-server, worker-1, etc.

Based on user's description, generate a COMPLETE topology.json with all three sections.
IMPORTANT: Return ONLY the JSON, no explanations, no markdown code blocks."""


EXAMPLES = [
    "Simple: 2 VMs on 1 network with 1 router",
    "Web + DB: web server với floating IP và database server trên 2 network khác nhau",
    "3-tier: web, app, db trên 3 network riêng biệt với routes đầy đủ",
    "Complex: 1 edge router, 2 internal routers, mỗi internal router có 2 networks với 3 VMs",
]



def generate_topology_with_ai(user_input: str, api_key: str = None) -> dict:
    """Generate topology JSON using Google Gemini API"""
    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] GEMINI_API_KEY not set. Please export your Gemini API key.")
        raise typer.Exit(1)
    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=SYSTEM_PROMPT,
        generation_config={
            "temperature": 0.7,
            "max_output_tokens": 4000
        }
    )
    with console.status("[dim]Generating topology with AI...", spinner="dots"):
        try:
            user_prompt = user_input
            response = model.generate_content(user_prompt)
            result = (response.text or "").strip()
            # Extract JSON if wrapped in markdown
            if "```json" in result:
                result = result.split("```json")[1].split("```", 1)[0].strip()
            elif "```" in result:
                result = result.split("```", 1)[1].split("```", 1)[0].strip()
            topology = json.loads(result)
            # Validate that all required sections exist
            required_sections = ["instances", "networks", "routers"]
            missing_sections = [s for s in required_sections if s not in topology or not topology[s]]
            if missing_sections:
                console.print(f"[yellow]Warning:[/yellow] AI output missing sections: {', '.join(missing_sections)}")
                console.print("[dim]Retrying with more specific prompt...[/dim]")
                retry_prompt = f"{user_input}\n\nIMPORTANT: Include instances, networks, AND routers sections in the output."
                response = model.generate_content(retry_prompt)
                result = (response.text or "").strip()
                if "```json" in result:
                    result = result.split("```json")[1].split("```", 1)[0].strip()
                elif "```" in result:
                    result = result.split("```", 1)[1].split("```", 1)[0].strip()
                topology = json.loads(result)
            return topology
        except json.JSONDecodeError as e:
            console.print(f"[red]Error:[/red] Failed to parse JSON response")
            console.print(f"\n[dim]{result}[/dim]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)


def display_topology_summary(topology: dict):
    """Display topology summary in clean tables"""

    # Instances table
    if topology.get("instances"):
        console.print()
        table = Table(
            title="Instances",
            show_header=True,
            header_style="bold",
            border_style="dim",
            title_style="bold"
        )
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("CPU", justify="right")
        table.add_column("RAM (GB)", justify="right")
        table.add_column("Disk (GB)", justify="right")
        table.add_column("Networks")
        table.add_column("Floating IP", justify="center")

        for inst in topology["instances"]:
            networks = ", ".join([n["name"] for n in inst.get("networks", [])])
            floating = "Yes" if inst.get("floating_ip") else "No"
            table.add_row(
                inst["name"],
                str(inst.get("cpu", "-")),
                str(inst.get("ram", "-")),
                str(inst.get("disk", "-")),
                networks,
                floating
            )
        console.print(table)

    # Networks table
    if topology.get("networks"):
        console.print()
        table = Table(
            title="Networks",
            show_header=True,
            header_style="bold",
            border_style="dim",
            title_style="bold"
        )
        table.add_column("Name", style="cyan")
        table.add_column("CIDR")
        table.add_column("Gateway")
        table.add_column("DHCP", justify="center")

        for net in topology["networks"]:
            dhcp = "Enabled" if net.get("enable_dhcp") else "Disabled"
            table.add_row(
                net["name"],
                net.get("cidr", "-"),
                net.get("gateway_ip", "-"),
                dhcp
            )
        console.print(table)

    # Routers table
    if topology.get("routers"):
        console.print()
        table = Table(
            title="Routers",
            show_header=True,
            header_style="bold",
            border_style="dim",
            title_style="bold"
        )
        table.add_column("Name", style="cyan")
        table.add_column("External", justify="center")
        table.add_column("Connected Networks")

        for router in topology["routers"]:
            networks = ", ".join([n["name"] for n in router.get("networks", [])])
            external = "Yes" if router.get("external") else "No"
            table.add_row(
                router["name"],
                external,
                networks
            )
        console.print(table)


@app.command()
def interactive():
    """Interactive mode with prompts"""

    console.print()
    console.print(Panel.fit(
        "[bold]AI Topology Generator[/bold]\n"
        "[dim]Powered by GPT-4o-mini[/dim]",
        border_style="blue"
    ))

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        console.print("\n[red]Error:[/red] OPENAI_API_KEY environment variable not set")
        console.print("[dim]Set it with: export OPENAI_API_KEY='your-key'[/dim]")
        raise typer.Exit(1)

    # Show examples
    console.print("\n[bold]Example prompts:[/bold]")
    for i, example in enumerate(EXAMPLES, 1):
        console.print(f"  [dim]{i}.[/dim] {example}")

    # Get user input
    console.print()
    user_input = questionary.text(
        "Describe your infrastructure:",
        qmark="",
        style=questionary.Style([
            ('question', 'bold'),
            ('answer', 'fg:cyan bold'),
        ])
    ).ask()

    if not user_input:
        console.print("[yellow]Warning:[/yellow] No input provided")
        raise typer.Exit(1)

    # Generate topology
    topology = generate_topology_with_ai(user_input, api_key)

    console.print("\n[green]Success:[/green] Topology generated")

    # Display summary
    display_topology_summary(topology)

    # Show full JSON
    console.print()
    console.print(Panel(
        Syntax(json.dumps(topology, indent=2), "json", theme="monokai", line_numbers=False),
        title="[bold]Generated JSON[/bold]",
        border_style="blue"
    ))

    # Ask to save
    console.print()
    save = questionary.confirm(
        "Save to topology.json?",
        default=True,
        qmark=""
    ).ask()

    if save:
        output_path = Path(__file__).parent.parent / "generate" / "topology.json"
        with open(output_path, "w") as f:
            json.dump(topology, f, indent=2)
        console.print(f"[green]Saved:[/green] {output_path}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  cd generate")
        console.print("  python3 terraform_generator.py [aws|openstack] <copies>")
        console.print()
    else:
        console.print("[dim]Not saved[/dim]")


@app.command()
def generate(
    description: str = typer.Argument(..., help="Infrastructure description"),
    output: Optional[str] = typer.Option("topology.json", "--output", "-o", help="Output file path"),
    preview: bool = typer.Option(True, "--preview/--no-preview", help="Show preview tables"),
    json_output: bool = typer.Option(False, "--json/--no-json", help="Show full JSON output"),
):
    """Generate topology from command line"""

    console.print()
    console.print(Panel.fit(
        f"[bold]Generating Topology[/bold]\n"
        f"[dim]{description}[/dim]",
        border_style="blue"
    ))


    # Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("\n[red]Error:[/red] GEMINI_API_KEY not set")
        raise typer.Exit(1)

    # Generate
    topology = generate_topology_with_ai(description, api_key)

    console.print("[green]Success:[/green] Generation complete")

    # Preview
    if preview:
        display_topology_summary(topology)

    # Full JSON
    if json_output:
        console.print()
        console.print(Panel(
            Syntax(json.dumps(topology, indent=2), "json", theme="monokai", line_numbers=False),
            title="[bold]Generated JSON[/bold]",
            border_style="blue"
        ))

    # Save
    if output.startswith("/"):
        output_path = Path(output)
    else:
        output_path = Path(__file__).parent.parent / "generate" / output

    with open(output_path, "w") as f:
        json.dump(topology, f, indent=2)

    console.print(f"\n[green]Saved:[/green] {output_path}")
    console.print()


@app.command()
def examples():
    """Show example prompts"""

    console.print()
    console.print(Panel.fit(
        "[bold]Example Prompts[/bold]",
        border_style="blue"
    ))

    for i, example in enumerate(EXAMPLES, 1):
        console.print(f"\n  [bold]{i}.[/bold] {example}")

    console.print("\n[dim]Usage: python3 ai_topology_generator.py generate \"<prompt>\"[/dim]")
    console.print()


if __name__ == "__main__":
    app()
