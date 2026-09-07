"""Terminal report (spec sections 4/5/81/82/83/84). This is the primary
interface -- it should read like a serious developer tool (ESLint, Trivy,
Lighthouse CLI), not a marketing dashboard. No banners, no emoji-per-line,
no rainbow colors. Severity communicates via text labels + a restrained
color, not decoration.
"""

from __future__ import annotations

from rich.console import Console, Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from slopscan.core.models import AIInterpretation, ScanResult, Severity

_SEVERITY_STYLE = {
    Severity.LOW: "dim cyan",
    Severity.MEDIUM: "yellow",
    Severity.HIGH: "bold red",
    Severity.CRITICAL: "bold white on red",
}
_SEVERITY_LABEL = {
    Severity.LOW: "LOW ",
    Severity.MEDIUM: "MED ",
    Severity.HIGH: "HIGH",
    Severity.CRITICAL: "CRIT",
}


def _score_style(score: float) -> str:
    if score >= 70:
        return "bold red"
    if score >= 40:
        return "yellow"
    return "green"


def render_terminal(result: ScanResult, console: Console, verbose: bool = False) -> None:
    console.print()
    console.print(f"[bold]Target[/bold]  {result.target}")
    console.print()

    score_style = _score_style(result.slop_score)
    console.print(f"[bold]AI-SLOP LIKELIHOOD[/bold]   [{score_style}]{result.slop_score:>5.0f}%[/{score_style}]")
    console.print(f"[bold]CONFIDENCE[/bold]           {result.confidence:>5.0f}%")
    console.print()

    _render_breakdown(result, console)
    _render_findings(result, console, verbose=verbose)

    if result.positive_signals:
        console.print()
        console.print("[bold]Positive signals[/bold]")
        for p in result.positive_signals:
            console.print(f"  [green]+[/green] {p.description}")

    if result.ai_interpretation:
        _render_ai(result.ai_interpretation, console)

    if result.warnings:
        console.print()
        for w in result.warnings:
            console.print(f"[yellow]Warning:[/yellow] {w}")

    console.print()
    console.print("[dim]" + "─" * 60 + "[/dim]")
    console.print(
        "[dim]This score measures AI-associated design and implementation patterns.\n"
        "It does NOT prove AI authorship.[/dim]"
    )
    console.print(
        f"[dim]Scanned {result.stats.files_scanned} file(s) · "
        f"evaluated {result.stats.rules_evaluated} rules · "
        f"{result.stats.duration_seconds:.2f}s[/dim]"
    )
    console.print()


def _render_breakdown(result: ScanResult, console: Console) -> None:
    scored = [c for c in result.categories if not (c.weight == 0 and c.finding_count == 0)]
    if not scored:
        return
    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column("category", style="bold")
    table.add_column("bar")
    table.add_column("score", justify="right")
    for c in scored:
        label = c.category.value.replace("_", " ").title()
        filled = int(round(c.score / 5))
        bar = "█" * filled + "░" * (20 - filled)
        style = _score_style(c.score)
        table.add_row(label, f"[{style}]{bar}[/{style}]", f"[{style}]{c.score:>3.0f}%[/{style}]")
    console.print(Panel(table, title="Breakdown", title_align="left", border_style="dim"))


def _render_findings(result: ScanResult, console: Console, verbose: bool) -> None:
    findings = result.top_findings(limit=None if verbose else 8)
    if not findings:
        console.print("[dim]No significant findings.[/dim]")
        return

    console.print()
    console.print("[bold]Top Findings[/bold]" if not verbose else "[bold]Findings (verbose)[/bold]")
    console.print()
    for f in findings:
        style = _SEVERITY_STYLE[f.severity]
        label = _SEVERITY_LABEL[f.severity]
        header = Text()
        header.append(f"{label}  ", style=style)
        header.append(f.title, style="bold")
        console.print(header)
        ev_limit = None if verbose else 2
        for e in f.evidence_strings(limit=ev_limit):
            console.print(Padding(f"[dim]{e}[/dim]", (0, 0, 0, 6)))
        if verbose:
            console.print(Padding(
                f"[dim]rule: {f.rule_id}  ·  strength: {f.strength:.2f}  ·  confidence: {f.confidence:.2f}[/dim]",
                (0, 0, 0, 6),
            ))
            if f.false_positive_note:
                console.print(Padding(f"[dim]possible false positives: {f.false_positive_note}[/dim]", (0, 0, 0, 6)))
        console.print()

    if not verbose:
        remaining = len(result.findings) - len(findings)
        if remaining > 0:
            console.print(f"[dim]...and {remaining} more finding(s). Use --verbose to see all.[/dim]")
            console.print()

    # Evidence-first summary (spec section 54): flatten the strongest
    # evidence lines across all findings into one compact list.
    evidence_lines = []
    for f in sorted(result.findings, key=lambda f: f.strength * f.confidence, reverse=True):
        if f.evidence:
            evidence_lines.append(f.evidence[0].description)
    if evidence_lines:
        console.print("[bold]Evidence[/bold]")
        for line in evidence_lines[:8]:
            console.print(f"  - {line}")


def _render_ai(ai: AIInterpretation, console: Console) -> None:
    console.print()
    body = Group(
        Text(
            "Probabilistic interpretation of the deterministic evidence above.\n"
            "This never overrides deterministic findings.",
            style="dim italic",
        ),
        Text(""),
        Text(ai.summary),
    )
    console.print(Panel(
        body,
        title=f"AI-Assisted Interpretation ({ai.provider}/{ai.model})",
        title_align="left",
        border_style="dim",
    ))
