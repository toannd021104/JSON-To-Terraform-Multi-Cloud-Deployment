#!/usr/bin/env python3
"""
Dual-AI topology fixer and reviewer

Flow (Rule-based Gate + Dual-AI):
- Validate topology.json with existing rules.
- If errors, ask OpenAI (ChatGPT) to propose a fix.
- Show diff preview (no changes written yet).
- Ask Gemini to review the fixed topology (advisory, not blocking).
- Re-validate the fixed topology in memory (mandatory gate).
- Apply if rule-based re-validation passes; prompt if review is "fail"
  or --auto-apply is not set.

This keeps deterministic validation as the final gate while still
leveraging a second AI for warnings and intent checks.
"""
import argparse
import json
import os
import sys
import difflib
from typing import Any, Dict, List, Optional, Tuple

# Thêm root để import theo cấu trúc module mới
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT_DIR)
from validate.topology_schema import validate_topology_file  # noqa: E402

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
        "You are a topology fixer. Preserve intent and structure, make minimal changes.\n"
        "Do NOT add/remove instances, networks, or routers. Do NOT rename instance/router names.\n"
        "Only change values needed to resolve listed errors. Do not delete existing keys.\n"
        "If a required key is missing, add it with a minimal valid value.\n"
        "\n"
        "Expected keys (structure summary):\n"
        "- root: instances, networks, routers\n"
        "- instance: name, image, cpu, ram, disk, networks, keypair, security_groups,\n"
        "  floating_ip, floating_ip_pool, cloud_init\n"
        "- instance.networks[]: name, ip\n"
        "- network: name, cidr, gateway_ip, enable_dhcp, pool\n"
        "- router: name, networks, external, routes\n"
        "- router.networks[]: name, ip\n"
        "- routes[]: destination, nexthop\n"
        "\n"
        "Rules:\n"
        "1) IPs must belong to their network CIDR; no duplicates within the same network.\n"
        "2) gateway_ip must match router interface IP for that network (if gateway_ip is set).\n"
        "3) All referenced networks must exist (fix typos; do not create new networks).\n"
        "4) Routes must have reachable nexthop from router interfaces.\n"
        "5) floating_ip can be true/false or explicit IPv4 string.\n"
        "\n"
        "Example structure (do not copy values):\n"
        "{\n"
        "  \"instances\": [\n"
        "    {\"name\": \"<vm>\", \"image\": \"<img>\", \"cpu\": 1, \"ram\": 1, \"disk\": 10,\n"
        "     \"networks\": [{\"name\": \"<net>\", \"ip\": \"<ip>\"}]}\n"
        "  ],\n"
        "  \"networks\": [{\"name\": \"<net>\", \"cidr\": \"<cidr>\", \"gateway_ip\": \"<gw>\"}],\n"
        "  \"routers\": [{\"name\": \"<r>\", \"external\": true,\n"
        "    \"networks\": [{\"name\": \"<net>\", \"ip\": \"<gw>\"}],\n"
        "    \"routes\": [{\"destination\": \"<cidr>\", \"nexthop\": \"<ip>\"}]}\n"
        "  ]\n"
        "}\n"
        "\n"
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
def review_with_gemini(topology: Dict[str, Any], original_errors: List[str], post_validate_errors: Optional[List[str]], model_name: str) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Ask Gemini to review fixed topology and return structured result (advisory)."""
    try:
        import google.generativeai as genai
    except ImportError:
        return False, {}, ["google-generativeai not installed (pip install google-generativeai)"]

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return False, {}, ["GEMINI_API_KEY not set"]

    review_prompt = (
        "You are a reviewer for topology fixes. Do NOT fix or rewrite.\n"
        "Return JSON only with keys: {status: pass|warn|fail, critical:[], warnings:[], notes:[]}.\n"
        "Check for:\n"
        "- Drift from intent: added/removed instances/networks/routers, renamed instance/router.\n"
        "- Changes unrelated to listed errors.\n"
        "- CIDR/IP correctness, duplicate IPs, gateway vs router IP alignment.\n"
        "- Route destination CIDR validity and nexthop reachability.\n"
        "Be concise."
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

    revalidation_block = "NOT RUN YET" if post_validate_errors is None else (
        "\n".join(f"- {e}" for e in post_validate_errors) if post_validate_errors else "None"
    )
    user_prompt = (
        f"Original validation errors:\n" + "\n".join(f"- {e}" for e in original_errors) +
        f"\n\nRe-validation errors after fix:\n{revalidation_block}" +
        f"\n\nFixed topology JSON:\n{json.dumps(topology, indent=2)}" +
        "\n\nIMPORTANT: Return ONLY valid JSON with this exact structure: {\"status\": \"pass\", \"critical\": [], \"warnings\": [], \"notes\": []}"
    )
    try:
        res = model.generate_content(user_prompt)
        text = (res.text or "").strip()
        
        # Handle empty response
        if not text:
            return True, {"status": "pass", "critical": [], "warnings": [], "notes": ["Gemini returned empty response, assuming pass"]}, []
        
        # Try to extract JSON from response (may be wrapped in markdown)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        # Try to parse JSON
        try:
            review = json.loads(text)
        except json.JSONDecodeError:
            # If can't parse, check if it looks like approval
            text_lower = text.lower()
            if "pass" in text_lower or "valid" in text_lower or "correct" in text_lower:
                return True, {"status": "pass", "critical": [], "warnings": [], "notes": [text[:200]]}, []
            elif "fail" in text_lower or "error" in text_lower or "invalid" in text_lower:
                return True, {"status": "fail", "critical": [text[:200]], "warnings": [], "notes": []}, []
            else:
                return True, {"status": "warn", "critical": [], "warnings": [], "notes": [text[:200]]}, []
        
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
    parser.add_argument("--auto-apply", action="store_true", help="Auto-apply if both validations pass (skip user confirmation)")
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

    # Gemini review (independent check BEFORE applying)
    if RICH_AVAILABLE:
        console.print("\n[cyan]Requesting Gemini review...[/cyan]")
    review_ok, review, review_errors = review_with_gemini(fixed_topology, errors, None, args.gemini_model)
    
    review_status = "unavailable"
    if review_ok:
        review_status = (review.get("status") or "warn").lower()
        
        if RICH_AVAILABLE:
            table = Table(title="Gemini Review", border_style="dim")
            table.add_column("Field", style="cyan")
            table.add_column("Value")
            status_color = "green" if review_status == "pass" else ("yellow" if review_status == "warn" else "red")
            table.add_row("status", f"[{status_color}]{review_status.upper()}[/{status_color}]")
            table.add_row("critical", "\n".join(review.get("critical", [])) or "-")
            table.add_row("warnings", "\n".join(review.get("warnings", [])) or "-")
            table.add_row("notes", "\n".join(review.get("notes", [])) or "-")
            console.print(table)
        else:
            print("\nGemini review:")
            print(json.dumps(review, indent=2))
    else:
        if RICH_AVAILABLE:
            console.print(Panel.fit("[yellow]Gemini review skipped[/yellow]\n" + "\n".join(review_errors), border_style="yellow"))
        else:
            print("Gemini review skipped:")
            for e in review_errors:
                print(f"- {e}")

    # Re-validate fixed topology (in-memory, BEFORE applying)
    tmp_path = os.path.join(os.path.dirname(topology_path) or ".", ".tmp_topology.json")
    save_topology(tmp_path, fixed_topology)
    post_valid, post_errors = validate_topology_file(tmp_path, args.provider)
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    if post_valid:
        if RICH_AVAILABLE:
            console.print(Panel.fit("[green]✓ Re-validation passed after OpenAI fix[/green]", border_style="green"))
        else:
            print("✓ Re-validation passed after OpenAI fix.")
    else:
        if RICH_AVAILABLE:
            console.print(Panel.fit("[red]✗ Re-validation still failing[/red]\n" + "\n".join(f"- {e}" for e in post_errors), border_style="red"))
        else:
            print("✗ Re-validation still failing:")
            for e in post_errors:
                print(f"- {e}")
        sys.exit(2)

    if RICH_AVAILABLE:
        console.print("\n" + "─" * 50)
        console.print("[bold]Decision Summary:[/bold]")
        console.print("  Re-validation: [green]✓ PASS[/green]")
        console.print(f"  Gemini Review: {review_status.upper()}")
        console.print("─" * 50)
    else:
        print("\n" + "─" * 50)
        print("Decision Summary:")
        print("  Re-validation: ✓ PASS")
        print(f"  Gemini Review: {review_status.upper()}")
        print("─" * 50)

    review_blocks_auto = review_status == "fail"
    should_apply = False

    if args.auto_apply and not review_blocks_auto:
        should_apply = True
        if RICH_AVAILABLE:
            console.print("[cyan]Auto-applying (--auto-apply flag set)...[/cyan]")
    else:
        if review_blocks_auto and RICH_AVAILABLE:
            console.print("\n[bold yellow]Gemini flagged issues (status=FAIL). Review before applying.[/bold yellow]")
        elif RICH_AVAILABLE:
            console.print("\n[bold yellow]Re-validation passed. Apply changes?[/bold yellow]")
        response = input("Apply fixed topology to file? (y/N): ").strip().lower()
        should_apply = response in ("y", "yes")

    if should_apply:
        save_topology(topology_path, fixed_topology)
        if RICH_AVAILABLE:
            console.print(Panel.fit("[green]✓ Applied OpenAI fix to file[/green]", border_style="green"))
        else:
            print("✓ Applied OpenAI fix to file.")
        sys.exit(0)
    else:
        if RICH_AVAILABLE:
            console.print("[dim]Changes not applied (user declined).[/dim]")
        else:
            print("Changes not applied (user declined).")
        sys.exit(0)


if __name__ == "__main__":
    main()
