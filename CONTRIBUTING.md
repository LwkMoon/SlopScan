# Contributing to SlopScan

Thanks for considering a contribution. SlopScan is most useful when its
rule set reflects real, observed patterns rather than one person's
opinions, so contributions to the rules themselves are especially welcome.

## Getting set up

```bash
git clone https://github.com/LwkMoonn/slopscan
cd slopscan
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

`pip install -e ".[dev]"` pulls in `pytest`, `ruff`, and `mypy` alongside
the core dependencies.

## Before you open a PR

```bash
ruff check src/ tests/
mypy src/slopscan
pytest
```

All three should pass. CI runs the same checks (see
`.github/workflows/ci.yml`).

## Ways to contribute

### 1. Report a false positive

This is one of the highest-value contributions. If SlopScan flagged
something it shouldn't have:

1. Open an issue with the target (or a minimal reproduction -- a small
   HTML/CSS snippet is ideal) and the rule id that fired
   (`slopscan analyze --format json` includes `rule_id` for every finding).
2. If you can, include a short explanation of why the pattern is
   legitimate in context -- that becomes the false-positive note for the
   rule.

### 2. Add a generic-phrase entry

`src/slopscan/rules/data/generic_phrases.json` is a plain JSON file, not
hardcoded Python. Add an entry under `generic_marketing_phrases` or
`buzzwords`, open a PR. No code changes needed for this one.

### 3. Add a new rule

Rules live in `src/slopscan/rules/`, one small module per category
(`visual.py`, `copy.py`, `layout.py`, etc.). A rule is a function decorated
with `@rule(...)` that takes a `RuleContext` and returns a
`DetectionResult | None`. See any existing rule for the shape, and
`src/slopscan/rules/registry.py` for what each field means.

Guidelines for new rules, straight from what SlopScan already tries to do
throughout the rule set:

- **One occurrence should almost never fire a strong finding.** Use
  `full_effect_at` to tune how many occurrences it takes to reach full
  strength -- the engine applies a diminishing-returns curve on top of
  whatever count your detection function returns, so you don't need to
  implement that yourself.
- **Write an honest `false_positives` string.** Every rule ships with one;
  it's shown in `slopscan rules show <id>` and it matters as much as the
  detection logic. If you can't think of a legitimate case where your rule
  would fire incorrectly, you probably haven't thought about it enough
  yet.
- **Point to real evidence.** Every `Evidence` should have a locator
  (file path, URL, or similar) wherever the corpus makes that possible.
  Findings without traceable evidence are much less useful to whoever
  reads the report.
- **Don't invent data.** If your rule can't verify something (e.g. whether
  a statistic is real), say so explicitly and cap `confidence` accordingly
  -- see `copy.fake_social_proof` for the pattern.
- **Add tests.** At minimum: one test showing a single/weak occurrence
  produces a low-strength (or no) finding, and one showing a repeated/
  strong occurrence produces a meaningfully stronger one. See
  `tests/test_rules_visual_copy.py`.

Once your module defines the rule, import it from
`src/slopscan/rules/__init__.py` if it's a new module (existing category
modules are already wired up).

### 4. Add a new analyzer / target type

See [docs/architecture.md](docs/architecture.md) for how `Target`,
`ScanCorpus`, and the rule engine fit together. The short version: a new
target type only needs to implement `collect() -> ScanCorpus`; nothing
downstream needs to change.

## Code style

- Formatted/linted with `ruff` (config in `pyproject.toml`).
- Type-checked with `mypy`; please don't introduce new `# type: ignore`
  without a comment explaining why it's needed.
- Prefer small, single-purpose modules over large ones -- the existing
  `rules/` package is the model to follow.

## Commit / PR expectations

- Keep PRs focused on one change where reasonably possible.
- If you're adding a rule, include the evidence/reasoning for why the
  pattern is worth detecting in the PR description -- it'll end up
  informing the rule's own `why_it_matters` text.
- Be upfront in the PR description about known false-positive risks for
  any new rule, even ones you haven't fully solved yet.

## Reporting security issues

Please don't open a public issue for a security vulnerability (e.g. an
SSRF or ZIP-extraction bypass). See [SECURITY.md](SECURITY.md).
