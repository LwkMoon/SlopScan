# AI-Enhanced Mode

SlopScan's default mode is entirely deterministic: rule-based, offline
(for local/ZIP targets), and fully explainable. `--ai` adds an optional
extra layer of semantic interpretation on top of that -- it never
replaces it.

## What actually happens with `--ai`

```
Deterministic scan (as always)
        │
        ▼
ScanResult (score, categories, findings, positive signals -- final and fixed)
        │
        ▼
ScanResult.as_summary_dict()   <- aggregated evidence only
        │
        ▼
ai.pipeline.run_ai_interpretation()  -- one API call to the configured provider
        │
        ▼
AIInterpretation (summary, notable_observations, caveats)
        │
        ▼
Attached to ScanResult.ai_interpretation, rendered in its own
clearly-labeled section by every report format
```

The deterministic `slop_score` and `confidence` are computed **before**
this step and are never modified by it. The AI layer can add commentary;
it cannot change the number.

## Exactly what gets sent to the provider

`ScanResult.as_summary_dict()` -- look at that method in
`src/slopscan/core/models.py` for the literal implementation. It contains:

- The target string and target type
- The final `slop_score` and `confidence`
- Per-category scores
- Per-finding: rule id, category, severity, occurrence count, strength,
  and up to 5 short evidence *strings* (e.g. `"14 gradient declarations
  detected across the scanned surfaces"`) -- not file contents
- Positive-signal descriptions

**Never sent:** raw HTML/CSS/JS source, full page content, file contents,
your API key (obviously), or anything not already aggregated into the
deterministic report.

The system prompt (`ai/pipeline.py::_SYSTEM_PROMPT`) explicitly instructs
the model to interpret the evidence, never assert AI authorship, never
name a specific AI tool as having produced the target, and never invent
findings not present in the input.

## Supported providers

| Provider | `--ai-provider` | Default model |
|---|---|---|
| Anthropic | `anthropic` | `claude-3-5-haiku-latest` |
| OpenAI | `openai` | `gpt-4o-mini` |
| Google | `google` | `gemini-1.5-flash` |

Override the model with `--ai-model` or the `SLOPSCAN_AI_MODEL`
environment variable / `[ai].model` in `.slopscan.toml`.

Adding a new provider means implementing `ai.provider.AIProvider` and
registering it in `ai.provider.get_provider` -- see
`ai/anthropic_provider.py` for the reference implementation. Nothing else
in the codebase needs to change.

## API key handling

```bash
export SLOPSCAN_AI_API_KEY=sk-...
export SLOPSCAN_AI_PROVIDER=anthropic   # optional, --ai-provider overrides this
slopscan analyze ./project --ai
```

- The key is only ever read from the `SLOPSCAN_AI_API_KEY` environment
  variable (or `GITHUB_TOKEN`/`SLOPSCAN_GITHUB_TOKEN` for the unrelated
  GitHub-API rate-limit case).
- SlopScan never writes an API key to `.slopscan.toml`, logs, reports, or
  anywhere else on disk. `slopscan config` explicitly excludes it from its
  output.
- If `--ai` is set but no key is configured, SlopScan prints a plain
  warning and continues with the deterministic result only -- it never
  fails the whole scan just because AI mode couldn't run.
- If the provider call fails for any reason (network, rate limit, bad
  response), the same graceful degradation applies: a warning, and the
  deterministic report proceeds unaffected.

## Why this design

Sending an entire website or codebase to an LLM and asking "is this AI?"
would be both a privacy problem (your source code leaves your machine)
and a quality problem (LLMs are not reliable authorship detectors, and a
vague open-ended question invites exactly the kind of overconfident,
unfalsifiable answer this project is trying to avoid). Sending only
structured, already-aggregated evidence and asking for *interpretation of
that evidence* keeps the deterministic layer as the source of truth, and
keeps what leaves your machine limited to numbers and short strings you
could regenerate yourself by reading the JSON report.
