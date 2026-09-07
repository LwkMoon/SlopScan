"""Integration tests: false-positive protection (spec section 55) and basic
end-to-end sanity for the local-directory scan path."""

from __future__ import annotations

from slopscan.core.scanner import scan


def test_restrained_human_site_scores_low(human_portfolio_dir):
    result = scan(str(human_portfolio_dir))
    assert result.slop_score < 15
    assert result.findings == []


def test_restrained_human_site_gets_positive_signals(human_portfolio_dir):
    result = scan(str(human_portfolio_dir))
    assert len(result.positive_signals) >= 1


def test_generic_saas_fixture_scores_meaningfully_higher(generic_saas_dir, human_portfolio_dir):
    generic_result = scan(str(generic_saas_dir))
    human_result = scan(str(human_portfolio_dir))
    assert generic_result.slop_score > human_result.slop_score
    assert generic_result.slop_score > 20


def test_generic_saas_fixture_has_traceable_evidence(generic_saas_dir):
    result = scan(str(generic_saas_dir))
    assert len(result.findings) > 0
    for finding in result.findings:
        assert len(finding.evidence) > 0
        # every finding should be traceable to a locator or contain a count
        assert any(e.locator or any(ch.isdigit() for ch in e.description) for e in finding.evidence)


def test_score_never_claims_certainty_in_language():
    """The disclaimer / wording constraint from spec section 1: never claim
    definite AI authorship anywhere in rule descriptions."""
    from slopscan.rules import all_rules

    forbidden_phrases = ["definitely made by ai", "100% ai-generated", "proves ai", "was created by ai"]
    for r in all_rules():
        text = f"{r.description} {r.why_it_matters}".lower()
        for phrase in forbidden_phrases:
            assert phrase not in text, f"{r.id} uses overclaiming language: {phrase!r}"


def test_scan_result_is_reproducible(generic_saas_dir):
    result1 = scan(str(generic_saas_dir))
    result2 = scan(str(generic_saas_dir))
    assert result1.slop_score == result2.slop_score
    assert result1.confidence == result2.confidence
    assert len(result1.findings) == len(result2.findings)


def test_confidence_is_independent_of_score_magnitude(generic_saas_dir, human_portfolio_dir):
    """Confidence should reflect evidence quality/coverage, not just track the score."""
    generic_result = scan(str(generic_saas_dir))
    human_result = scan(str(human_portfolio_dir))
    # human site: low score AND low confidence (very little to go on) is fine;
    # what we assert is that confidence isn't simply "= score" or "= 100 - score".
    assert generic_result.confidence != generic_result.slop_score
    assert human_result.confidence != human_result.slop_score
