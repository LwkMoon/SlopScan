# Architecture

## The pipeline, end to end

```
raw target string (CLI arg)
        │
        ▼
targets.detect.detect_target_type()      -- URL / GitHub / local dir / archive
        │
        ▼
targets.{local,archive,url,github}.Target.collect()
        │
        ▼
core.source.ScanCorpus                   -- list[SourceFile], target-agnostic
        │
        ▼
core.pipeline.run_pipeline()
        │  ├─ rules.all_rules() -> each Rule.run(ctx) -> Finding | None
        │  ├─ core.positive_signals.detect_positive_signals()
        │  └─ core.scoring.compute_score()
        ▼
core.models.ScanResult
        │
        ├─ (optional) ai.pipeline.run_ai_interpretation()  -- adds AIInterpretation
        ▼
reports.{terminal,json,markdown,html}.render_*()
```

Everything to the left of `ScanResult` doesn't know anything about the
CLI, and everything to the right of it doesn't know anything about where
the corpus came from. That separation is deliberate and is what makes
each piece independently testable (see `tests/`).

## Key types

- **`SourceFile`** (`core/source.py`): one scannable file -- a path
  (used as the traceable locator in evidence), content, and a `SourceKind`
  (HTML/CSS/JS/JSX/PY/JSON/MARKDOWN/OTHER) inferred from the extension.
- **`ScanCorpus`**: all `SourceFile`s for one scan, plus metadata
  (`rendered`, `source_available`, `truncated`, `skipped_count`) that
  feeds into confidence calculation.
- **`Rule`** (`rules/registry.py`): a detector. Rules self-register via
  the `@rule(...)` decorator into a module-level `REGISTRY`. A rule's
  `detect()` function returns a `DetectionResult` (occurrence count +
  evidence) or `None`; the `Rule.run()` wrapper turns that into a
  `Finding` with severity and strength already computed.
- **`Finding`**: the output of one rule against one corpus. Carries
  `strength` (0-1, already diminishing-returns-adjusted) and `confidence`
  (0-1, the rule's own certainty about its evidence) separately.
- **`ScanResult`**: the complete, self-contained output of a scan. This is
  what every report renderer consumes, and it's the stable shape behind
  `--format json`.

## Adding a new target type

Implement `targets.base.Target`:

```python
class MyTarget(Target):
    def collect(self) -> ScanCorpus:
        ...  # fetch/read content, wrap each file in a SourceFile
        return ScanCorpus(files=[...], rendered=False, source_available=True)
```

Wire it into `targets.detect.detect_target_type` (if it needs its own
detection logic) and `core.scanner._build_target`. Nothing in
`rules/`, `core/scoring.py`, or `reports/` needs to change.

## Adding a new rule

See [CONTRIBUTING.md](../CONTRIBUTING.md#3-add-a-new-rule) for the
practical how-to, and [docs/rules.md](rules.md) for the design philosophy
each rule is expected to follow (frequency-gating, honest false-positive
notes, traceable evidence).

## Adding a new report format

Implement a `render_xxx(result: ScanResult) -> str` function in
`reports/`, add it to `reports/__init__.py`, and wire the `--format`
choice into `cli/output.write_report`. Report renderers are pure
functions of `ScanResult` -- they never call back into the scan pipeline
or do their own analysis.

## Why regex/BeautifulSoup instead of a full CSS/JS parser

CSS and JS rules in this codebase use regex over raw source rather than a
real AST (tree-sitter, a CSS parser, etc.). This is a deliberate trade-off:
SlopScan's rules care about the *frequency and presence* of patterns
(how many gradients, how many `box-shadow` glow declarations), not
refactor-grade syntactic precision. A full parser would improve accuracy
at the margins for a much heavier dependency footprint. HTML analysis
does use a real tree (BeautifulSoup) because DOM structure -- nesting,
sibling similarity, section ordering -- genuinely can't be approximated
well with regex. If a future contribution wants to swap in tree-sitter
for JS/CSS, the `rules/` module boundary is exactly where that would slot
in without touching anything else.
