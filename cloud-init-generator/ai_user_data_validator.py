#!/usr/bin/env python3
"""
AI-powered user-data validator
Validates cloud-init / cloudbase-init JSON using schema checks and Gemini review
"""
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import typer

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
except ImportError as e:
    print(f"Missing dependency: {e}. Install with: pip install rich typer")
    sys.exit(1)

# Gemini client (optional)
try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GEMINI_AVAILABLE = False

from validate_cloudinit import collect_errors, format_path, get_custom_message


app = typer.Typer(help="AI-powered validator for cloud-init / cloudbase-init user-data JSON")
console = Console()

DEFAULT_MODEL = "gemini-2.5-flash"

# System prompt with explicit validation logic
SYSTEM_PROMPT = """You are a senior cloud-init/cloudbase-init engineer.
Review user-data JSON for correctness, safety, and portability across Linux/Windows targets.

Validation rules to enforce:
- target must be one of: windows, wins, wind, winserver, linux, lin, lnx, unix
- files[] rules:
  * type=file requires content or source, must NOT have target (only links need target)
  * type=dir cannot include content/source/append/validate_cmd
  * type=link MUST include target and no content/source
  * paths must be absolute: /path or C:\\path
- users[] rules:
  * every user needs a name; primary_group/groups must match regex ^[a-zA-Z_][a-zA-Z0-9_-]*$
  * if lock_passwd=true then no hashed_passwd/plain_passwd provided
  * uid for system users <1000, regular users >=1000
  * ssh_authorized_keys must look like ssh-rsa/ssh-ed25519 or ecdsa-sha2-*
- packages:
  * ensure supports present/latest/absent
  * if ensure=absent then no version/mark_hold
  * options must be strings
- exec / commands:
  * command must be non-empty; onlyif/unless are mutually exclusive
  * timeout 0-86400, tries 1-100, try_sleep 0-3600
- services:
  * ensure running/stopped/restarted; provider allowed systemd/sysvinit/windows/launchd/smf/\"\"; name must fit provider style
- ssh_config:
  * if disable_root=true then disable_root_opts must be non-empty
  * ssh_publish_hostkeys.enabled=false requires empty blacklist
- swap requires filename/size/maxsize with unit suffix (K/M/G)
- power_state.mode in [poweroff, halt, reboot] with optional delay/message/timeout/condition
- gateway rule: not applicable here (do not invent networking)

Security and hygiene:
- warn on plain text passwords; prefer hashed_passwd
- warn if allow_public_ssh_keys=false but users expect ssh access
- flag HTTP URLs in files.source or packages keyserver as weaker than HTTPS
- flag missing packages/runcmd/service sections when intent is unclear

Output JSON ONLY with keys:
{
  "status": "pass" | "warn" | "fail",
  "critical": [],      # blocking issues
  "warnings": [],      # non-blocking but risky
  "suggested_fixes": [],  # actionable, concise
  "notes": []          # optional tips
}
No Markdown, no prose outside JSON."""


# Helpers ---------------------------------------------------------------------

def load_user_data(path: Path) -> Dict:
    """Load user-data JSON from disk."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def summarize_schema_errors(raw_errors) -> List[Dict[str, str]]:
    """Convert jsonschema errors into display-friendly dicts."""
    summaries = []
    for err in raw_errors:
        summaries.append(
            {
                "path": format_path(err),
                "message": get_custom_message(err),
                "detail": err.message if get_custom_message(err) != err.message else "",
            }
        )
    return summaries


def display_schema_results(errors: List[Dict[str, str]]):
    """Render schema validation results using Rich."""
    if not errors:
        console.print(
            Panel.fit("[green]✓ Schema validation passed[/green]", border_style="green")
        )
        return

    console.print(
        Panel.fit(
            f"[red]✗ Found {len(errors)} schema issue(s)[/red]",
            border_style="red",
        )
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="cyan", no_wrap=True)
    table.add_column("Path", style="yellow")
    table.add_column("Message", style="white")

    for idx, err in enumerate(errors, 1):
        detail = f"\n[dim]{err['detail']}[/dim]" if err.get("detail") else ""
        table.add_row(str(idx), err["path"], f"{err['message']}{detail}")

    console.print(table)


def ai_validate_user_data(
    user_data: Dict, schema_errors: List[str], api_key: Optional[str] = None
) -> Tuple[bool, Optional[Dict], str]:
    """Run Gemini to perform semantic validation."""
    if not GEMINI_AVAILABLE:
        return False, None, "google-generativeai not installed (pip install google-generativeai)"

    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return False, None, "GEMINI_API_KEY not set"

    try:
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_PROMPT,
            generation_config={"temperature": 0.25, "max_output_tokens": 2000},
        )

        schema_block = "\n".join(f"- {err}" for err in schema_errors) or "None"
        user_prompt = f"""Validate the following user-data JSON. Respect the rules above.
Schema errors already detected:
{schema_block}

USER DATA JSON:
{json.dumps(user_data, indent=2)}
"""

        with console.status("[dim]Running Gemini validation...[/dim]", spinner="dots"):
            response = model.generate_content(user_prompt)

        result = (response.text or "").strip()
        if "```json" in result:
            result = result.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in result:
            result = result.split("```", 1)[1].split("```", 1)[0].strip()

        report = json.loads(result)
        normalized = {
            "status": report.get("status", "warn"),
            "critical": report.get("critical", []) or [],
            "warnings": report.get("warnings", []) or [],
            "suggested_fixes": report.get("suggested_fixes", []) or [],
            "notes": report.get("notes", []) or [],
        }
        return True, normalized, ""
    except json.JSONDecodeError as e:
        return False, None, f"Gemini returned invalid JSON: {e}"
    except Exception as e:
        return False, None, f"Gemini validation failed: {e}"


def display_ai_report(report: Dict):
    """Render AI validation output."""
    status = report.get("status", "warn").lower()
    style = {"pass": "green", "warn": "yellow", "fail": "red"}.get(status, "yellow")
    title = f"[bold]{status.upper()}[/bold]"

    console.print()
    console.print(Panel.fit(title, border_style=style))

    def print_section(name: str, items: List[str], bullet: str):
        if not items:
            return
        console.print(f"\n[bold]{name}[/bold]")
        for entry in items:
            console.print(f"{bullet} {entry}")

    print_section("Critical", report.get("critical", []), "[red]•[/red]")
    print_section("Warnings", report.get("warnings", []), "[yellow]•[/yellow]")
    print_section("Suggested fixes", report.get("suggested_fixes", []), "[green]•[/green]")
    print_section("Notes", report.get("notes", []), "[cyan]•[/cyan]")


# CLI command -----------------------------------------------------------------

@app.command()
def validate(
    file: str = typer.Option(
        str(Path(__file__).parent / "cloud_init.json"),
        "--file",
        "-f",
        help="Path to user-data JSON to validate",
    ),
    ai: bool = typer.Option(
        True, "--ai/--no-ai", help="Enable Gemini semantic validation"
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", envvar="GEMINI_API_KEY", help="Gemini API key"
    ),
):
    """Validate user-data JSON with schema checks and optional Gemini review."""
    console.print()
    console.print(
        Panel.fit(
            "[bold]User-Data Validation[/bold]\n[dim]Schema + Gemini review[/dim]",
            border_style="blue",
        )
    )

    path = Path(file)
    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}")
        raise typer.Exit(1)

    try:
        user_data = load_user_data(path)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON:[/red] line {e.lineno}, col {e.colno} - {e.msg}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading file:[/red] {e}")
        raise typer.Exit(1)

    # Schema validation
    raw_errors = collect_errors(user_data)
    schema_errors = summarize_schema_errors(raw_errors)
    display_schema_results(schema_errors)

    ai_report = None
    ai_error = ""
    if ai:
        success, ai_report, ai_error = ai_validate_user_data(
            user_data, [e["message"] for e in schema_errors], api_key
        )
        if success and ai_report:
            display_ai_report(ai_report)
        else:
            console.print(f"[yellow]AI validation skipped:[/yellow] {ai_error}")

    console.print()
    if schema_errors:
        console.print("[red]Result:[/red] Please fix schema errors above.")
        raise typer.Exit(1)

    if ai and ai_report and ai_report.get("status") == "fail":
        console.print("[red]Result:[/red] AI flagged blocking issues. Review suggestions above.")
        raise typer.Exit(1)

    console.print("[green]Result:[/green] User-data passed validation.")


@app.command()
def show(path: str = typer.Argument(str(Path(__file__).parent / "cloud_init.json"))):
    """Show the user-data JSON with syntax highlighting."""
    file_path = Path(path)
    if not file_path.exists():
        console.print(f"[red]File not found:[/red] {file_path}")
        raise typer.Exit(1)

    try:
        data = load_user_data(file_path)
    except Exception as e:
        console.print(f"[red]Error loading file:[/red] {e}")
        raise typer.Exit(1)

    console.print(
        Panel(
            Syntax(json.dumps(data, indent=2), "json", theme="monokai"),
            title=str(file_path),
            border_style="blue",
        )
    )


if __name__ == "__main__":
    app()
