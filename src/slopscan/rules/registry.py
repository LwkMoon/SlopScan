"""The rule engine.

A `Rule` is a small, self-contained detector: it looks at a `ScanCorpus`
and returns zero or one `Finding`. Rules are intentionally *not* allowed to
know about scoring weights or other rules -- that separation is what keeps
"detect a pattern" and "decide how much it matters" independent, which is
what section 35/36 of the project spec (avoid double counting, transparent
scoring) actually requires in practice.

Rules register themselves via the `@rule(...)` decorator into a module-level
`REGISTRY`. `rules/visual.py`, `rules/copy.py`, etc. each populate a slice of
it; `slopscan rules list` / `slopscan rules show <id>` read directly from it.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from slopscan.core.models import Category, Evidence, Finding, Severity
from slopscan.core.source import ScanCorpus

DetectFn = Callable[["RuleContext"], "DetectionResult | None"]


@dataclass
class RuleContext:
    """What a detection function receives. Kept minimal on purpose so
    rules can be unit tested with a bare ScanCorpus."""

    corpus: ScanCorpus
    config: dict = field(default_factory=dict)


@dataclass
class DetectionResult:
    """What a detection function returns when its pattern is present.

    `occurrences` drives the diminishing-returns strength curve (see
    Rule.strength_from_count). `evidence` should be concrete and traceable;
    keep it short here -- deduplication/truncation for display happens in
    the report layer, not here.
    """

    occurrences: int
    evidence: list[Evidence]
    confidence: float = 1.0
    detail: str | None = None


@dataclass
class Rule:
    id: str
    name: str
    category: Category
    base_severity: Severity
    description: str
    why_it_matters: str
    false_positives: str
    detect: DetectFn
    full_effect_at: int = 10
    """Occurrence count at which strength saturates near 1.0. Lower this for
    rules where even a few occurrences are meaningful (e.g. fake social
    proof); raise it for rules that are only meaningful in bulk (e.g. a
    generic SaaS section sequence, which either matches or doesn't, vs.
    gradient count which needs real repetition to mean something)."""

    def strength_from_count(self, occurrences: int) -> float:
        """Diminishing-returns activation curve.

        One occurrence of almost anything is unremarkable; strength should
        rise quickly then flatten, so rule 15 doesn't count for 15x rule 1.
        This is the concrete mechanism behind section 88's "one gradient:
        negligible, fourteen gradients: stronger" requirement.
        """
        if occurrences <= 0:
            return 0.0
        return 1.0 - math.exp(-occurrences / max(self.full_effect_at, 1))

    def run(self, ctx: RuleContext) -> Finding | None:
        result = self.detect(ctx)
        if result is None or result.occurrences <= 0:
            return None
        strength = self.strength_from_count(result.occurrences)
        return Finding(
            rule_id=self.id,
            category=self.category,
            severity=self._severity_for(strength),
            title=self.name,
            description=self.description,
            occurrences=result.occurrences,
            strength=strength,
            confidence=result.confidence,
            evidence=result.evidence,
            false_positive_note=self.false_positives,
        )

    def _severity_for(self, strength: float) -> Severity:
        """A rule's configured severity is its *ceiling*; a weakly-triggered
        rule is downgraded so a single occurrence never reads as HIGH."""
        order = self.base_severity.order
        if strength < 0.25:
            order = min(order, Severity.LOW.order)
        elif strength < 0.55:
            order = min(order, Severity.MEDIUM.order)
        for sev in Severity:
            if sev.order == order:
                return sev
        return self.base_severity


REGISTRY: dict[str, Rule] = {}


def rule(
    id: str,
    name: str,
    category: Category,
    severity: Severity,
    description: str,
    why_it_matters: str,
    false_positives: str,
    full_effect_at: int = 10,
) -> Callable[[DetectFn], DetectFn]:
    """Decorator that registers a detection function as a Rule."""

    def wrapper(fn: DetectFn) -> DetectFn:
        REGISTRY[id] = Rule(
            id=id,
            name=name,
            category=category,
            base_severity=severity,
            description=description,
            why_it_matters=why_it_matters,
            false_positives=false_positives,
            detect=fn,
            full_effect_at=full_effect_at,
        )
        return fn

    return wrapper


def all_rules() -> list[Rule]:
    return sorted(REGISTRY.values(), key=lambda r: r.id)


def get_rule(rule_id: str) -> Rule | None:
    return REGISTRY.get(rule_id)


def rules_by_category(category: Category) -> list[Rule]:
    return [r for r in all_rules() if r.category == category]
