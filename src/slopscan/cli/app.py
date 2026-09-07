"""The `slopscan` CLI (spec section 48-50).

Commands:
    slopscan analyze <target>   Run a scan (the main command)
    slopscan rules list         List all registered rules
    slopscan rules show <id>    Explain one rule
    slopscan config             Show effective configuration
    slopscan doctor             Environment/connectivity sanity check
    slopscan version            Print version

Exit codes (spec section 50): 0 success, 1 threshold exceeded,
2 invalid usage, 3 target error, 4 configuration error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from slopscan import __version__
from slopscan.cli.output import write_report
from slopscan.core.config import ScanConfig, load_config
from slopscan.core.models import TargetType
from slopscan.core.scanner import TargetError, scan
from slopscan.rules import all_rules, get_rule
from slopscan.rules.registry import rules_by_category

app = typer.Typer(
    name="slopscan",
    help="Scan a website, repository, or codebase for AI-associated and generic-template patterns.",
    add_completion=True,
    no_args_is_help=True,
)
rules_app = typer.Typer(help="Inspect the rules SlopScan evaluates.")
app.add_typer(rules_app, name="rules")

EXIT_OK = 0
EXIT_THRESHOLD_EXCEEDED = 1
EXIT_INVALID_USAGE = 2
EXIT_TARGET_ERROR = 3
EXIT_CONFIG_ERROR = 4


def _console(no_color: bool, quiet: bool) -> Console:
    return Console(no_color=no_color, quiet=quiet, highlight=False)


@app.command()
def analyze(
    target: str = typer.Argument(..., help="URL, GitHub repo URL, local directory, or .zip archive."),
    target_type: Optional[str] = typer.Option(
        None, "--type", help="Force target type: url, github, local_dir, archive (auto-detected by default)."
    ),
    fmt: str = typer.Option("terminal", "--format", "-f", help="Output format: terminal, json, markdown, html."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write the report to a file instead of stdout."),
    ai: bool = typer.Option(False, "--ai", help="Enable optional AI-assisted semantic interpretation."),
    ai_provider: Optional[str] = typer.Option(None, "--ai-provider", help="AI provider: anthropic, openai, google."),
    ai_model: Optional[str] = typer.Option(None, "--ai-model", help="Override the provider's default model."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full evidence and per-finding detail."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress all but the final report."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable terminal colors."),
    timeout: Optional[float] = typer.Option(None, "--timeout", help="Network timeout in seconds (URL/GitHub targets)."),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", help="Max pages to fetch when --crawl is set."),
    crawl: bool = typer.Option(False, "--crawl", help="Follow same-origin links for deeper site analysis (URL targets)."),
    exclude: list[str] = typer.Option([], "--exclude", help="Additional ignore pattern(s); repeatable."),
    severity: Optional[str] = typer.Option(None, "--severity", help="Only show findings at or above this severity (low/medium/high/critical)."),
    rule_filter: list[str] = typer.Option([], "--rule", help="Only evaluate these rule id(s); repeatable."),
    fail_under: Optional[int] = typer.Option(None, "--fail-under", help="Exit with code 1 if the score is >= this threshold (CI usage)."),
) -> None:
    """Analyze TARGET and report AI-slop likelihood with evidence."""
    console = _console(no_color=no_color, quiet=quiet)

    if fmt not in ("terminal", "json", "markdown", "html"):
        console.print(f"[red]Error:[/red] unknown --format {fmt!r}. Use terminal, json, markdown, or html.")
        raise typer.Exit(EXIT_INVALID_USAGE)

    try:
        resolved_type = TargetType(target_type) if target_type else None
    except ValueError:
        console.print(f"[red]Error:[/red] unknown --type {target_type!r}.")
        raise typer.Exit(EXIT_INVALID_USAGE) from None

    try:
        config: ScanConfig = load_config()
    except Exception as exc:  # noqa: BLE001 - config errors should never traceback to the user
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(EXIT_CONFIG_ERROR) from exc

    if timeout is not None:
        config.timeout = timeout
    if max_pages is not None:
        config.max_pages = max_pages
    if crawl:
        config.crawl = crawl
    if exclude:
        config.exclude.extend(exclude)
    if fail_under is not None:
        config.score.fail_under = fail_under
    if ai:
        config.ai.enabled = True
    if ai_provider:
        config.ai.provider = ai_provider
    if ai_model:
        config.ai.model = ai_model

    if not quiet and fmt == "terminal":
        console.print(f"[dim]Scanning {target}...[/dim]")

    try:
        result = scan(target, config=config, target_type=resolved_type)
    except TargetError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(EXIT_TARGET_ERROR) from exc
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Unexpected error:[/red] {exc}")
        if verbose:
            console.print_exception()
        raise typer.Exit(EXIT_TARGET_ERROR) from exc

    if rule_filter:
        allowed = set(rule_filter)
        result.findings = [f for f in result.findings if f.rule_id in allowed]
    if severity:
        from slopscan.core.models import Severity

        try:
            min_order = Severity(severity.lower()).order
        except ValueError:
            console.print(f"[red]Error:[/red] unknown --severity {severity!r}.")
            raise typer.Exit(EXIT_INVALID_USAGE) from None
        result.findings = [f for f in result.findings if f.severity.order >= min_order]

    if config.ai.enabled:
        _apply_ai_interpretation(result, config, console)

    write_report(result, fmt=fmt, output=output, console=console, verbose=verbose)

    threshold = config.score.fail_under
    if threshold is not None and result.slop_score >= threshold:
        if not quiet:
            console.print(f"[red]Score {result.slop_score:.0f}% >= --fail-under {threshold} threshold.[/red]")
        raise typer.Exit(EXIT_THRESHOLD_EXCEEDED)
    raise typer.Exit(EXIT_OK)


def _apply_ai_interpretation(result, config: ScanConfig, console: Console) -> None:
    from slopscan.ai.pipeline import AIProviderError, run_ai_interpretation

    api_key = config.ai.api_key
    if not api_key:
        console.print(
            "[yellow]--ai was set but no API key is configured.[/yellow] "
            "Set SLOPSCAN_AI_API_KEY and try again. Continuing with deterministic results only."
        )
        return
    try:
        result.ai_interpretation = run_ai_interpretation(
            result, provider_id=config.ai.provider, api_key=api_key, model=config.ai.model
        )
    except AIProviderError as exc:
        console.print(f"[yellow]AI interpretation skipped:[/yellow] {exc}")


@rules_app.command("list")
def rules_list() -> None:
    """List all rules SlopScan currently evaluates, grouped by category."""
    from rich.console import Console as RichConsole

    console = RichConsole(highlight=False)
    from slopscan.core.models import Category

    for category in Category:
        rules = rules_by_category(category)
        if not rules:
            continue
        console.print(f"\n[bold]{category.value.upper()}[/bold]")
        for r in rules:
            console.print(f"  {r.id:<38} [dim]{r.base_severity.value}[/dim]")


@rules_app.command("show")
def rules_show(rule_id: str = typer.Argument(..., help="Rule id, e.g. visual.gradient.overuse")) -> None:
    """Show full detail for one rule."""
    console = Console(highlight=False)
    r = get_rule(rule_id)
    if r is None:
        console.print(f"[red]No such rule:[/red] {rule_id}")
        console.print("[dim]Run `slopscan rules list` to see available rule ids.[/dim]")
        raise typer.Exit(EXIT_INVALID_USAGE)

    console.print(f"\n[bold]Rule:[/bold] {r.id}")
    console.print(f"\n[bold]Category:[/bold]\n{r.category.value.title()}")
    console.print(f"\n[bold]Severity (ceiling):[/bold]\n{r.base_severity.value.title()}")
    console.print(f"\n[bold]Description:[/bold]\n{r.description}")
    console.print(f"\n[bold]Why it matters:[/bold]\n{r.why_it_matters}")
    console.print(f"\n[bold]False positives:[/bold]\n{r.false_positives}\n")


@app.command()
def config() -> None:
    """Show the effective configuration (defaults + .slopscan.toml + env)."""
    console = Console(highlight=False)
    cfg = load_config()
    console.print(cfg.model_dump_json(indent=2, exclude={"ai": {"api_key"}}))


@app.command()
def doctor() -> None:
    """Check that SlopScan's environment is set up correctly."""
    console = Console(highlight=False)
    console.print("[bold]SlopScan doctor[/bold]\n")

    import importlib.util

    checks: list[tuple[str, bool, str]] = []
    for mod in ("httpx", "bs4", "lxml", "rich", "pydantic", "typer"):
        found = importlib.util.find_spec(mod) is not None
        checks.append((f"dependency: {mod}", found, "" if found else "not installed"))

    import os

    has_ai_key = bool(os.environ.get("SLOPSCAN_AI_API_KEY"))
    checks.append(("SLOPSCAN_AI_API_KEY set (optional)", has_ai_key, "AI mode unavailable without it" if not has_ai_key else ""))

    playwright_available = importlib.util.find_spec("playwright") is not None
    checks.append(("playwright installed (optional, browser rendering)", playwright_available, "static HTML/CSS analysis still works without it"))

    all_ok = True
    for name, ok, note in checks:
        icon = "[green]OK[/green]  " if ok else "[yellow]--[/yellow]  "
        line = f"{icon}{name}"
        if note:
            line += f"  [dim]({note})[/dim]"
        console.print(line)
        if not ok and "optional" not in name.lower():
            all_ok = False

    console.print()
    console.print(f"{len(all_rules())} rules registered.")
    if all_ok:
        console.print("[green]Environment looks good.[/green]")
    else:
        console.print("[yellow]Some required dependencies are missing.[/yellow]")
        raise typer.Exit(EXIT_CONFIG_ERROR)


@app.command()
def version() -> None:
    """Print the SlopScan version."""
    typer.echo(f"slopscan {__version__}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
