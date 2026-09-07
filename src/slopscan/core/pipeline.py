"""The deterministic analysis pipeline.

    ScanCorpus -> [run every registered rule] -> Findings
               -> positive-signal detection
               -> scoring.compute_score
               -> ScanResult

This is deliberately target-agnostic: `run_pipeline` doesn't know or care
whether the corpus came from a local dir, a zip, a URL, or GitHub.
"""

from __future__ import annotations

import time

from slopscan.core.config import ScanConfig
from slopscan.core.ignore import is_ignored
from slopscan.core.models import Category, ScanResult, ScanStats, TargetType
from slopscan.core.positive_signals import detect_positive_signals
from slopscan.core.scoring import DEFAULT_CATEGORY_WEIGHTS, compute_score
from slopscan.core.source import ScanCorpus
from slopscan.rules import all_rules
from slopscan.rules.registry import RuleContext


def _apply_extra_excludes(corpus: ScanCorpus, exclude_patterns: list[str]) -> ScanCorpus:
    if not exclude_patterns:
        return corpus
    kept = [f for f in corpus.files if not is_ignored(f.path, exclude_patterns)]
    corpus.skipped_count += len(corpus.files) - len(kept)
    corpus.files = kept
    return corpus


def _weights_with_overrides(overrides: dict[str, float]) -> dict[Category, float]:
    if not overrides:
        return DEFAULT_CATEGORY_WEIGHTS
    weights = dict(DEFAULT_CATEGORY_WEIGHTS)
    for key, value in overrides.items():
        try:
            weights[Category(key)] = float(value)
        except ValueError:
            continue  # unknown category name in config -- ignore rather than crash
    return weights


def run_pipeline(
    corpus: ScanCorpus,
    target: str,
    target_type: TargetType,
    config: ScanConfig | None = None,
) -> ScanResult:
    start = time.monotonic()
    config = config or ScanConfig()
    corpus = _apply_extra_excludes(corpus, config.exclude)

    ctx = RuleContext(corpus=corpus, config={})
    findings = []
    for r in all_rules():
        finding = r.run(ctx)
        if finding is not None:
            findings.append(finding)

    positive_signals = detect_positive_signals(corpus)

    stats = ScanStats(
        files_scanned=len(corpus.files),
        files_skipped=corpus.skipped_count,
        bytes_scanned=corpus.total_bytes,
        rules_evaluated=len(all_rules()),
        duration_seconds=round(time.monotonic() - start, 3),
        rendered=corpus.rendered,
        source_available=corpus.source_available,
    )

    weights = _weights_with_overrides(config.score.weights)
    scoring = compute_score(findings, stats, weights=weights)

    warnings: list[str] = []
    if corpus.truncated:
        warnings.append("Scan was truncated: the target contains more files than the configured limit.")
    if not corpus.files:
        warnings.append("No supported files were found to analyze.")

    return ScanResult(
        target=target,
        target_type=target_type,
        slop_score=scoring.slop_score,
        confidence=scoring.confidence,
        categories=scoring.category_scores,
        findings=findings,
        positive_signals=positive_signals,
        stats=stats,
        warnings=warnings,
    )
