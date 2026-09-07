"""The scoring engine.

Design goals (see docs/scoring.md for the full writeup):

1. No linear "violation counting". Each rule already turns raw occurrence
   counts into a diminishing-returns `strength` (0..1) in rules.registry.
2. No double counting within a category. Related rules firing together
   (e.g. gradient + glow + glassmorphism, all VISUAL) are combined with a
   noisy-OR, not summed: combined = 1 - product(1 - severity_i * strength_i).
   This means five weak-to-moderate signals in the same family push the
   category score up, but nowhere near as much as five independent full-
   strength signals would if they were just added together.
3. Category weights (configurable) turn category scores into one overall
   score.
4. ACCESSIBILITY is tracked and reported, but excluded from the slop score
   entirely -- accessibility gaps are not AI-authorship evidence (spec
   section 57).
5. Confidence is a *separate* number from the score, based on how much
   evidence and how complete the scan was -- not on how high the score is.
"""

from __future__ import annotations

from dataclasses import dataclass

from slopscan.core.models import Category, CategoryScore, Finding, ScanStats

DEFAULT_CATEGORY_WEIGHTS: dict[Category, float] = {
    Category.VISUAL: 20.0,
    Category.CODE: 15.0,
    Category.TEMPLATE: 15.0,
    Category.COPY: 10.0,
    Category.REPETITION: 10.0,
    Category.TYPOGRAPHY: 5.0,
    Category.ANIMATION: 5.0,
    Category.COMPONENTS: 10.0,
    Category.OTHER: 10.0,
    # ACCESSIBILITY is intentionally absent: it is reported, never scored
    # into the slop-likelihood number. See module docstring point 4.
}

_SEVERITY_MULTIPLIER = {"low": 0.45, "medium": 0.7, "high": 0.9, "critical": 1.0}


@dataclass
class ScoringResult:
    slop_score: float
    confidence: float
    category_scores: list[CategoryScore]
    accessibility_score: float | None


def _noisy_or_combine(activations: list[float]) -> float:
    """1 - product(1 - a_i), the standard way to combine independent-ish
    probabilities without linear stacking. Clamped defensively."""
    if not activations:
        return 0.0
    prob_none = 1.0
    for a in activations:
        a = max(0.0, min(1.0, a))
        prob_none *= 1.0 - a
    return 1.0 - prob_none


def score_category(findings: list[Finding]) -> tuple[float, list[str]]:
    """Combine a category's findings into a 0-100 score plus the rule ids
    that drove it (for CategoryScore.top_rule_ids / report summaries)."""
    if not findings:
        return 0.0, []
    activations = []
    for f in findings:
        mult = _SEVERITY_MULTIPLIER.get(f.severity.value, 0.6)
        activations.append(f.strength * f.confidence * mult)
    combined = _noisy_or_combine(activations)
    ranked = sorted(findings, key=lambda f: f.strength * f.confidence, reverse=True)
    top_ids = [f.rule_id for f in ranked[:3]]
    return round(combined * 100, 1), top_ids


def compute_confidence(
    findings: list[Finding],
    categories_with_signal: int,
    total_categories: int,
    stats: ScanStats,
) -> float:
    """How much to trust the score, independent of what the score is.

    Combines:
    - coverage: how many distinct rule *categories* fired (a score built
      from one category's evidence is less trustworthy than one
      corroborated across several independent categories)
    - volume: how many files/bytes were actually scanned
    - completeness: was this a full static-source scan, or a smaller
      surface like a single fetched HTML page with no linked assets?
    - evidence quality: average per-finding confidence
    """
    coverage_ratio = categories_with_signal / max(total_categories, 1)

    # Volume: saturates around ~40 files / ~250KB scanned -- enough to be a
    # meaningfully sized sample without requiring huge repos to reach 1.0.
    file_factor = min(1.0, stats.files_scanned / 40)
    byte_factor = min(1.0, stats.bytes_scanned / 250_000)
    volume_factor = (file_factor + byte_factor) / 2

    completeness = 1.0 if stats.source_available else 0.6
    if stats.rendered:
        completeness = min(1.0, completeness + 0.15)

    if findings:
        evidence_quality = sum(f.confidence for f in findings) / len(findings)
    else:
        evidence_quality = 0.5  # no findings at all is itself weak evidence either way

    confidence = (
        0.35 * coverage_ratio
        + 0.30 * volume_factor
        + 0.20 * completeness
        + 0.15 * evidence_quality
    )
    return round(max(0.0, min(1.0, confidence)) * 100, 1)


def compute_score(
    findings: list[Finding],
    stats: ScanStats,
    weights: dict[Category, float] | None = None,
) -> ScoringResult:
    weights = weights or DEFAULT_CATEGORY_WEIGHTS
    findings_by_cat: dict[Category, list[Finding]] = {}
    for f in findings:
        findings_by_cat.setdefault(f.category, []).append(f)

    category_scores: list[CategoryScore] = []
    weighted_sum = 0.0
    weight_total = 0.0
    categories_with_signal = 0
    accessibility_score: float | None = None

    for category, weight in weights.items():
        cat_findings = findings_by_cat.get(category, [])
        score, top_ids = score_category(cat_findings)
        category_scores.append(
            CategoryScore(
                category=category,
                score=score,
                weight=weight,
                finding_count=len(cat_findings),
                top_rule_ids=top_ids,
            )
        )
        if cat_findings:
            categories_with_signal += 1
        weighted_sum += score * weight
        weight_total += weight

    # Accessibility: tracked and reported, never folded into the slop score.
    accessibility_findings = findings_by_cat.get(Category.ACCESSIBILITY, [])
    if accessibility_findings:
        accessibility_score, _ = score_category(accessibility_findings)
        category_scores.append(
            CategoryScore(
                category=Category.ACCESSIBILITY,
                score=accessibility_score,
                weight=0.0,
                finding_count=len(accessibility_findings),
                top_rule_ids=[f.rule_id for f in accessibility_findings][:3],
            )
        )

    slop_score = round(weighted_sum / weight_total, 1) if weight_total else 0.0
    confidence = compute_confidence(
        findings=[f for f in findings if f.category != Category.ACCESSIBILITY],
        categories_with_signal=categories_with_signal,
        total_categories=len(weights),
        stats=stats,
    )

    return ScoringResult(
        slop_score=slop_score,
        confidence=confidence,
        category_scores=category_scores,
        accessibility_score=accessibility_score,
    )
