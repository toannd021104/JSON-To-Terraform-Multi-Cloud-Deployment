#!/usr/bin/env python3
"""
Dual-AI topology fixer and reviewer

Flow:
- Validate topology.json with existing rules.
- If errors, ask OpenAI (ChatGPT) to propose a fix.
- Show diff; optionally write the fixed file.
- Re-validate; then ask Gemini to review the fixed topology and flag any risks.

This is intentionally separate from ai_fixer.py (Gemini-only) to allow
cross-checking between two independent AI providers.
"""
import argparse
import json
import os
import sys
import difflib
from typing import Any, Dict, List, Tuple

# Make sure we can import sibling validator
sys.path.insert(0, os.path.dirname(__file__))
from validate_json import validate_topology_file  # noqa: E402

# Optional Rich UI
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table

    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    console = None


# --------------------------------------------------------------------------- #
# OpenAI (ChatGPT) fixer
# --------------------------------------------------------------------------- #
def fix_with_openai(topology: Dict[str, Any], errors: List[str], model: str) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Use OpenAI ChatGPT to fix topology based on validation errors."""
    try:
        from openai import OpenAI
    except ImportError:
        return False, topology, ["openai package not installed (pip install openai)"]

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False, topology, ["OPENAI_API_KEY not set"]

    client = OpenAI(api_key=api_key)
    system_prompt = (
        "You are a cloud network engineer. Fix the provided topology JSON so it passes "
        "schema and network logic validation. Keep intent and structure, only adjust values.\n"
        "Rules:\n"
        "1) IPs must belong to their network CIDR; no duplicates.\n"
        "2) gateway_ip must match router interface IP for that network.\n"
        "3) All referenced networks must exist (fix typos if needed).\n"
        "4) Routes must have reachable nexthop from router interfaces.\n"
        "5) floating_ip can be true/false or explicit IP.\n"
        "Return ONLY JSON (no Markdown, no prose)."
    )
    user_prompt = (
        f"Current topology:\n{json.dumps(topology, indent=2)}\n\n"
        f"Validation errors:\n" + "\n".join(f"- {e}" for e in errors)
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content
        fixed = json.loads(content)
        return True, fixed, []
    except Exception as e:  # noqa: BLE001
        return False, topology, [str(e)]


# --------------------------------------------------------------------------- #
# Gemini reviewer (independent check after fix)
# --------------------------------------------------------------------------- #
def review_with_gemini(topology: Dict[str, Any], original_errors: List[str], post_validate_errors: List[str], model_name: str) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Ask Gemini to review fixed topology and return structured result."""
    try:
        import google.generativeai as genai
    except ImportError:
        return False, {}, ["google-generativeai not installed (pip install google-generativeai)"]

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return False, {}, ["GEMINI_API_KEY not set"]

    review_prompt = (
        "You are a second-opinion validator for cloud topology JSON. "
        "Review the fixed topology and return JSON only with keys: "
        "{status: pass|warn|fail, critical:[], warnings:[], notes:[]}. "
        "Focus on: CIDR/IP correctness, gateway vs router IP alignment, "
        "route nexthop reachability, missing networks/typos, duplicate IPs, "
        "cloud_init references existing. Be concise."
    )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name,
        system_instruction=review_prompt,
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 1200,
        },
    )

    user_prompt = (
        f"Original validation errors:\n" + "\n".join(f"- {e}" for e in original_errors) +
        f"\n\nRe-validation errors after fix:\n" + ("\n".join(f"- {e}" for e in post_validate_errors) if post_validate_errors else "None") +
        f"\n\nFixed topology JSON:\n{json.dumps(topology, indent=2)}"
    )
    try:
        res = model.generate_content(user_prompt)
        text = res.text
        review = json.loads(text)
        return True, review, []
    except Exception as e:  # noqa: BLE001
        return False, {}, [str(e)]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def render_diff(original: Dict[str, Any], fixed: Dict[str, Any]) -> str:
    """Create unified diff between two JSON objects."""
    orig_lines = json.dumps(original, indent=2).splitlines()
    fixed_lines = json.dumps(fixed, indent=2).splitlines()
    diff = difflib.unified_diff(orig_lines, fixed_lines, fromfile="original", tofile="openai-fixed", lineterm="")
    return "\n".join(diff)


def load_topology(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_topology(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description="Dual-AI topology fixer/reviewer (OpenAI + Gemini).")
    parser.add_argument("--file", default="topology.json", help="Path to topology.json (default: topology.json)")
    parser.add_argument("--provider", default="openstack", choices=["openstack", "aws"], help="Provider for validation context")
    parser.add_argument("--openai-model", default="gpt-4o-mini", help="Model name for OpenAI fixer")
    parser.add_argument("--gemini-model", default="gemini-2.5-flash", help="Model name for Gemini reviewer")
    parser.add_argument("--apply", action="store_true", help="Overwrite topology file with OpenAI-fixed version")
    args = parser.parse_args()

    topology_path = args.file
    if not os.path.isfile(topology_path):
        print(f"File not found: {topology_path}")
        sys.exit(1)

    if RICH_AVAILABLE:
        console.print(Panel.fit(f"[bold blue]Dual-AI Topology Fix/Review[/bold blue]\n[dim]{topology_path} ({args.provider})[/dim]", border_style="blue"))

    original_topology = load_topology(topology_path)

    # Initial validation
    valid, errors = validate_topology_file(topology_path, args.provider)
    if valid:
        if RICH_AVAILABLE:
            console.print(Panel.fit("[green]Topology already valid. Nothing to fix.[/green]", border_style="green"))
        else:
            print("Topology already valid. Nothing to fix.")
        sys.exit(0)

    if RICH_AVAILABLE:
        console.print(Panel.fit("[red]Validation failed[/red]\n" + "\n".join(f"- {e}" for e in errors), border_style="red"))
    else:
        print("Validation failed:")
        for e in errors:
            print(f"- {e}")

    # OpenAI fix
    if RICH_AVAILABLE:
        console.print("\n[cyan]Requesting OpenAI fix...[/cyan]")
    success, fixed_topology, fix_errors = fix_with_openai(original_topology, errors, args.openai_model)
    if not success:
        if RICH_AVAILABLE:
            console.print(Panel.fit("[red]OpenAI fix failed[/red]\n" + "\n".join(fix_errors), border_style="red"))
        else:
            print("OpenAI fix failed:")
            for e in fix_errors:
                print(f"- {e}")
        sys.exit(1)

    diff_text = render_diff(original_topology, fixed_topology)
    if diff_text:
        if RICH_AVAILABLE:
            console.print(Panel.fit(Syntax(diff_text, "diff", theme="ansi_dark"), title="Diff (OpenAI proposal)", border_style="yellow"))
        else:
            print("\nDiff (OpenAI proposal):")
            print(diff_text)
    else:
        if RICH_AVAILABLE:
            console.print("[dim]No changes proposed by OpenAI[/dim]")
        else:
            print("No changes proposed by OpenAI.")

    # Optionally save
    if args.apply:
        save_topology(topology_path, fixed_topology)
        if RICH_AVAILABLE:
            console.print("[green]Applied OpenAI fix to file[/green]")
        else:
            print("Applied OpenAI fix to file.")

    # Re-validate fixed topology (in-memory)
    tmp_path = topology_path
    if not args.apply:
        tmp_path = os.path.join(os.path.dirname(topology_path) or ".", ".tmp_topology.json")
        save_topology(tmp_path, fixed_topology)
    post_valid, post_errors = validate_topology_file(tmp_path, args.provider)
    if not args.apply and os.path.exists(tmp_path):
        os.remove(tmp_path)

    if RICH_AVAILABLE:
        if post_valid:
            console.print(Panel.fit("[green]Re-validation passed after OpenAI fix[/green]", border_style="green"))
        else:
            console.print(Panel.fit("[red]Re-validation still failing[/red]\n" + "\n".join(f"- {e}" for e in post_errors), border_style="red"))
    else:
        if post_valid:
            print("Re-validation passed after OpenAI fix.")
        else:
            print("Re-validation still failing:")
            for e in post_errors:
                print(f"- {e}")

    # Gemini review (independent)
    if RICH_AVAILABLE:
        console.print("\n[cyan]Requesting Gemini review...[/cyan]")
    review_ok, review, review_errors = review_with_gemini(fixed_topology, errors, post_errors, args.gemini_model)
    if review_ok:
        if RICH_AVAILABLE:
            table = Table(title="Gemini Review", border_style="dim")
            table.add_column("Field", style="cyan")
            table.add_column("Value")
            table.add_row("status", str(review.get("status", "")))
            table.add_row("critical", "\n".join(review.get("critical", [])) or "-")
            table.add_row("warnings", "\n".join(review.get("warnings", [])) or "-")
            table.add_row("notes", "\n".join(review.get("notes", [])) or "-")
            console.print(table)
        else:
            print("\nGemini review:")
            print(json.dumps(review, indent=2))
    else:
        if RICH_AVAILABLE:
            console.print(Panel.fit("[red]Gemini review failed[/red]\n" + "\n".join(review_errors), border_style="red"))
        else:
            print("Gemini review failed:")
            for e in review_errors:
                print(f"- {e}")

    # Exit code reflects validation after fix
    sys.exit(0 if post_valid else 2)


if __name__ == "__main__":
    main()
