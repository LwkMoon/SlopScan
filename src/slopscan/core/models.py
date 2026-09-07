"""Core data model shared by analyzers, the rule engine, scoring, and reports.

Everything downstream of a scan (terminal output, JSON, markdown, HTML,
the optional AI interpretation layer) consumes these types. Keeping them
in one place is what makes the report format stable and the pipeline
testable independently of any single analyzer.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """How strong an individual finding's signal is, on its own.

    Severity is about the *pattern*, not the final score -- a HIGH severity
    finding that only fires once still contributes very little to the
    overall score. See core.scoring for how severity and frequency combine.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def order(self) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}[self.value]


class Category(str, Enum):
    """Top-level scoring categories. See core.scoring for default weights."""

    VISUAL = "visual"
    CODE = "code"
    TEMPLATE = "template"
    COPY = "copy"
    REPETITION = "repetition"
    TYPOGRAPHY = "typography"
    ANIMATION = "animation"
    COMPONENTS = "components"
    ACCESSIBILITY = "accessibility"  # reported, but excluded from the slop score
    OTHER = "other"


class TargetType(str, Enum):
    URL = "url"
    GITHUB = "github"
    LOCAL_DIR = "local_dir"
    ARCHIVE = "archive"


class Evidence(BaseModel):
    """One concrete, traceable piece of support for a finding.

    `locator` should point somewhere real whenever possible: a file path
    (optionally with a line number), a URL, or a DOM/CSS selector. SlopScan
    never fabricates evidence -- if an analyzer can't point to where a
    pattern occurred, it should lower its confidence instead of inventing
    a locator.
    """

    description: str
    locator: str | None = None
    snippet: str | None = None


class Finding(BaseModel):
    """The output of a single rule evaluated against a single target.

    `strength` (0..1) is the rule's own estimate of how strongly its
    pattern is present, already accounting for frequency via a diminishing
    -returns curve (see rules.registry.Rule.strength_from_count). It is
    *not* the same as the score contribution -- that also factors in
    category weight and combination with sibling rules (core.scoring).
    """

    rule_id: str
    category: Category
    severity: Severity
    title: str
    description: str
    occurrences: int = 0
    strength: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    evidence: list[Evidence] = Field(default_factory=list)
    false_positive_note: str | None = None

    def evidence_strings(self, limit: int | None = None) -> list[str]:
        items = [e.description for e in self.evidence]
        return items[:limit] if limit else items


class CategoryScore(BaseModel):
    category: Category
    score: float = Field(ge=0.0, le=100.0)
    weight: float
    finding_count: int
    top_rule_ids: list[str] = Field(default_factory=list)


class PositiveSignal(BaseModel):
    """A detected characteristic that argues *against* genericness.

    These never subtract points mechanically (that would just invite
    gaming); they exist to contextualize the report and feed the AI
    interpretation layer when it's enabled.
    """

    signal_id: str
    description: str
    evidence: list[Evidence] = Field(default_factory=list)


class ScanStats(BaseModel):
    files_scanned: int = 0
    files_skipped: int = 0
    bytes_scanned: int = 0
    rules_evaluated: int = 0
    duration_seconds: float = 0.0
    rendered: bool = False
    source_available: bool = True


class AIInterpretation(BaseModel):
    """Output of the optional AI-enhanced semantic layer (see ai/pipeline.py).

    This is always additive and clearly separated from deterministic
    findings in every report format -- it never silently changes the
    deterministic score.
    """

    provider: str
    model: str
    summary: str
    notable_observations: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


class ScanResult(BaseModel):
    """The complete, self-contained output of a scan.

    This is what every report renderer (terminal/json/markdown/html)
    consumes, and it is the stable machine-readable contract for
    `--format json` (see docs/scoring.md and reports/json_report.py).
    """

    target: str
    target_type: TargetType
    slop_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=100.0)
    categories: list[CategoryScore]
    findings: list[Finding]
    positive_signals: list[PositiveSignal] = Field(default_factory=list)
    stats: ScanStats
    ai_interpretation: AIInterpretation | None = None
    scanned_at: float = Field(default_factory=time.time)
    slopscan_version: str = "0.1.0"
    warnings: list[str] = Field(default_factory=list)

    def findings_by_severity(self) -> dict[Severity, list[Finding]]:
        out: dict[Severity, list[Finding]] = {s: [] for s in Severity}
        for f in self.findings:
            out[f.severity].append(f)
        return out

    def top_findings(self, limit: int | None = 6) -> list[Finding]:
        ranked = sorted(
            self.findings,
            key=lambda f: (f.severity.order, f.strength * f.confidence),
            reverse=True,
        )
        return ranked[:limit] if limit is not None else ranked

    def category_score(self, category: Category) -> float | None:
        for c in self.categories:
            if c.category == category:
                return c.score
        return None

    def as_summary_dict(self) -> dict[str, Any]:
        """A compact dict used by the AI interpretation layer as structured
        evidence -- never the raw source, just aggregated signals."""
        return {
            "target": self.target,
            "target_type": self.target_type.value,
            "slop_score": self.slop_score,
            "confidence": self.confidence,
            "categories": {c.category.value: c.score for c in self.categories},
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "category": f.category.value,
                    "severity": f.severity.value,
                    "occurrences": f.occurrences,
                    "strength": round(f.strength, 3),
                    "evidence": f.evidence_strings(limit=5),
                }
                for f in self.findings
            ],
            "positive_signals": [p.description for p in self.positive_signals],
        }
