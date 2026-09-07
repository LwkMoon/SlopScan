from __future__ import annotations

from slopscan.core.source import ScanCorpus, SourceFile, SourceKind
from slopscan.rules.registry import RuleContext, get_rule


def _css_corpus(css: str) -> ScanCorpus:
    return ScanCorpus(files=[SourceFile(path="styles.css", content=css, kind=SourceKind.CSS)])


def _html_corpus(html: str) -> ScanCorpus:
    return ScanCorpus(files=[SourceFile(path="index.html", content=html, kind=SourceKind.HTML)])


def test_one_gradient_is_negligible():
    r = get_rule("visual.gradient.overuse")
    css = ".hero { background: linear-gradient(90deg, red, blue); }"
    finding = r.run(RuleContext(corpus=_css_corpus(css)))
    assert finding is not None
    assert finding.strength < 0.15  # spec section 88: "one gradient -> negligible"


def test_many_gradients_is_a_stronger_signal():
    r = get_rule("visual.gradient.overuse")
    css = "\n".join(f".el{i} {{ background: linear-gradient(90deg, red, blue); }}" for i in range(14))
    finding = r.run(RuleContext(corpus=_css_corpus(css)))
    assert finding is not None
    assert finding.strength > 0.6


def test_normal_shadow_is_not_flagged_as_glow():
    r = get_rule("visual.glow.overuse")
    css = ".card { box-shadow: 0 1px 3px rgba(0,0,0,0.08); }"  # ordinary elevation shadow
    finding = r.run(RuleContext(corpus=_css_corpus(css)))
    assert finding is None


def test_neon_glow_is_flagged():
    r = get_rule("visual.glow.overuse")
    css = "\n".join(
        f".el{i} {{ box-shadow: 0 0 40px rgba(124,58,237,0.8); }}" for i in range(6)
    )
    finding = r.run(RuleContext(corpus=_css_corpus(css)))
    assert finding is not None


def test_single_purple_button_is_not_flagged():
    r = get_rule("visual.color.palette")
    css = ".btn-primary { background: purple; }"
    finding = r.run(RuleContext(corpus=_css_corpus(css)))
    assert finding is None  # spec: "one purple button -> no significant penalty"


def test_pervasive_purple_gradient_system_is_flagged():
    r = get_rule("visual.color.palette")
    css = "\n".join(
        [
            ".bg { background: linear-gradient(violet, indigo); }",
            ".text { color: violet; }",
            ".card { border-color: indigo; }",
            ".cta { background: purple; }",
            ".accent { color: fuchsia; }",
        ]
    )
    finding = r.run(RuleContext(corpus=_css_corpus(css)))
    assert finding is not None


def test_one_generic_phrase_has_low_impact():
    r = get_rule("copy.generic_marketing")
    html = "<html><body><h1>Welcome</h1><p>We build tools. Also: seamless experience for you.</p></body></html>"
    finding = r.run(RuleContext(corpus=_html_corpus(html)))
    assert finding is not None
    assert finding.strength < 0.35


def test_many_generic_phrases_together_are_a_strong_signal():
    r = get_rule("copy.generic_marketing")
    html = (
        "<html><body>"
        "<h1>Transform your workflow</h1>"
        "<p>Build faster. Ship smarter. The future of productivity is here.</p>"
        "<p>Powerful tools for every team. Unlock your potential today.</p>"
        "<p>Seamless experience, revolutionize the way you work.</p>"
        "</body></html>"
    )
    finding = r.run(RuleContext(corpus=_html_corpus(html)))
    assert finding is not None
    assert finding.strength > 0.5


def test_fake_social_proof_has_capped_confidence():
    r = get_rule("copy.fake_social_proof")
    html = "<html><body><p>Trusted by 10,000+ users. 99.9% satisfaction guaranteed.</p></body></html>"
    finding = r.run(RuleContext(corpus=_html_corpus(html)))
    assert finding is not None
    assert finding.confidence < 0.7  # inherently uncertain rule, must not overclaim


def test_border_radius_rule_does_not_flag_single_rounded_button():
    r = get_rule("visual.radius.overuse")
    css = ".btn { border-radius: 6px; }"
    finding = r.run(RuleContext(corpus=_css_corpus(css)))
    assert finding is None


def test_border_radius_rule_flags_universal_pill_rounding():
    r = get_rule("visual.radius.overuse")
    css = "\n".join(f".el{i} {{ border-radius: 9999px; }}" for i in range(16))
    finding = r.run(RuleContext(corpus=_css_corpus(css)))
    assert finding is not None


def test_generic_saas_sequence_detects_full_template():
    r = get_rule("template.generic_saas_sequence")
    html = """
    <html><body>
    <nav class="navbar">Brand</nav>
    <section class="hero"><h1>Hi</h1></section>
    <section class="features">features</section>
    <section class="logos">logos</section>
    <section class="screenshot">shot</section>
    <section class="stats">stats</section>
    <section class="testimonials">quotes</section>
    <section class="pricing">plans</section>
    <section class="faq">faq</section>
    <section class="cta">cta</section>
    <footer class="footer">footer</footer>
    </body></html>
    """
    finding = r.run(RuleContext(corpus=_html_corpus(html)))
    assert finding is not None
    assert finding.strength > 0.7


def test_generic_saas_sequence_does_not_flag_minimal_page():
    r = get_rule("template.generic_saas_sequence")
    html = "<html><body><header>About me</header><main><p>hi</p></main></body></html>"
    finding = r.run(RuleContext(corpus=_html_corpus(html)))
    assert finding is None
