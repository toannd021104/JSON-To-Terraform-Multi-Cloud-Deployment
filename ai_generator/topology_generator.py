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
    from openai import OpenAI
except ImportError as e:
    print(f"Error: Missing required library: {e}")
    print("\nInstall dependencies:")
    print("  pip install typer rich questionary openai")
    sys.exit(1)

app = typer.Typer(help="AI-powered Topology Generator for Multi-Cloud Deployment")
console = Console()

SYSTEM_PROMPT = """You are a cloud infrastructure expert. Help users create valid topology.json files for multi-cloud deployment.

A topology.json file MUST contain ALL three components: instances, networks, and routers.

You must handle COMPLEX topologies including:
- Multiple routers with hierarchical relationships (edge router -> internal routers)
- Multiple networks per router
- Multiple instances per network
- Router-to-router connections via shared networks

EXAMPLE STRUCTURE:
{
  "instances": [
    {"name": "vm1", "image": "ubuntu-jammy", "cpu": 2, "ram": 4, "disk": 20,
     "networks": [{"name": "net1", "ip": "192.168.1.10"}],
     "keypair": "my-keypair", "security_groups": ["default"], "floating_ip": true}
  ],
  "networks": [
    {"name": "net1", "cidr": "192.168.1.0/24", "gateway_ip": "192.168.1.1", "enable_dhcp": true}
  ],
  "routers": [
    {"name": "edge-router", "networks": [{"name": "net1", "ip": "192.168.1.1"}], "external": true},
    {"name": "internal-R1", "networks": [{"name": "net1", "ip": "192.168.1.254"}, {"name": "net2", "ip": "192.168.2.1"}], "external": false}
  ]
}

CRITICAL RULES:
1. ALWAYS include instances, networks, AND routers sections
2. Each instance MUST reference a network that exists in networks section
3. Each router MUST connect to networks defined in networks section
4. Router gateway IP MUST match the network's gateway_ip OR be within the network's CIDR
5. Use private IP ranges: 192.168.x.0/24, 10.x.x.0/24, 172.16-31.x.0/24
6. Default image: "ubuntu-jammy" or "ubuntu-server-noble"
7. Edge router (internet-facing) has "external": true
8. Internal routers have "external": false
9. For router-to-router connections, use a shared network

NAMING CONVENTIONS:
- Routers: edge-router, R1, R2, internal-R1, etc.
- Networks: net1, net2, web-network, db-network, etc.
- Instances: vm1, web1, db1, worker-1, etc.

COMPLEX EXAMPLE - "1 edge router, 2 internal routers, each internal router has 3 networks with 3 instances each":
- 1 edge router (external=true) connected to transit-net
- 2 internal routers (R1, R2) each connected to transit-net + 3 own networks
- Total: 1 edge + 2 internal = 3 routers
- Total: 1 transit + 6 private = 7 networks
- Total: 6 networks x 3 instances = 18 instances

Based on user's description, generate a COMPLETE topology.json with all three sections.
IMPORTANT: Return ONLY the JSON, no explanations, no markdown code blocks."""


EXAMPLES = [
    "Simple: 3 VMs with 2 CPUs each on one network",
    "Complex: 1 edge router, 2 internal routers, each has 3 networks with 3 VMs",
    "Medium: 2 routers, 4 networks, 8 VMs total",
    "Large: 1 edge router to internet, 3 internal routers, each router has 2 networks, each network has 5 VMs",
]


def generate_topology_with_ai(user_input: str, api_key: str) -> dict:
    """Generate topology JSON using OpenAI API"""

    client = OpenAI(api_key=api_key)

    with console.status("[dim]Generating topology with AI...", spinner="dots"):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            result = response.choices[0].message.content.strip()

            # Extract JSON if wrapped in markdown
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()

            topology = json.loads(result)

            # Validate that all required sections exist
            required_sections = ["instances", "networks", "routers"]
            missing_sections = [s for s in required_sections if s not in topology or not topology[s]]

            if missing_sections:
                console.print(f"[yellow]Warning:[/yellow] AI output missing sections: {', '.join(missing_sections)}")
                console.print("[dim]Retrying with more specific prompt...[/dim]")

                # Retry with more specific prompt
                retry_prompt = f"{user_input}\n\nIMPORTANT: Include instances, networks, AND routers sections in the output."
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": retry_prompt}
                    ],
                    temperature=0.5,
                    max_tokens=2000
                )
                result = response.choices[0].message.content.strip()
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0].strip()
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0].strip()
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
        output_path = Path(__file__).parent.parent / "terraform-generator" / "topology.json"
        with open(output_path, "w") as f:
            json.dump(topology, f, indent=2)
        console.print(f"[green]Saved:[/green] {output_path}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  cd terraform-generator")
        console.print("  python3 generate.py [aws|openstack] <copies>")
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
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        console.print("\n[red]Error:[/red] OPENAI_API_KEY not set")
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
        output_path = Path(__file__).parent.parent / "terraform-generator" / output

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
