"""TYPOGRAPHY.* rules.

Per spec section 17: never flag a font just because it's popular. These
rules instead look at the *system* -- lack of hierarchy (too few distinct
sizes for the amount of content) and overused decorative treatments
(uppercase labels, generic default stacks used with no other typographic
decisions layered on top).
"""

from __future__ import annotations

from slopscan.core.models import Category, Evidence, Severity
from slopscan.core.source import SourceKind
from slopscan.rules.registry import DetectionResult, RuleContext, rule
from slopscan.utils.textutils import (
    UPPERCASE_LABEL_RE,
    count_font_sizes,
    find_font_families,
)

_GENERIC_STACKS = {"inter", "geist", "roboto", "poppins", "system-ui", "-apple-system"}


@rule(
    id="typography.weak_hierarchy",
    name="Weak typographic hierarchy",
    category=Category.TYPOGRAPHY,
    severity=Severity.LOW,
    description="Very few distinct font-size values used across a sizeable stylesheet, suggesting minimal deliberate type-scale design.",
    why_it_matters="Using a popular font is not a signal by itself. A near-total absence of a considered type scale (most text at one or two sizes despite a large stylesheet) suggests defaults were used with little typographic decision-making.",
    false_positives="Minimalist design systems can deliberately use very few sizes; this rule only fires when the stylesheet is large enough that a genuinely designed scale would be expected.",
    full_effect_at=1,
)
def typography_weak_hierarchy(ctx: RuleContext) -> DetectionResult | None:
    css_files = ctx.corpus.by_kind(SourceKind.CSS)
    total_bytes = sum(f.size_bytes for f in css_files)
    if total_bytes < 3000:  # too little CSS to judge a "system" meaningfully
        return None
    all_sizes: set[str] = set()
    for f in css_files:
        all_sizes |= count_font_sizes(f.content)
    if len(all_sizes) == 0:
        return None
    if len(all_sizes) >= 5:
        return None
    occurrences = 6 - len(all_sizes)  # 1-2 sizes -> stronger signal than 4
    evidence = [
        Evidence(
            description=f"Only {len(all_sizes)} distinct font-size value(s) found across {total_bytes // 1000}KB of CSS"
        )
    ]
    return DetectionResult(occurrences=occurrences, evidence=evidence, confidence=0.6)


@rule(
    id="typography.excessive_uppercase",
    name="Excessive uppercase micro-labels",
    category=Category.TYPOGRAPHY,
    severity=Severity.LOW,
    description="Many elements styled with text-transform: uppercase, commonly used for badge/eyebrow-style labels throughout generic templates.",
    why_it_matters="A couple of uppercase labels (e.g. section eyebrows) are completely normal. Pervasive uppercase styling across many unrelated elements is a common generic-template typography pattern.",
    false_positives="Editorial and fashion-forward brands often use uppercase as a deliberate, consistent identity choice.",
    full_effect_at=10,
)
def typography_excessive_uppercase(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence = []
    for f in ctx.corpus.by_kind(SourceKind.CSS):
        n = len(UPPERCASE_LABEL_RE.findall(f.content))
        if n:
            total += n
            evidence.append(Evidence(description=f"{n} uppercase text-transform declaration(s)", locator=f.path))
    if total < 5:
        return None
    return DetectionResult(occurrences=total, evidence=evidence[:8])


@rule(
    id="typography.generic_stack_only",
    name="Generic default font stack with no supporting decisions",
    category=Category.TYPOGRAPHY,
    severity=Severity.LOW,
    description="Only a common default UI font stack is declared, with no weight variety, custom fallback chain, or pairing decisions visible.",
    why_it_matters="Popular fonts are popular because they're good defaults -- using Inter or Geist is not evidence of anything by itself. This rule only fires when the *entire* typographic decision appears to be \"accept the default\", i.e. a single generic family with almost no weight variation.",
    false_positives="Many excellent, deliberately minimal designs use exactly one font family with restraint -- this is a very low-severity, low-weight signal for that reason.",
    full_effect_at=1,
)
def typography_generic_stack_only(ctx: RuleContext) -> DetectionResult | None:
    families: set[str] = set()
    weight_hits = 0
    css_bytes = 0
    for f in ctx.corpus.by_kind(SourceKind.CSS):
        css_bytes += f.size_bytes
        for fam in find_font_families(f.content):
            primary = fam.split(",")[0].strip().strip("\"'").lower()
            if primary:
                families.add(primary)
        weight_hits += f.content.lower().count("font-weight")
    if css_bytes < 2000 or not families:
        return None
    only_generic = families.issubset(_GENERIC_STACKS)
    if only_generic and len(families) <= 1 and weight_hits <= 2:
        return DetectionResult(
            occurrences=2,
            evidence=[
                Evidence(
                    description=f"Only a generic default stack ({', '.join(sorted(families))}) with minimal weight variation ({weight_hits} font-weight declarations) across {css_bytes // 1000}KB of CSS"
                )
            ],
            confidence=0.4,
        )
    return None
