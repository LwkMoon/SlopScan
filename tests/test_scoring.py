from __future__ import annotations

from slopscan.core.models import Category, Evidence, Finding, ScanStats, Severity
from slopscan.core.scoring import compute_confidence, compute_score, score_category


def _finding(rule_id: str, category: Category, severity: Severity, strength: float, confidence: float = 1.0) -> Finding:
    return Finding(
        rule_id=rule_id,
        category=category,
        severity=severity,
        title=rule_id,
        description="test",
        occurrences=max(1, int(strength * 10)),
        strength=strength,
        confidence=confidence,
        evidence=[Evidence(description="evidence")],
    )


def test_no_findings_gives_zero_score():
    result = score_category([])
    assert result == (0.0, [])


def test_single_low_strength_finding_has_small_impact():
    findings = [_finding("visual.gradient.overuse", Category.VISUAL, Severity.HIGH, strength=0.1)]
    score, top = score_category(findings)
    assert 0 < score < 20
    assert top == ["visual.gradient.overuse"]


def test_multiple_findings_diminish_via_noisy_or_not_linear_sum():
    """Five findings each individually worth ~40% should NOT sum linearly to 200%;
    noisy-OR combination should keep the result well under a naive sum and under 100."""
    findings = [
        _finding(f"rule.{i}", Category.VISUAL, Severity.MEDIUM, strength=0.4) for i in range(5)
    ]
    score, _ = score_category(findings)
    naive_linear_sum = 100 * 5 * 0.4 * 0.7  # severity multiplier for medium is 0.7
    assert score < naive_linear_sum
    assert score <= 100.0


def test_full_strength_critical_findings_saturate_near_100():
    findings = [_finding(f"rule.{i}", Category.VISUAL, Severity.CRITICAL, strength=1.0) for i in range(3)]
    score, _ = score_category(findings)
    assert score > 95


def test_compute_score_overall_weighted_average():
    findings = [
        _finding("visual.gradient.overuse", Category.VISUAL, Severity.HIGH, strength=1.0),
    ]
    stats = ScanStats(files_scanned=10, bytes_scanned=50_000, rules_evaluated=22, source_available=True)
    result = compute_score(findings, stats)
    assert 0 < result.slop_score <= 100
    visual = next(c for c in result.category_scores if c.category == Category.VISUAL)
    assert visual.score > 0
    code = next(c for c in result.category_scores if c.category == Category.CODE)
    assert code.score == 0.0


def test_accessibility_excluded_from_slop_score():
    """A pile of accessibility findings alone should not move the slop score at all."""
    findings = [
        _finding(f"accessibility.rule{i}", Category.ACCESSIBILITY, Severity.HIGH, strength=1.0) for i in range(5)
    ]
    stats = ScanStats(files_scanned=5, bytes_scanned=10_000, rules_evaluated=22)
    result = compute_score(findings, stats)
    assert result.slop_score == 0.0
    assert result.accessibility_score is not None
    assert result.accessibility_score > 0


def test_confidence_increases_with_coverage_and_volume():
    stats_small = ScanStats(files_scanned=1, bytes_scanned=500, rules_evaluated=22, source_available=True)
    stats_large = ScanStats(files_scanned=50, bytes_scanned=300_000, rules_evaluated=22, source_available=True)
    findings = [_finding("rule.1", Category.VISUAL, Severity.MEDIUM, strength=0.5)]

    low_conf = compute_confidence(findings, categories_with_signal=1, total_categories=9, stats=stats_small)
    high_conf = compute_confidence(findings, categories_with_signal=1, total_categories=9, stats=stats_large)
    assert high_conf > low_conf


def test_confidence_bounded_0_to_100():
    stats = ScanStats(files_scanned=1000, bytes_scanned=10_000_000, rules_evaluated=22, source_available=True, rendered=True)
    findings = [_finding(f"rule.{i}", Category.VISUAL, Severity.HIGH, strength=1.0, confidence=1.0) for i in range(20)]
    conf = compute_confidence(findings, categories_with_signal=9, total_categories=9, stats=stats)
    assert 0.0 <= conf <= 100.0
