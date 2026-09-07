# Rules

SlopScan's rules live in `src/slopscan/rules/`, one small module per
category. Run `slopscan rules list` for the live list from your installed
version, and `slopscan rules show <id>` for full detail on any one rule.
This document is the philosophy behind them.

## What makes a rule "good" in this codebase

Every rule in SlopScan is expected to follow the same shape, because the
project's entire credibility rests on not being a "gradient = AI" toy:

1. **Frequency-gated, never single-occurrence.** A rule's detection
   function counts occurrences; the engine (not the rule) applies a
   diminishing-returns curve so one instance is negligible and repeated
   instances matter more, with steeply diminishing marginal weight past
   a point. See [docs/scoring.md](scoring.md) for the exact math.
2. **An honest false-positive note.** Every rule ships with a
   `false_positives` string describing a real, plausible case where it
   would fire on legitimate work. `slopscan rules show <id>` always
   displays it. If a rule doesn't have one, it hasn't been thought through.
3. **Traceable evidence.** Findings point to a file path, URL, or
   similarly concrete locator wherever the corpus makes that possible.
4. **No fabrication.** A rule that can't verify something (e.g. whether a
   testimonial or statistic is real) says so in its own evidence text and
   caps its `confidence` accordingly, rather than reporting with false
   certainty.
5. **Never claims authorship.** Rule descriptions describe *patterns*,
   not verdicts -- "commonly associated with," "detected sequence,"
   never "this proves" or "this was made by."

## Current rule set

### Visual (`rules/visual.py`)

- `visual.gradient.overuse` -- repeated CSS gradients across surfaces
- `visual.glow.overuse` -- decorative glow/neon shadows, distinguished
  from ordinary elevation shadows
- `visual.glassmorphism` -- repeated frosted/translucent panel patterns
- `visual.border.repetition` -- repeated colored/accent border systems
- `visual.radius.overuse` -- universal excessive/pill rounding with no
  size hierarchy
- `visual.color.palette` -- purple/violet/indigo/cyan family overuse,
  amplified when combined with gradients

### Copy (`rules/copy.py`)

- `copy.generic_marketing` -- stock AI-style marketing phrases (backed
  by the maintainable phrase database in `rules/data/generic_phrases.json`)
- `copy.buzzword_density` -- high concentration of vague superlatives
- `copy.fake_social_proof` -- unsourced round-number statistic claims
  (explicitly confidence-capped -- see the rule's own note)

### Template / Layout (`rules/layout.py`)

- `template.generic_saas_sequence` -- page section order closely matches
  the common navbar → hero → features → ... → footer template (measured
  via longest-common-subsequence similarity, not just "has a hero")
- `layout.repetitive_cards` -- many structurally near-identical card
  elements (icon/heading/paragraph/button composition)
- `layout.card_in_card` -- card-like containers nested inside other cards

### Typography (`rules/typography.py`)

- `typography.weak_hierarchy` -- very few distinct font-size values
  across a sizeable stylesheet
- `typography.excessive_uppercase` -- pervasive uppercase micro-labels
- `typography.generic_stack_only` -- only a generic default font with no
  supporting weight/pairing decisions (deliberately very low weight --
  using a popular font is not evidence of anything by itself)

### Animation (`rules/animation.py`)

- `animation.repetitive_reveal` -- the same scroll-reveal animation
  applied across many elements
- `animation.infinite_decorative` -- repeated ambient float/bounce/wiggle
  motion
- `accessibility.reduced_motion_missing` -- animations present with no
  `prefers-reduced-motion` support (accessibility category, not scored
  into the slop number)

### Components (`rules/components.py`)

- `components.repeated_jsx_tags` -- the same generically-named component
  tag used many times with little other diversity nearby
- `components.icon_heading_description` -- repeated icon+heading+
  description block structure (registered under the Repetition category)

### Code (`rules/code.py`)

- `code.duplicate_blocks` -- near-identical multi-line code blocks
  repeated across the codebase
- `accessibility.missing_alt_text` -- images missing alt text
  (accessibility category, not scored into the slop number)

## Why some things are deliberately *not* rules

- **Dependencies** (`analyzers/dependencies.py`) are detected and shown
  as context, but never scored. Using Tailwind, shadcn, Framer Motion, or
  React proves nothing about how a site was made.
- **Unconventional/asymmetric layouts** are not rewarded directly. The
  goal is never "different = human" -- positive signals
  (`core/positive_signals.py`) look for specificity and intentionality
  (semantic HTML, a real design-token system, typographic variety,
  accessible images), not mere difference from a template.
- **A single instance of almost anything.** See point 1 above.

## Adding your own rule

See [CONTRIBUTING.md](../CONTRIBUTING.md#3-add-a-new-rule).
