"""ANIMATION.* rules -- repetitive reveal/decorative motion.

Per spec section 23: detecting *one* fade-in animation proves nothing.
The signal is every section/card using the *same* reveal animation, or
decorative elements using infinite ambient motion everywhere.
"""

from __future__ import annotations

from slopscan.core.models import Category, Evidence, Severity
from slopscan.core.source import SourceKind
from slopscan.rules.registry import DetectionResult, RuleContext, rule
from slopscan.utils.textutils import (
    ANIMATE_CLASS_USAGE_RE,
    FADE_UP_NAME_RE,
    FLOAT_BOUNCE_NAME_RE,
    REDUCED_MOTION_RE,
)


@rule(
    id="animation.repetitive_reveal",
    name="Repetitive scroll-reveal animation",
    category=Category.ANIMATION,
    severity=Severity.MEDIUM,
    description="The same fade-up / slide-up / reveal-on-scroll animation class or utility is applied across many elements.",
    why_it_matters="One entrance animation on a hero is normal polish. The identical reveal animation applied to every section and card, with no variation, is a common generic-template/AI-scaffolded pattern rather than deliberate motion design.",
    false_positives="Motion-design-led products and agencies sometimes deliberately apply one consistent reveal style everywhere as a brand choice.",
    full_effect_at=10,
)
def animation_repetitive_reveal(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence: list[Evidence] = []
    for f in ctx.corpus.by_kind(SourceKind.CSS, SourceKind.HTML, SourceKind.JSX, SourceKind.JS):
        class_hits = len(ANIMATE_CLASS_USAGE_RE.findall(f.content))
        name_hits = len(FADE_UP_NAME_RE.findall(f.content))
        n = class_hits + (name_hits if f.kind == SourceKind.CSS else 0)
        if n:
            total += n
            evidence.append(Evidence(description=f"{n} reveal-animation usage(s)", locator=f.path))
    if total < 4:
        return None
    return DetectionResult(occurrences=total, evidence=evidence[:10])


@rule(
    id="animation.infinite_decorative",
    name="Repetitive infinite decorative motion",
    category=Category.ANIMATION,
    severity=Severity.LOW,
    description="Multiple elements use infinite ambient motion (float, bounce, wiggle, pulse-glow) purely for decoration.",
    why_it_matters="A single floating decorative element can be an intentional flourish. Many independent elements all gently floating/pulsing is a common generic-AI-site pattern (\"everything is alive\") rather than purposeful animation.",
    false_positives="Playful, animation-forward brands (games, kids products) can use this deliberately and extensively.",
    full_effect_at=6,
)
def animation_infinite_decorative(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence: list[Evidence] = []
    for f in ctx.corpus.by_kind(SourceKind.CSS):
        n = len(FLOAT_BOUNCE_NAME_RE.findall(f.content))
        if n:
            total += n
            evidence.append(Evidence(description=f"{n} infinite/ambient decorative animation name(s)", locator=f.path))
    if total < 3:
        return None
    return DetectionResult(occurrences=total, evidence=evidence[:8], confidence=0.65)


@rule(
    id="accessibility.reduced_motion_missing",
    name="No prefers-reduced-motion support",
    category=Category.ACCESSIBILITY,
    severity=Severity.LOW,
    description="Animations are present in the stylesheet(s) but no @media (prefers-reduced-motion) rule was found.",
    why_it_matters="This is an accessibility gap, not evidence of AI authorship -- plenty of human-written sites skip this too. It's reported separately and contributes only a very small amount to the overall score.",
    false_positives="Sites with no meaningful animation at all correctly don't trigger this rule.",
    full_effect_at=1,
)
def accessibility_reduced_motion_missing(ctx: RuleContext) -> DetectionResult | None:
    css_files = ctx.corpus.by_kind(SourceKind.CSS)
    has_animation = any(
        "@keyframes" in f.content or "animation" in f.content.lower() for f in css_files
    )
    if not has_animation:
        return None
    has_reduced_motion = any(REDUCED_MOTION_RE.search(f.content) for f in css_files)
    if has_reduced_motion:
        return None
    animated_files = [
        f.path for f in css_files if "@keyframes" in f.content or "animation" in f.content.lower()
    ]
    return DetectionResult(
        occurrences=1,
        evidence=[
            Evidence(
                description="Animations detected with no @media (prefers-reduced-motion) rule in the scanned CSS",
                locator=", ".join(animated_files[:5]),
            )
        ],
        confidence=0.9,
    )
