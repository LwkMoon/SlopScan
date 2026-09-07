"""COPY.* rules -- generic marketing language and fabricated-looking social proof.

Phrase lists live in rules/data/generic_phrases.json (not hardcoded here) so
they're maintainable without touching Python -- see that file's header and
CONTRIBUTING.md for how to extend it.
"""

from __future__ import annotations

import json
from importlib import resources

from slopscan.core.models import Category, Evidence, Severity
from slopscan.core.source import SourceKind
from slopscan.rules.registry import DetectionResult, RuleContext, rule
from slopscan.utils.textutils import STAT_CLAIM_RE, count_phrase_occurrences, visible_text_from_html


def _load_phrase_db() -> dict:
    with resources.files("slopscan.rules.data").joinpath("generic_phrases.json").open(
        "r", encoding="utf-8"
    ) as fh:
        return json.load(fh)


_PHRASE_DB = _load_phrase_db()
GENERIC_PHRASES: tuple[str, ...] = tuple(_PHRASE_DB["generic_marketing_phrases"])
BUZZWORDS: tuple[str, ...] = tuple(_PHRASE_DB["buzzwords"])


def _all_visible_text(ctx: RuleContext) -> list[tuple[str, str]]:
    """(path, text) for HTML pages (rendered text) and JSX/JS string literals
    (raw source -- good enough to catch copy authored inline in components)."""
    out = []
    for f in ctx.corpus.by_kind(SourceKind.HTML):
        out.append((f.path, visible_text_from_html(f.content)))
    for f in ctx.corpus.by_kind(SourceKind.JSX, SourceKind.JS, SourceKind.MARKDOWN):
        out.append((f.path, f.content))
    return out


@rule(
    id="copy.generic_marketing",
    name="Generic AI-style marketing phrases",
    category=Category.COPY,
    severity=Severity.MEDIUM,
    description="Stock marketing phrases (e.g. \"transform your workflow\", \"the future of...\") commonly produced by AI copywriting and generic templates.",
    why_it_matters="A single generic phrase is common even in human copy. Several of these phrases appearing together, especially in headline/hero text, suggests unedited AI-generated or template copy.",
    false_positives="Short marketing copy naturally reuses common industry phrasing; context (repetition + combination with other signals) matters more than any one phrase.",
    full_effect_at=6,
)
def copy_generic_marketing(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence: list[Evidence] = []
    seen_phrases: set[str] = set()
    for path, text in _all_visible_text(ctx):
        hits = count_phrase_occurrences(text, GENERIC_PHRASES)
        if hits:
            total += sum(hits.values())
            seen_phrases.update(hits.keys())
            sample = ", ".join(f'"{p}"' for p in list(hits)[:3])
            evidence.append(Evidence(description=f"Generic phrase(s) found: {sample}", locator=path))
    if total == 0:
        return None
    evidence.insert(0, Evidence(description=f"{total} generic marketing phrase occurrence(s) across {len(seen_phrases)} distinct phrase(s)"))
    return DetectionResult(occurrences=total, evidence=evidence[:10])


@rule(
    id="copy.buzzword_density",
    name="High buzzword density",
    category=Category.COPY,
    severity=Severity.LOW,
    description="Dense concentration of vague superlatives and buzzwords (\"seamless\", \"powerful\", \"revolutionary\", \"AI-powered\", ...).",
    why_it_matters="Occasional buzzwords are normal in any marketing copy. A high concentration relative to actual content is a generic-copy signal.",
    false_positives="Technical marketing in genuinely fast-moving fields sometimes legitimately uses these words.",
    full_effect_at=12,
)
def copy_buzzword_density(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence: list[Evidence] = []
    for path, text in _all_visible_text(ctx):
        hits = count_phrase_occurrences(text, BUZZWORDS)
        n = sum(hits.values())
        if n:
            total += n
            evidence.append(Evidence(description=f"{n} buzzword occurrence(s)", locator=path))
    if total < 4:
        return None
    return DetectionResult(occurrences=total, evidence=evidence[:10])


@rule(
    id="copy.fake_social_proof",
    name="Potential generic/fabricated social-proof pattern",
    category=Category.COPY,
    severity=Severity.LOW,
    description="Round-number user/customer/satisfaction statistics presented without visible sourcing (e.g. \"10,000+ users\", \"99.9% satisfaction\").",
    why_it_matters="SlopScan cannot verify whether such numbers are real or fabricated. Their presence -- especially several at once, unlinked to any source -- is a pattern commonly seen in generic template copy and AI-generated landing pages.",
    false_positives="Legitimate, sourced statistics (e.g. linked to a case study or press release) are common and should not be penalized; this rule cannot distinguish sourced from unsourced claims and keeps its confidence capped accordingly.",
    full_effect_at=4,
)
def copy_fake_social_proof(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence: list[Evidence] = []
    for path, text in _all_visible_text(ctx):
        matches = STAT_CLAIM_RE.findall(text)
        if matches:
            total += len(matches)
            evidence.append(Evidence(description=f"{len(matches)} round-number statistic claim(s)", locator=path))
    if total == 0:
        return None
    evidence.insert(
        0,
        Evidence(
            description=(
                f"{total} statistic-style claim(s) detected without visible sourcing in the scanned content -- "
                "this is reported as a pattern, not an accusation of fabrication"
            )
        ),
    )
    # This rule is inherently uncertain -- cap confidence explicitly.
    return DetectionResult(occurrences=total, evidence=evidence[:8], confidence=0.55)
