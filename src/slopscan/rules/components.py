"""COMPONENTS.* rules -- React/Vue/Svelte-ish component architecture heuristics.

These operate on raw JSX/TS source text via regex rather than a real parser.
That's a deliberate trade-off: a full JS/TSX AST (tree-sitter, babel, etc.)
would be more precise but is a much heavier dependency for a CLI whose goal
is pattern *frequency*, not refactor-grade correctness. The regexes here are
intentionally conservative -- they undercount rather than risk false
positives on unrelated code.
"""

from __future__ import annotations

import re
from collections import Counter

from slopscan.core.models import Category, Evidence, Severity
from slopscan.core.source import SourceKind
from slopscan.rules.registry import DetectionResult, RuleContext, rule

JSX_TAG_RE = re.compile(r"<([A-Z][A-Za-z0-9_]*)\b[^>]*/?>")
ICON_IMPORT_RE = re.compile(r"from\s+[\"']((?:lucide|@heroicons|react-icons)[^\"']*)[\"']", re.IGNORECASE)


@rule(
    id="components.repeated_jsx_tags",
    name="Highly repeated identical component tags",
    category=Category.COMPONENTS,
    severity=Severity.MEDIUM,
    description="The same custom component tag (e.g. <FeatureCard />) appears a large number of times with no other component diversity nearby.",
    why_it_matters="Using a reusable component several times (<FeatureCard /> x3) is normal, good engineering. Dozens of uses of the same generic-sounding component, with little else in the file, suggests templated generation of near-identical sections rather than distinct, purpose-built UI.",
    false_positives="Data-driven lists (e.g. mapping over an array to render N genuinely distinct items) legitimately repeat one component many times -- this rule cannot fully distinguish that from templated repetition and keeps severity capped at MEDIUM for this reason.",
    full_effect_at=14,
)
def components_repeated_jsx_tags(ctx: RuleContext) -> DetectionResult | None:
    tag_counts: Counter = Counter()
    tag_examples: dict[str, str] = {}
    generic_names = ("card", "feature", "item", "box", "section", "block", "tile")
    for f in ctx.corpus.by_kind(SourceKind.JSX):
        for tag in JSX_TAG_RE.findall(f.content):
            tag_counts[tag] += 1
            tag_examples.setdefault(tag, f.path)
    if not tag_counts:
        return None
    # Only consider tags whose name suggests a generic repeatable unit --
    # repeated <Layout /> or <Provider /> is normal app structure, not slop.
    candidates = {
        t: c for t, c in tag_counts.items() if any(g in t.lower() for g in generic_names) and c >= 6
    }
    if not candidates:
        return None
    tag, count = max(candidates.items(), key=lambda kv: kv[1])
    evidence = [
        Evidence(description=f"<{tag} /> used {count} times across scanned components", locator=tag_examples.get(tag))
    ]
    return DetectionResult(occurrences=count, evidence=evidence, confidence=0.6)


@rule(
    id="components.icon_heading_description",
    name="Repeated icon + heading + description block",
    category=Category.REPETITION,
    severity=Severity.MEDIUM,
    description="The icon -> heading -> short description structure recurs many times across component source files.",
    why_it_matters="This is one of the most common generic-AI/template feature-list structures. A few instances are completely normal (that's just a feature list); many nearly identical instances with generic icon imports is a stronger combined signal.",
    false_positives="Icon libraries (lucide-react, heroicons, etc.) are extremely common and legitimate -- this rule requires the *structural repetition*, not just the import, to fire.",
    full_effect_at=8,
)
def components_icon_heading_description(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence: list[Evidence] = []
    heading_re = re.compile(r"<h[1-4][^>]*>", re.IGNORECASE)
    for f in ctx.corpus.by_kind(SourceKind.JSX, SourceKind.HTML):
        icon_uses = len(re.findall(r"<(svg|Icon\w*|[A-Z]\w*Icon)\b", f.content))
        heading_uses = len(heading_re.findall(f.content))
        para_uses = len(re.findall(r"<p\b", f.content, re.IGNORECASE))
        # crude co-occurrence proxy: the minimum of the three roughly bounds
        # how many "icon+heading+paragraph" units could exist in this file
        n = min(icon_uses, heading_uses, para_uses)
        if n >= 3:
            total += n
            evidence.append(
                Evidence(
                    description=f"~{n} icon+heading+description block(s) (icons={icon_uses}, headings={heading_uses}, paragraphs={para_uses})",
                    locator=f.path,
                )
            )
    if total < 3:
        return None
    return DetectionResult(occurrences=total, evidence=evidence[:8], confidence=0.55)
