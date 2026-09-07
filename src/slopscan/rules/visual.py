"""VISUAL.* rules -- gradients, glow, glassmorphism, borders, radius, color.

Every rule here is frequency-gated: the detection function counts
occurrences across the whole corpus and hands that count to the rule
engine, which turns it into a diminishing-returns strength (see
rules.registry.Rule.strength_from_count). One gradient never triggers a
meaningful finding; a dozen across primary surfaces does.
"""

from __future__ import annotations

from slopscan.core.models import Category, Evidence, Severity
from slopscan.core.source import ScanCorpus, SourceKind
from slopscan.rules.registry import DetectionResult, RuleContext, rule
from slopscan.utils.textutils import (
    BORDER_LEFT_ACCENT_RE,
    BORDER_RADIUS_RE,
    COLORED_BORDER_RE,
    GLASSMORPHISM_RE,
    GLOW_RE,
    GRADIENT_RE,
    NEON_BLUE_CYAN_RE,
    NORMAL_SHADOW_RE,
    PILL_RADIUS_VALUES,
    PURPLE_FAMILY_RE,
    TRANSLUCENT_BG_RE,
)


def _style_text(corpus: ScanCorpus) -> list[tuple[str, str]]:
    """(path, content) pairs for CSS files plus inline style/class attrs in HTML."""
    out = [(f.path, f.content) for f in corpus.by_kind(SourceKind.CSS)]
    for f in corpus.by_kind(SourceKind.HTML, SourceKind.JSX):
        out.append((f.path, f.content))
    return out


@rule(
    id="visual.gradient.overuse",
    name="Excessive gradient usage",
    category=Category.VISUAL,
    severity=Severity.HIGH,
    description="Repeated use of CSS gradients across UI surfaces (backgrounds, text, buttons, borders).",
    why_it_matters=(
        "Gradients are not inherently AI-generated. Repeated decorative gradient "
        "usage across many unrelated surfaces is a common pattern in generic "
        "AI-generated and template-driven web design."
    ),
    false_positives="Brand-heavy interfaces and creative/portfolio sites that use gradients as an intentional signature.",
    full_effect_at=14,
)
def visual_gradient_overuse(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence: list[Evidence] = []
    for path, content in _style_text(ctx.corpus):
        matches = GRADIENT_RE.findall(content)
        if matches:
            total += len(matches)
            evidence.append(Evidence(description=f"{len(matches)} gradient declaration(s)", locator=path))
    if total == 0:
        return None
    evidence.insert(0, Evidence(description=f"{total} gradient declarations detected across the scanned surfaces"))
    return DetectionResult(occurrences=total, evidence=evidence[:12])


@rule(
    id="visual.glow.overuse",
    name="Excessive glow / neon shadow effects",
    category=Category.VISUAL,
    severity=Severity.MEDIUM,
    description="Decorative glow (large-spread box-shadow, text-shadow, blur filters) repeated across components.",
    why_it_matters=(
        "Normal elevation shadows are ordinary UI depth cues. Large, colorful, "
        "or blurred glow effects repeated across many elements are a common "
        "generic-AI-design signature rather than a deliberate elevation system."
    ),
    false_positives="Gaming, music, or nightlife-brand sites where neon is the intentional aesthetic.",
    full_effect_at=10,
)
def visual_glow_overuse(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    normal_shadows = 0
    evidence: list[Evidence] = []
    for path, content in _style_text(ctx.corpus):
        glow_matches = GLOW_RE.findall(content)
        normal_matches = NORMAL_SHADOW_RE.findall(content)
        normal_shadows += len(normal_matches)
        # Don't double count shadows that are actually subtle/normal elevation.
        effective = max(0, len(glow_matches) - len(normal_matches))
        if effective:
            total += effective
            evidence.append(Evidence(description=f"{effective} glow/neon-style effect(s)", locator=path))
    if total == 0:
        return None
    evidence.insert(
        0,
        Evidence(
            description=(
                f"{total} decorative glow effects detected "
                f"(distinguished from {normal_shadows} ordinary elevation shadows, which are not counted)"
            )
        ),
    )
    return DetectionResult(occurrences=total, evidence=evidence[:12])


@rule(
    id="visual.glassmorphism",
    name="Repeated glassmorphism panels",
    category=Category.VISUAL,
    severity=Severity.MEDIUM,
    description="Frosted/translucent panels using backdrop-filter blur combined with semi-transparent backgrounds, repeated across components.",
    why_it_matters="A single glass panel can be a deliberate accent; the same frosted-card treatment applied everywhere is a common generic-template pattern.",
    false_positives="Design systems that use glassmorphism as one consistent, deliberate material language (e.g. macOS-style products).",
    full_effect_at=6,
)
def visual_glassmorphism(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence: list[Evidence] = []
    for path, content in _style_text(ctx.corpus):
        blur_hits = len(GLASSMORPHISM_RE.findall(content))
        translucent_hits = len(TRANSLUCENT_BG_RE.findall(content))
        combined = min(blur_hits, translucent_hits) + max(0, blur_hits - translucent_hits) // 2
        if combined:
            total += combined
            evidence.append(Evidence(description=f"{combined} glass-panel pattern(s)", locator=path))
    if total == 0:
        return None
    return DetectionResult(occurrences=total, evidence=evidence[:10])


@rule(
    id="visual.border.repetition",
    name="Repeated decorative border system",
    category=Category.VISUAL,
    severity=Severity.LOW,
    description="Identical colored/accent borders (e.g. left-border cards) repeated across many components.",
    why_it_matters="One accent border is a design choice; the exact same border treatment on every card is a template signature.",
    false_positives="Deliberate, consistent design systems with a documented border scale.",
    full_effect_at=12,
)
def visual_border_repetition(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence: list[Evidence] = []
    for path, content in _style_text(ctx.corpus):
        left = len(BORDER_LEFT_ACCENT_RE.findall(content))
        colored = len(COLORED_BORDER_RE.findall(content))
        n = left + colored
        if n:
            total += n
            evidence.append(Evidence(description=f"{n} colored/accent border declaration(s)", locator=path))
    if total < 3:  # a couple of borders is unremarkable; don't even fire
        return None
    return DetectionResult(occurrences=total, evidence=evidence[:10])


@rule(
    id="visual.radius.overuse",
    name="Universal excessive rounding",
    category=Category.VISUAL,
    severity=Severity.LOW,
    description="Very large or pill-shaped border-radius values applied broadly, without hierarchy between components.",
    why_it_matters="A rounded button or pill badge is normal UI. Applying near-identical maximal rounding to nearly everything (cards, inputs, images, containers) with no size hierarchy is a common generic-template pattern.",
    false_positives="Intentionally soft/playful brand systems, and legitimate pill-shaped controls (tags, toggles).",
    full_effect_at=16,
)
def visual_radius_overuse(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    distinct_values: set[str] = set()
    evidence: list[Evidence] = []
    for path, content in _style_text(ctx.corpus):
        values = BORDER_RADIUS_RE.findall(content)
        pill_like = [v for v in values if v.strip() in PILL_RADIUS_VALUES or _is_large_px(v)]
        distinct_values.update(values)
        if pill_like:
            total += len(pill_like)
            evidence.append(Evidence(description=f"{len(pill_like)} large/pill-radius declaration(s)", locator=path))
    if total == 0:
        return None
    # Lack of hierarchy: very few distinct radius values relative to usage count
    # is itself part of the signal, but we keep the primary metric simple (count).
    evidence.insert(
        0,
        Evidence(
            description=f"{total} large/universal rounding declarations across {len(distinct_values)} distinct radius value(s)"
        ),
    )
    return DetectionResult(occurrences=total, evidence=evidence[:10])


def _is_large_px(value: str) -> bool:
    value = value.strip().lower()
    if value.endswith("px"):
        try:
            return float(value[:-2]) >= 20
        except ValueError:
            return False
    if value.endswith("rem"):
        try:
            return float(value[:-3]) >= 1.5
        except ValueError:
            return False
    return False


@rule(
    id="visual.color.palette",
    name="Purple/violet/indigo/cyan gradient palette overuse",
    category=Category.VISUAL,
    severity=Severity.MEDIUM,
    description="Heavy, repeated reliance on the purple/violet/indigo/cyan family, especially combined with gradients.",
    why_it_matters=(
        "This palette family is extremely common in AI-generated and generic "
        "SaaS templates. A single purple button is not a signal; the palette "
        "dominating backgrounds, text, and CTAs together is."
    ),
    false_positives="Brands whose identity color is genuinely purple/indigo/cyan (this is common and legitimate).",
    full_effect_at=10,
)
def visual_color_palette(ctx: RuleContext) -> DetectionResult | None:
    total = 0
    evidence: list[Evidence] = []
    gradient_overlap = 0
    for path, content in _style_text(ctx.corpus):
        purple_hits = len(PURPLE_FAMILY_RE.findall(content))
        cyan_hits = len(NEON_BLUE_CYAN_RE.findall(content))
        n = purple_hits + cyan_hits
        if n:
            total += n
            evidence.append(Evidence(description=f"{n} purple/violet/indigo/cyan color reference(s)", locator=path))
            if GRADIENT_RE.search(content):
                gradient_overlap += 1
    if total < 4:  # a couple of purple references is unremarkable on its own
        return None
    if gradient_overlap:
        evidence.insert(
            0,
            Evidence(
                description=f"Palette co-occurs with gradients in {gradient_overlap} file(s), amplifying the pattern"
            ),
        )
    return DetectionResult(occurrences=total, evidence=evidence[:10])
