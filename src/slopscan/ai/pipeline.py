"""Deterministic evidence -> AI semantic interpretation (spec section 42/43).

    Deterministic Scanner -> Evidence -> AI Semantic Analysis
    -> Additional Interpretation -> Final Report

The model receives only the aggregated JSON evidence (rule ids, categories,
severities, occurrence counts, short evidence strings) -- never raw source
files or full page HTML. It is explicitly instructed to interpret, not
verdict, and its output is stored as a clearly-separated `AIInterpretation`
that reports render in its own section, never merged into deterministic
findings or allowed to change `slop_score`.
"""

from __future__ import annotations

import json

from slopscan.ai.provider import AICompletionRequest, AIProviderError, get_provider
from slopscan.core.models import AIInterpretation, ScanResult

_SYSTEM_PROMPT = """You are assisting a static-analysis CLI tool called SlopScan.

You will be given structured, aggregated evidence already collected by a
deterministic rule engine that scanned a website or codebase for patterns
associated with AI-generated or generic template-driven design and code.
You have NOT seen the raw source; you only have this evidence.

Your job is to add brief, calibrated interpretation on top of the evidence
-- noting which combinations of signals are most/least meaningful together,
and any patterns in the evidence worth highlighting to a developer.

Rules you must follow:
- Never claim the target was definitely made by AI, or name a specific AI
  tool/model as having produced it. You do not have that information.
- Never invent findings, statistics, or evidence not present in the input.
- Be concise: a short summary (2-4 sentences), a few notable observations,
  and 1-2 caveats about the limits of this analysis.
- Your output is always presented to the user as a separate, clearly-
  labeled "AI-assisted interpretation" section alongside the deterministic
  findings -- it does not replace them and cannot change the score.

Respond ONLY with JSON matching this shape, no other text:
{"summary": "...", "notable_observations": ["...", "..."], "caveats": ["...", "..."]}
"""


def run_ai_interpretation(
    result: ScanResult,
    provider_id: str,
    api_key: str,
    model: str | None = None,
) -> AIInterpretation:
    provider = get_provider(provider_id, api_key=api_key, model=model)
    evidence_payload = json.dumps(result.as_summary_dict(), indent=2)
    request = AICompletionRequest(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=f"Deterministic scan evidence:\n\n{evidence_payload}",
        max_tokens=700,
    )
    response = provider.complete(request)
    parsed = _parse_response(response.text)

    return AIInterpretation(
        provider=response.provider,
        model=response.model,
        summary=parsed.get("summary", "").strip() or "No summary returned.",
        notable_observations=[str(o) for o in parsed.get("notable_observations", [])],
        caveats=[str(c) for c in parsed.get("caveats", [])] or [
            "This interpretation is a probabilistic reading of the deterministic evidence "
            "and does not independently verify AI authorship."
        ],
    )


def _parse_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Model didn't return clean JSON -- degrade gracefully rather than crash.
        return {"summary": text[:600], "notable_observations": [], "caveats": []}


__all__ = ["run_ai_interpretation", "AIProviderError"]
