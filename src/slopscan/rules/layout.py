"""LAYOUT / TEMPLATE.* and REPETITION rules -- DOM structure analysis.

These rules use BeautifulSoup because they genuinely need tree structure
(section ordering, sibling similarity, nesting) rather than plain text
matching. They only run against HTML sources (rendered pages, or .html
files in a repo) -- JSX component repetition is handled separately in
rules/components.py since it needs source-level heuristics instead.
"""

from __future__ import annotations

from collections import Counter

from bs4 import Tag

from slopscan.core.models import Category, Evidence, Severity
from slopscan.core.source import SourceKind
from slopscan.rules.registry import DetectionResult, RuleContext, rule
from slopscan.utils.textutils import SECTION_KEYWORDS, parse_html


def _section_signature(html: str) -> list[str]:
    """Best-effort ordered list of recognized page-section types, based on
    element id/class/tag naming. Heuristic, not exhaustive on purpose --
    this only needs to catch the *very common* generic sequence, not every
    possible layout."""
    soup = parse_html(html)
    candidates: list[tuple[int, str]] = []
    for tag in soup.find_all(["section", "header", "footer", "nav", "div"]):
        if not isinstance(tag, Tag):
            continue
        classes_raw: object = tag.get("class") or []
        classes = classes_raw if isinstance(classes_raw, list) else [classes_raw]
        hint = " ".join(
            filter(
                None,
                [tag.name, str(tag.get("id", "")), " ".join(str(c) for c in classes)],
            )
        ).lower()
        for label, keywords in SECTION_KEYWORDS.items():
            if any(kw in hint for kw in keywords):
                # position = document order via sourceline if available, else insertion order
                pos = tag.sourceline or len(candidates)
                candidates.append((pos, label))
                break
    candidates.sort(key=lambda c: c[0])
    # Collapse consecutive duplicates (e.g. multiple divs matching "features")
    sig: list[str] = []
    for _, label in candidates:
        if not sig or sig[-1] != label:
            sig.append(label)
    return sig


_GENERIC_SEQUENCE = ["navbar", "hero", "features", "logos", "screenshot", "stats", "testimonials", "pricing", "faq", "cta", "footer"]


def _sequence_similarity(found: list[str]) -> float:
    """Fraction of the canonical generic sequence found, in order (LCS-based)."""
    if not found:
        return 0.0
    # Longest common subsequence length between found and canonical order
    a, b = found, _GENERIC_SEQUENCE
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[len(a)][len(b)]
    return lcs / len(_GENERIC_SEQUENCE)


@rule(
    id="template.generic_saas_sequence",
    name="Generic SaaS page structure",
    category=Category.TEMPLATE,
    severity=Severity.HIGH,
    description="Page section order closely matches the extremely common navbar -> hero -> features -> logos -> stats -> testimonials -> pricing -> FAQ -> CTA -> footer template.",
    why_it_matters="A hero section or a pricing table alone proves nothing. Matching most of this specific sequence, in this specific order, without other page-specific structure is a strong generic-template signal.",
    false_positives="Legitimate SaaS marketing sites also commonly use this structure deliberately and effectively; this rule measures similarity to the template, not correctness of the choice.",
    full_effect_at=1,  # this is a match/no-match structural signal, not a repeated-count one
)
def template_generic_saas_sequence(ctx: RuleContext) -> DetectionResult | None:
    best_sim = 0.0
    best_path = None
    best_sig: list[str] = []
    for f in ctx.corpus.by_kind(SourceKind.HTML):
        sig = _section_signature(f.content)
        if len(sig) < 4:
            continue
        sim = _sequence_similarity(sig)
        if sim > best_sim:
            best_sim, best_path, best_sig = sim, f.path, sig
    if best_sim < 0.55:
        return None
    # Map similarity (0.55-1.0) onto an occurrence-like scale so the shared
    # diminishing-returns curve still applies sensibly (near-full match saturates).
    occurrences = round(best_sim * 12)
    evidence = [
        Evidence(
            description=f"Detected sequence: {' -> '.join(best_sig)} ({round(best_sim * 100)}% match to the generic template order)",
            locator=best_path,
        )
    ]
    return DetectionResult(occurrences=occurrences, evidence=evidence, confidence=0.8)


def _card_like_elements(soup) -> list[Tag]:
    out = []
    for tag in soup.find_all(["div", "article", "li"]):
        classes = " ".join(tag.get("class", []) or []).lower()
        if "card" in classes or "feature" in classes or tag.name == "article":
            out.append(tag)
    return out


def _structural_shape(tag: Tag) -> tuple:
    """A coarse structural fingerprint: child tag sequence + whether it has
    an icon-like element, heading, paragraph, and button -- used to group
    'the same card, repeated' without requiring byte-identical HTML."""
    child_tags = tuple(c.name for c in tag.find_all(recursive=False) if isinstance(c, Tag))
    has_icon = bool(tag.find(["svg", "img"]) or "icon" in (tag.get("class") or []))
    has_heading = bool(tag.find(["h1", "h2", "h3", "h4"]))
    has_para = bool(tag.find("p"))
    has_button = bool(tag.find(["button", "a"]))
    return (child_tags, has_icon, has_heading, has_para, has_button)


@rule(
    id="layout.repetitive_cards",
    name="Repetitive card architecture",
    category=Category.REPETITION,
    severity=Severity.HIGH,
    description="Multiple card elements share an (near-)identical internal structure -- e.g. icon, heading, description, button repeated across many cards.",
    why_it_matters="Three cards in a features section is completely normal. Nine or more cards that are all structurally identical (not just visually consistent) suggests templated generation rather than distinct, purpose-built content.",
    false_positives="A well-designed, genuinely reusable card component used consistently is good engineering, not a defect -- this rule looks at *quantity* of near-identical instances, not the existence of a shared component.",
    full_effect_at=10,
)
def layout_repetitive_cards(ctx: RuleContext) -> DetectionResult | None:
    shape_counts: Counter = Counter()
    shape_examples: dict[tuple, str] = {}
    for f in ctx.corpus.by_kind(SourceKind.HTML):
        soup = parse_html(f.content)
        for card in _card_like_elements(soup):
            shape = _structural_shape(card)
            if not (shape[2] or shape[3]):  # skip cards with neither heading nor paragraph -- too generic to compare
                continue
            shape_counts[shape] += 1
            shape_examples.setdefault(shape, f.path)
    if not shape_counts:
        return None
    shape, count = shape_counts.most_common(1)[0]
    if count < 4:
        return None
    evidence = [
        Evidence(
            description=f"{count} visually/structurally similar card elements detected (icon={shape[1]}, heading={shape[2]}, paragraph={shape[3]}, button={shape[4]})",
            locator=shape_examples.get(shape),
        )
    ]
    return DetectionResult(occurrences=count, evidence=evidence, confidence=0.85)


@rule(
    id="layout.card_in_card",
    name="Card-inside-card nesting",
    category=Category.REPETITION,
    severity=Severity.LOW,
    description="Card-like containers nested directly inside other card-like containers, repeated across the page.",
    why_it_matters="Occasional nested cards can be intentional (e.g. a summary tile inside a panel). Widespread card-in-card nesting is typically a sign of compositional templates stacking pre-made components rather than a deliberate layout.",
    false_positives="Dashboards and admin UIs sometimes legitimately nest cards for grouping.",
    full_effect_at=6,
)
def layout_card_in_card(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence: list[Evidence] = []
    for f in ctx.corpus.by_kind(SourceKind.HTML):
        soup = parse_html(f.content)
        cards = _card_like_elements(soup)
        card_set = set(id(c) for c in cards)
        nested = 0
        for card in cards:
            for child in card.find_all(["div", "article"], recursive=True):
                if id(child) in card_set:
                    nested += 1
        if nested:
            total += nested
            evidence.append(Evidence(description=f"{nested} nested card-in-card instance(s)", locator=f.path))
    if total < 2:
        return None
    return DetectionResult(occurrences=total, evidence=evidence[:8], confidence=0.7)
