# SlopScan

SlopScan is a command-line tool that scans a website, a GitHub repository,
a local codebase, or a ZIP archive for patterns commonly associated with
AI-generated design and code -- generic SaaS templates, repetitive card
grids, gradient/glow overload, stock marketing copy, and similar signals --
and reports what it found, with evidence.

```
$ slopscan analyze ./my-landing-page

Target  ./my-landing-page

AI-SLOP LIKELIHOOD      78%
CONFIDENCE              86%

╭─ Breakdown ──────────────────────────────────────────────────────────╮
│ Visual         █████████████████░░░   84%                            │
│ Template       █████████████████░░░   89%                            │
│ Copy           ███████████████░░░░░   73%                            │
│ Repetition     ████████████████░░░░   82%                            │
╰─────────────────────────────────────────────────────────────────────╯

Top Findings

HIGH  Generic SaaS page structure
      Detected sequence: navbar -> hero -> features -> logos -> stats ->
      testimonials -> pricing -> faq -> cta -> footer (100% match)

HIGH  Repetitive card architecture
      9 structurally identical card elements detected

MED   Generic AI-style marketing phrases
      "transform your workflow", "the future of", "seamless experience"

...

This score measures AI-associated design and implementation patterns.
It does NOT prove AI authorship.
```

## What this is, and isn't

SlopScan is a **heuristic pattern analyzer**, not an authorship detector.
The score measures how strongly a target exhibits patterns that are
*statistically associated* with generic, template-driven, or AI-scaffolded
work -- repeated gradients, glow effects, cookie-cutter card grids, a
too-familiar SaaS section order, stock marketing phrases, and so on. It is
not a claim about who or what wrote the code, and it never asserts one.

SlopScan will never tell you a site was "definitely made by AI," name a
specific model that produced it, or claim certainty it doesn't have. If you
want that kind of accusation, this isn't the right tool -- and honestly, no
tool can currently give you that reliably.

What it's actually useful for, even if you ignore the "AI slop" framing
entirely: it's a **design-pattern and template-pattern analyzer**. It'll
tell you, with file-and-line evidence, why a site or codebase feels generic
-- 14 gradients, 9 repeated card structures, a stock SaaS page sequence,
7 stock marketing phrases -- so you can decide what to do about it.

## Installation

```bash
pip install slopscan-cli
```

Or from source:

```bash
git clone https://github.com/slopscan/slopscan
cd slopscan
pip install -e .
```

Requires Python 3.9+.

## Quick start

```bash
# A local project
slopscan analyze ./my-project

# A live website
slopscan analyze https://example.com

# A public GitHub repository
slopscan analyze https://github.com/someuser/somerepo

# A ZIP export
slopscan analyze ./project.zip
```

SlopScan auto-detects the target type from what you give it. No API key,
no account, no network access required for local/ZIP scans -- everything
runs on your machine.

## What it looks at

- **Visual**: gradients, glow/neon effects, glassmorphism, border and
  border-radius overuse, the purple/violet/indigo/cyan palette family
- **Template structure**: how closely the page section order matches the
  extremely common navbar → hero → features → logos → stats → testimonials
  → pricing → FAQ → CTA → footer sequence
- **Repetition**: near-identical card structures, card-in-card nesting,
  repeated icon+heading+description blocks
- **Copy**: stock marketing phrases ("transform your workflow", "the future
  of..."), buzzword density, unsourced statistic-style claims
- **Typography**: weak type hierarchy, generic default stacks with no
  supporting decisions, excessive uppercase micro-labels
- **Animation**: repetitive scroll-reveal effects, decorative infinite
  motion (floating/bouncing/pulsing everywhere)
- **Code**: duplicated code blocks, repeated component tags, repeated
  icon/heading/description JSX structures
- **Accessibility** (reported separately, never scored into the slop
  number): missing alt text, missing `prefers-reduced-motion` support

Run `slopscan rules list` to see the full current rule set, and
`slopscan rules show <rule-id>` for a full explanation of any one rule,
including its known false-positive cases.

**No single signal decides the score.** One gradient, one card, one
buzzword -- negligible. The score rises when many of these converge:
repetition, combination across categories, and a lack of anything
page-specific. See [docs/scoring.md](docs/scoring.md) for exactly how
that combination works, and [docs/rules.md](docs/rules.md) for the design
philosophy behind each category.

## Output formats

```bash
slopscan analyze ./project                          # terminal (default)
slopscan analyze ./project --format json             # machine-readable
slopscan analyze ./project --format markdown          # for PRs / docs
slopscan analyze ./project --format html --output report.html
```

JSON output is stable and documented -- see [docs/scoring.md](docs/scoring.md)
for the schema. It's meant for CI pipelines and other tooling.

## CI usage

```bash
slopscan analyze . --format json --fail-under 70
```

Exits non-zero if the score meets or exceeds the threshold. Exit codes:

| Code | Meaning |
|------|---------|
| 0 | Scan completed, threshold not exceeded (or no threshold set) |
| 1 | Scan completed, score >= `--fail-under` |
| 2 | Invalid CLI usage |
| 3 | Target error (network, filesystem, invalid archive, etc.) |
| 4 | Configuration error |

## Configuration

No configuration is required for normal use. If you want to tune it, drop
a `.slopscan.toml` in your project root:

```toml
[scan]
timeout = 15
max_file_size = 2_000_000
exclude = ["generated/", "vendor/"]

[score]
fail_under = 70
# weights.visual = 25   # override a category weight, 0-100 scale

[ai]
provider = "anthropic"
model = "claude-3-5-haiku-latest"
```

You can also drop a `.slopscanignore` file (same syntax as `.gitignore`)
in the scan root to exclude paths beyond the defaults (`node_modules`,
`.git`, `dist`, `build`, `venv`, etc.).

## Optional AI-enhanced mode

By default SlopScan is entirely deterministic -- no API key, no network
calls beyond fetching the target itself. If you want an additional layer
of semantic interpretation on top of the deterministic evidence:

```bash
export SLOPSCAN_AI_API_KEY=sk-...
slopscan analyze ./project --ai --ai-provider anthropic
```

Supported providers: `anthropic`, `openai`, `google`. See
[docs/ai-mode.md](docs/ai-mode.md) for exactly what gets sent (short
answer: aggregated evidence -- rule ids, categories, counts, short evidence
strings -- never your raw source code or full page content), and why the
AI layer can only add interpretation, never change the deterministic score.

## Privacy

- Local and ZIP scans never leave your machine.
- Website scans fetch only the requested page plus a small, bounded number
  of same-origin linked stylesheets -- nothing else, no crawling by default.
- GitHub scans use the public GitHub API to read file contents; nothing is
  cloned or executed.
- AI mode is opt-in and sends only aggregated evidence, never raw source.
- No telemetry. SlopScan doesn't phone home, ever.

See [SECURITY.md](SECURITY.md) for the full threat model (SSRF protection,
ZIP-bomb/path-traversal protection, and what SlopScan deliberately never
does, like installing dependencies or running scanned code).

## Architecture

```
slopscan/
├── cli/          Typer CLI: analyze, rules, config, doctor, version
├── core/         Models, the rule engine's scoring math, the pipeline
├── targets/      local dir / zip / url / github -> ScanCorpus
├── analyzers/    dependency detection (contextual, never scored)
├── rules/        the actual detectors, one small module per category
├── ai/           optional provider abstraction (anthropic/openai/google)
└── reports/      terminal (rich) / json / markdown / html renderers
```

See [docs/architecture.md](docs/architecture.md) for how a scan actually
flows through this, and how to add a new rule.

## Contributing

Contributions are welcome, especially:

- New rules (see [docs/rules.md](docs/rules.md) for what makes a good one)
- Additional generic-phrase entries in `rules/data/generic_phrases.json`
- False-positive fixture reports -- if SlopScan flagged something it
  shouldn't have, that's exactly the kind of issue we want

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
