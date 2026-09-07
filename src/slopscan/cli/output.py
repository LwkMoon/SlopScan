from __future__ import annotations

from pathlib import Path

from rich.console import Console

from slopscan.core.models import ScanResult
from slopscan.reports import render_html, render_json, render_markdown, render_terminal


def write_report(
    result: ScanResult,
    fmt: str,
    output: Path | None,
    console: Console,
    verbose: bool = False,
) -> None:
    if fmt == "terminal":
        render_terminal(result, console, verbose=verbose)
        return

    if fmt == "json":
        text = render_json(result)
    elif fmt == "markdown":
        text = render_markdown(result)
    elif fmt == "html":
        text = render_html(result)
    else:  # pragma: no cover - guarded earlier in cli/app.py
        raise ValueError(f"Unknown format: {fmt}")

    if output:
        output.write_text(text, encoding="utf-8")
        console.print(f"[dim]Report written to {output}[/dim]")
    else:
        # Machine-readable formats go straight to stdout, undecorated.
        print(text)
