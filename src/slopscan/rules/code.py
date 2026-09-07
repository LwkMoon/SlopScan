"""CODE.* and remaining ACCESSIBILITY.* rules.

code.duplicate_blocks is a simple normalized-line-hashing duplicate detector
-- not a full clone-detection algorithm (that's a whole research area on its
own), but enough to catch the "same function/block copy-pasted repeatedly"
pattern that section 24/27 asks for, without pretending to be more precise
than it is.
"""

from __future__ import annotations

import re
from collections import defaultdict

from bs4 import Tag

from slopscan.core.models import Category, Evidence, Severity
from slopscan.core.source import SourceKind
from slopscan.rules.registry import DetectionResult, RuleContext, rule
from slopscan.utils.textutils import parse_html

_WS_RE = re.compile(r"\s+")
_MIN_BLOCK_LINES = 4


def _normalized_blocks(content: str, block_size: int = _MIN_BLOCK_LINES) -> list[str]:
    lines = [_WS_RE.sub(" ", ln).strip() for ln in content.splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith(("//", "#", "*", "/*"))]
    blocks = []
    for i in range(0, len(lines) - block_size + 1, block_size):
        block = "\n".join(lines[i : i + block_size])
        if len(block) > 40:  # skip trivially short/boilerplate blocks
            blocks.append(block)
    return blocks


@rule(
    id="code.duplicate_blocks",
    name="Duplicated code blocks",
    category=Category.CODE,
    severity=Severity.MEDIUM,
    description="Near-identical multi-line code blocks repeated across the codebase (normalized for whitespace).",
    why_it_matters="Copy-pasted, near-identical blocks -- as opposed to genuinely shared, extracted functions -- are common in quickly scaffolded or template/AI-generated code that wasn't refactored afterward.",
    false_positives="Boilerplate that's inherent to a framework (e.g. repeated import blocks, config files) can trigger this; --exclude can be used to skip generated or vendored directories.",
    full_effect_at=8,
)
def code_duplicate_blocks(ctx: RuleContext) -> DetectionResult | None:
    block_locations: dict[str, list[str]] = defaultdict(list)
    for f in ctx.corpus.by_kind(SourceKind.JS, SourceKind.JSX, SourceKind.PY):
        for block in _normalized_blocks(f.content):
            block_locations[block].append(f.path)
    duplicated = {b: locs for b, locs in block_locations.items() if len(locs) >= 2}
    if not duplicated:
        return None
    total_dupes = sum(len(locs) - 1 for locs in duplicated.values())
    evidence = []
    for _block, locs in sorted(duplicated.items(), key=lambda kv: -len(kv[1]))[:6]:
        unique_locs = sorted(set(locs))
        evidence.append(
            Evidence(
                description=f"Near-identical {_MIN_BLOCK_LINES}+ line block repeated in {len(locs)} location(s)",
                locator=", ".join(unique_locs[:4]),
            )
        )
    return DetectionResult(occurrences=total_dupes, evidence=evidence, confidence=0.75)


@rule(
    id="accessibility.missing_alt_text",
    name="Images missing alt text",
    category=Category.ACCESSIBILITY,
    severity=Severity.LOW,
    description="Multiple <img> elements have no alt attribute (or an empty one on a non-decorative image).",
    why_it_matters="This is a genuine accessibility gap worth fixing, but it is common in both human-written and generated code and is not treated as AI-pattern evidence -- it contributes only a very small, separate amount to the overall score.",
    false_positives="Decorative images intentionally using alt=\"\" are correct and are not counted here.",
    full_effect_at=8,
)
def accessibility_missing_alt_text(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence = []
    for f in ctx.corpus.by_kind(SourceKind.HTML):
        soup = parse_html(f.content)
        imgs = soup.find_all("img")
        missing = [img for img in imgs if isinstance(img, Tag) and img.get("alt") is None]
        if missing:
            total += len(missing)
            evidence.append(Evidence(description=f"{len(missing)} <img> without an alt attribute", locator=f.path))
    if total < 2:
        return None
    return DetectionResult(occurrences=total, evidence=evidence[:8], confidence=0.9)
