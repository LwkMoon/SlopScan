"""JSON report (spec section 6/85). Stable, documented shape -- no terminal
formatting leaks into it. This is what `--format json` and CI/SARIF-adjacent
tooling should rely on.
"""

from __future__ import annotations

import json

from slopscan.core.models import ScanResult


def render_json(result: ScanResult, indent: int = 2) -> str:
    payload = {
        "slopscan_version": result.slopscan_version,
        "target": result.target,
        "target_type": result.target_type.value,
        "scanned_at": result.scanned_at,
        "slop_score": result.slop_score,
        "confidence": result.confidence,
        "categories": {
            c.category.value: {
                "score": c.score,
                "weight": c.weight,
                "finding_count": c.finding_count,
                "top_rule_ids": c.top_rule_ids,
            }
            for c in result.categories
        },
        "findings": [
            {
                "rule_id": f.rule_id,
                "category": f.category.value,
                "severity": f.severity.value,
                "title": f.title,
                "description": f.description,
                "occurrences": f.occurrences,
                "strength": round(f.strength, 4),
                "confidence": round(f.confidence, 4),
                "evidence": [
                    {"description": e.description, "locator": e.locator, "snippet": e.snippet}
                    for e in f.evidence
                ],
                "false_positive_note": f.false_positive_note,
            }
            for f in result.findings
        ],
        "positive_signals": [
            {"signal_id": p.signal_id, "description": p.description} for p in result.positive_signals
        ],
        "stats": result.stats.model_dump(),
        "ai_interpretation": result.ai_interpretation.model_dump() if result.ai_interpretation else None,
        "warnings": result.warnings,
        "disclaimer": (
            "This score measures the presence of patterns statistically associated with "
            "AI-generated or generic template-driven work. It does not prove AI authorship."
        ),
    }
    return json.dumps(payload, indent=indent, sort_keys=False)
