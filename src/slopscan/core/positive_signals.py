"""Positive-signal detection (spec section 38).

These never mechanically subtract from the slop score -- that would just
create an obvious gaming vector ("add one semantic <main> tag, score drops
5%"). Instead they're surfaced in the report to contextualize the result,
and are handed to the optional AI interpretation layer as extra evidence.
"""

from __future__ import annotations

from slopscan.core.models import PositiveSignal
from slopscan.core.source import ScanCorpus, SourceKind
from slopscan.utils.textutils import find_font_families, parse_html


def detect_positive_signals(corpus: ScanCorpus) -> list[PositiveSignal]:
    signals: list[PositiveSignal] = []

    # Semantic HTML usage
    semantic_tags = {"main", "article", "aside", "figure", "figcaption", "nav", "header", "footer"}
    semantic_hits = 0
    for f in corpus.by_kind(SourceKind.HTML):
        soup = parse_html(f.content)
        for tag in semantic_tags:
            semantic_hits += len(soup.find_all(tag))
    if semantic_hits >= 4:
        signals.append(
            PositiveSignal(
                signal_id="semantic_html",
                description=f"{semantic_hits} semantic HTML5 landmark elements used",
            )
        )

    # Typographic variety (more than a couple of distinct font sizes+weights
    # suggests a considered type scale rather than accepting defaults)
    css_files = corpus.by_kind(SourceKind.CSS)
    if css_files:
        families: set[str] = set()
        for f in css_files:
            families |= {
                fam.split(",")[0].strip().strip("\"'").lower() for fam in find_font_families(f.content)
            }
        if len(families) >= 3:
            signals.append(
                PositiveSignal(
                    signal_id="typographic_variety",
                    description=(
                        f"{len(families)} distinct font families declared, "
                        "suggesting deliberate typographic pairing"
                    ),
                )
            )

    # Custom/varied color tokens (a real palette system, not just a couple
    # of copy-pasted gradient stops)
    custom_props: set[str] = set()
    for f in css_files:
        for line in f.content.splitlines():
            line = line.strip()
            if line.startswith("--") and ":" in line:
                custom_props.add(line.split(":", 1)[0].strip())
    if len(custom_props) >= 8:
        signals.append(
            PositiveSignal(
                signal_id="design_token_system",
                description=(
                    f"{len(custom_props)} CSS custom properties defined, "
                    "suggesting a maintained design-token system"
                ),
            )
        )

    # Alt text present and non-empty on most images
    total_imgs = 0
    described_imgs = 0
    for f in corpus.by_kind(SourceKind.HTML):
        soup = parse_html(f.content)
        for img in soup.find_all("img"):
            total_imgs += 1
            alt = img.get("alt")
            if alt and str(alt).strip():
                described_imgs += 1
    if total_imgs >= 3 and described_imgs / total_imgs >= 0.8:
        signals.append(
            PositiveSignal(
                signal_id="accessible_images",
                description=f"{described_imgs}/{total_imgs} images have meaningful alt text",
            )
        )

    return signals
