# Scoring

This is the full explanation of how a scan turns into `AI-SLOP LIKELIHOOD: X%`
and `CONFIDENCE: Y%`. The implementation is `src/slopscan/core/scoring.py`;
this document explains *why* it works this way, not just what the code
does.

## The problem with naive scoring

The obviously-wrong approach is linear violation counting:

```
gradient found        -> +10
rounded corner found  -> +10
card found            -> +10
Inter font found       -> +10
```

This is exactly what the project is not supposed to do, for two reasons.
First, every one of those things is completely normal in legitimate,
human-made design -- flagging any of them individually would make the
tool useless (and reversible: remove your gradients, "prove" you're
human). Second, even setting that aside, naive counting double-penalizes
one underlying decision that happens to show up in several places: a
purple gradient used in a hero, a button, and a card border is *one*
design choice, not three independent violations.

## Step 1: occurrence count -> strength (diminishing returns)

Every rule's detection function counts occurrences (however "occurrence"
makes sense for that rule -- gradient declarations, repeated card
structures, generic phrases found, etc.) and hands that count to the rule
engine. The engine converts it to a **strength** in `[0, 1)` via:

```
strength = 1 - exp(-occurrences / full_effect_at)
```

`full_effect_at` is per-rule (set when the rule is defined) and represents
roughly how many occurrences it takes to approach full strength. For
`visual.gradient.overuse`, `full_effect_at=14`: one gradient gives
strength ≈ 0.07 (negligible), 14 gradients gives ≈ 0.63, and it keeps
climbing slowly after that, never quite reaching 1.0. This is the concrete
mechanism behind "one gradient: negligible, fourteen gradients: stronger"
-- it's a real curve, not a hardcoded threshold table.

A rule's **severity** is a ceiling, not a flat label: a rule defined as
`Severity.HIGH` only reports as HIGH when its strength is also high (see
`Rule._severity_for`). A single weak trigger of a HIGH-severity rule
reports as LOW or MEDIUM, never HIGH.

## Step 2: findings -> category score (noisy-OR, not summation)

Within one category (say, VISUAL), several rules might fire at once --
gradients, glow, glassmorphism, colored borders. Summing their strengths
would double-count what's often one underlying aesthetic decision.
Instead, each finding's `strength × confidence × severity_multiplier` is
treated as an independent activation probability, and they're combined
with the standard noisy-OR formula:

```
combined = 1 - Π(1 - activation_i)
```

This has the property that stacking more moderate signals pushes the
category score up, but with steeply diminishing returns -- five findings
each individually "worth" 40% do **not** combine to 200% (or even
anywhere close to it); they combine to something well under what a naive
sum would give, and never above 100%. See
`tests/test_scoring.py::test_multiple_findings_diminish_via_noisy_or_not_linear_sum`
for this asserted directly.

## Step 3: category scores -> overall score (weighted average)

```
overall = Σ(category_score_i × weight_i) / Σ(weight_i)
```

Default weights (0-100 scale, configurable in `.slopscan.toml` under
`[score.weights]`):

| Category | Default weight |
|---|---|
| Visual | 20 |
| Code | 15 |
| Template | 15 |
| Copy | 10 |
| Repetition | 10 |
| Components | 10 |
| Typography | 5 |
| Animation | 5 |
| Other | 10 |

**Accessibility is intentionally not in this table.** Accessibility
findings (missing alt text, missing `prefers-reduced-motion`) are computed
and reported the same way as any other category, but are explicitly
excluded from the weighted sum -- accessibility gaps are common in both
human-written and generated code and are not treated as evidence either
way (see spec rationale in `core/scoring.py`'s module docstring).

## Confidence is a separate axis from the score

Confidence answers "how much should you trust this number", not "how bad
is it" -- a small target with one weird finding and a huge, thoroughly
scanned repository with the same score should not report the same
confidence. It's computed from:

- **Coverage** (35%): how many distinct categories produced any signal at
  all. A score built entirely from one category's evidence is less
  trustworthy than one corroborated across several independent categories.
- **Volume** (30%): files scanned and bytes scanned, saturating around
  ~40 files / ~250KB -- enough to be a meaningful sample without
  requiring huge repos to reach full confidence.
- **Completeness** (20%): was full source available (vs. e.g. a single
  fetched HTML page with no linked assets), and was the page rendered
  (reserved for future browser-based analysis).
- **Evidence quality** (15%): the average per-finding confidence across
  all findings (some rules, like `copy.fake_social_proof`, cap their own
  confidence because they're inherently uncertain).

A tiny single-file target and a fully-scanned large repository can
legitimately produce the same slop score with very different confidence
values -- that's the point.

## JSON schema

`--format json` output is stable and documented inline in
`reports/json_report.py`. Top-level shape:

```json
{
  "slopscan_version": "0.1.0",
  "target": "...",
  "target_type": "local_dir | archive | url | github",
  "slop_score": 78.0,
  "confidence": 86.0,
  "categories": { "visual": {"score": 84.0, "weight": 20.0, "finding_count": 4, "top_rule_ids": [...]}, ... },
  "findings": [
    {
      "rule_id": "visual.gradient.overuse",
      "category": "visual",
      "severity": "high",
      "title": "...",
      "description": "...",
      "occurrences": 14,
      "strength": 0.63,
      "confidence": 1.0,
      "evidence": [{"description": "...", "locator": "styles.css", "snippet": null}],
      "false_positive_note": "..."
    }
  ],
  "positive_signals": [{"signal_id": "semantic_html", "description": "..."}],
  "stats": {"files_scanned": 12, "files_skipped": 0, "bytes_scanned": 45000, "rules_evaluated": 22, "duration_seconds": 0.08, "rendered": false, "source_available": true},
  "ai_interpretation": null,
  "warnings": [],
  "disclaimer": "This score measures the presence of patterns statistically associated with AI-generated or generic template-driven work. It does not prove AI authorship."
}
```
