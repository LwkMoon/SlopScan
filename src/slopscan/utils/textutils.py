"""Regex and text-extraction helpers shared by rule modules.

Kept deliberately dumb (regex over CSS/HTML/JS rather than a full parser)
for CSS/JS -- a real CSS/JS AST is a much bigger dependency for marginal
accuracy gain here, since these rules care about *presence and frequency*
of patterns, not perfect syntactic correctness. HTML uses BeautifulSoup
since DOM structure (nesting, repeated siblings) genuinely needs a tree.
"""

from __future__ import annotations

import re
from functools import lru_cache

from bs4 import BeautifulSoup

# --- CSS / inline-style pattern families -----------------------------------

GRADIENT_RE = re.compile(
    r"(linear-gradient|radial-gradient|conic-gradient|repeating-linear-gradient)\s*\(",
    re.IGNORECASE,
)

GLOW_RE = re.compile(
    r"(box-shadow\s*:[^;{}]*(0\s+0\s+\d|(\d+px\s+){2}\d+px\s+\d+px))"
    r"|(text-shadow\s*:[^;{}]+)"
    r"|(filter\s*:[^;{}]*blur\()"
    r"|(drop-shadow\()",
    re.IGNORECASE,
)

NORMAL_SHADOW_RE = re.compile(
    r"box-shadow\s*:\s*0\s+1?\d?px\s+[0-3]?\d?px\s+(rgba?\([^)]*,\s*0?\.0[0-9]|#[0-9a-f]{3,8})",
    re.IGNORECASE,
)

GLASSMORPHISM_RE = re.compile(r"backdrop-filter\s*:[^;{}]*blur\(", re.IGNORECASE)
TRANSLUCENT_BG_RE = re.compile(
    r"background(-color)?\s*:\s*rgba?\([^)]*,\s*0?\.[0-9]+\s*\)", re.IGNORECASE
)

BORDER_LEFT_ACCENT_RE = re.compile(
    r"border-left\s*:\s*[1-9]\d?px\s+solid\s+", re.IGNORECASE
)
COLORED_BORDER_RE = re.compile(
    r"border(-\w+)?\s*:\s*\d+px\s+solid\s+(#[0-9a-f]{3,8}|rgba?\()", re.IGNORECASE
)

BORDER_RADIUS_RE = re.compile(r"border-radius\s*:\s*([\w.%]+)", re.IGNORECASE)
PILL_RADIUS_VALUES = {"9999px", "999px", "50%", "100%", "1000px", "50vh"}

# purple/violet/indigo/cyan family -- named colors, common hex ranges, and
# CSS variable names that signal the same design choice
PURPLE_FAMILY_RE = re.compile(
    r"(#7[0-9a-f]{1}[0-9a-f]{1}(?:[0-9a-f]{2}){0,2}e[0-9a-f]{2,4}\b)"  # crude hex-purple heuristic
    r"|(\bpurple\b|\bviolet\b|\bindigo\b|\bfuchsia\b)"
    r"|(--(color-)?(purple|violet|indigo|fuchsia)[a-z0-9-]*)"
    r"|(\brgb\(\s*1[0-9]{2}\s*,\s*[0-6]?\d\s*,\s*2[0-4]\d\s*\))",  # rough purple rgb band
    re.IGNORECASE,
)
NEON_BLUE_CYAN_RE = re.compile(
    r"(\bcyan\b|\bcyan-[0-9]{2,3}\b|\bneon-blue\b|#00[0-9a-f]{2}ff\b|#0ff\b)", re.IGNORECASE
)

ANIMATION_KEYFRAME_RE = re.compile(
    r"@keyframes\s+([\w-]+)\s*{([^}]*)}", re.IGNORECASE | re.DOTALL
)
FADE_UP_NAME_RE = re.compile(r"fade-?up|fadeUp|reveal|slide-?up|slideUp", re.IGNORECASE)
FLOAT_BOUNCE_NAME_RE = re.compile(r"float|bounce|wiggle|pulse-?glow|shimmer", re.IGNORECASE)
ANIMATE_CLASS_USAGE_RE = re.compile(
    r"(animate-(fade|slide|bounce|pulse|float|wiggle)[\w-]*)"
    r"|(data-aos\s*=\s*[\"'](fade|zoom|slide)[\w-]*[\"'])"
    r"|(\.animate__[\w-]+)",
    re.IGNORECASE,
)
REDUCED_MOTION_RE = re.compile(r"prefers-reduced-motion", re.IGNORECASE)

UPPERCASE_LABEL_RE = re.compile(r"text-transform\s*:\s*uppercase", re.IGNORECASE)
LETTER_SPACING_RE = re.compile(r"letter-spacing\s*:\s*([\w.]+)", re.IGNORECASE)

_GENERIC_FONT_STACK_HINTS = (
    "inter",
    "geist",
    "poppins",
    "roboto",
    "space grotesk",
    "manrope",
    "sf pro",
    "system-ui",
)


def find_font_families(css_text: str) -> list[str]:
    fams = re.findall(r"font-family\s*:\s*([^;{}]+)", css_text, re.IGNORECASE)
    return [f.strip().strip("\"'") for f in fams]


def count_font_sizes(css_text: str) -> set[str]:
    sizes = re.findall(r"font-size\s*:\s*([\w.%]+)", css_text, re.IGNORECASE)
    return {s.strip() for s in sizes}


@lru_cache(maxsize=256)
def _compile_phrase_regex(phrase: str) -> re.Pattern:
    return re.compile(re.escape(phrase), re.IGNORECASE)


def count_phrase_occurrences(text: str, phrases: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for phrase in phrases:
        n = len(_compile_phrase_regex(phrase).findall(text))
        if n:
            counts[phrase] = n
    return counts


def visible_text_from_html(html: str, limit_chars: int = 200_000) -> str:
    """Extract human-visible text, dropping script/style/noscript content."""
    soup = BeautifulSoup(html[:limit_chars], "lxml")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text)


def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


STAT_CLAIM_RE = re.compile(
    r"(\b\d[\d,]{2,}\+?\s*(users|customers|companies|downloads|installs|teams)\b)"
    r"|(\b9[5-9](\.\d+)?%\s*(satisfaction|uptime|approval)\b)"
    r"|(\b100%\s*(satisfaction|guarantee)\b)",
    re.IGNORECASE,
)

SECTION_KEYWORDS = {
    "navbar": ("nav", "navbar", "navigation"),
    "hero": ("hero", "banner", "jumbotron"),
    "features": ("feature", "features", "benefits"),
    "logos": ("logo-cloud", "logos", "trusted-by", "brands"),
    "screenshot": ("screenshot", "product-preview", "app-preview"),
    "stats": ("stats", "statistics", "metrics", "numbers"),
    "testimonials": ("testimonial", "reviews", "quotes"),
    "pricing": ("pricing", "plans", "tiers"),
    "faq": ("faq", "questions", "accordion"),
    "cta": ("cta", "get-started", "signup-banner"),
    "footer": ("footer",),
}
