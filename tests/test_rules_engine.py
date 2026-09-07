from __future__ import annotations

from slopscan.core.models import Category, Severity
from slopscan.core.source import ScanCorpus, SourceFile, SourceKind
from slopscan.rules import all_rules, get_rule
from slopscan.rules.registry import REGISTRY, RuleContext, rule


def test_registry_has_rules_in_every_documented_category():
    categories_present = {r.category for r in all_rules()}
    # every category except OTHER should have at least one rule defined
    for cat in Category:
        if cat == Category.OTHER:
            continue
        assert cat in categories_present, f"no rules registered for {cat}"


def test_get_rule_returns_none_for_unknown_id():
    assert get_rule("nonexistent.rule.id") is None


def test_strength_from_count_is_monotonic_and_diminishing():
    r = get_rule("visual.gradient.overuse")
    assert r is not None
    s1 = r.strength_from_count(1)
    s5 = r.strength_from_count(5)
    s20 = r.strength_from_count(20)
    s100 = r.strength_from_count(100)
    assert 0 < s1 < s5 < s20 < s100
    # Marginal gain from 20->100 should be much smaller than from 1->5
    assert (s100 - s20) < (s5 - s1) * 5
    assert s100 < 1.0  # never fully saturates to exactly 1


def test_strength_from_count_zero_is_zero():
    r = get_rule("visual.gradient.overuse")
    assert r.strength_from_count(0) == 0.0


def test_weak_trigger_never_reports_as_high_severity():
    r = get_rule("visual.gradient.overuse")  # base severity HIGH
    assert r.base_severity == Severity.HIGH
    finding = r.run(RuleContext(corpus=_corpus_with_gradients(count=1)))
    assert finding is not None
    assert finding.severity != Severity.HIGH  # single occurrence should downgrade


def test_strong_trigger_can_reach_base_severity():
    r = get_rule("visual.gradient.overuse")
    finding = r.run(RuleContext(corpus=_corpus_with_gradients(count=30)))
    assert finding is not None
    assert finding.severity == Severity.HIGH


def _corpus_with_gradients(count: int) -> ScanCorpus:
    css = "\n".join(f".el{i} {{ background: linear-gradient(90deg, red, blue); }}" for i in range(count))
    return ScanCorpus(files=[SourceFile(path="styles.css", content=css, kind=SourceKind.CSS)])


def test_custom_rule_registration_via_decorator():
    calls = {"count": 0}

    @rule(
        id="test.custom_rule",
        name="Custom test rule",
        category=Category.OTHER,
        severity=Severity.LOW,
        description="desc",
        why_it_matters="why",
        false_positives="fp",
    )
    def _detect(ctx: RuleContext):
        calls["count"] += 1
        return None

    try:
        assert get_rule("test.custom_rule") is not None
        r = get_rule("test.custom_rule")
        result = r.run(RuleContext(corpus=ScanCorpus()))
        assert result is None
        assert calls["count"] == 1
    finally:
        REGISTRY.pop("test.custom_rule", None)
