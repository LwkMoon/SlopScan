"""Top-level entry point used by the CLI: resolve a raw target string into
a Target, collect its corpus, and run it through the pipeline."""

from __future__ import annotations

from slopscan.core.config import ScanConfig
from slopscan.core.models import ScanResult, TargetType
from slopscan.core.pipeline import run_pipeline
from slopscan.targets.archive import ArchiveTarget
from slopscan.targets.base import Target, TargetError
from slopscan.targets.detect import detect_target_type
from slopscan.targets.github import GithubTarget
from slopscan.targets.local import LocalDirTarget
from slopscan.targets.url import UrlTarget

__all__ = ["scan", "TargetError", "detect_target_type"]


def _build_target(raw: str, target_type: TargetType, config: ScanConfig) -> Target:
    if target_type == TargetType.LOCAL_DIR:
        return LocalDirTarget(raw, max_file_bytes=config.max_file_size, max_files=config.max_files)
    if target_type == TargetType.ARCHIVE:
        return ArchiveTarget(raw, max_file_bytes=config.max_file_size, max_files=config.max_files)
    if target_type == TargetType.URL:
        return UrlTarget(raw, timeout=config.timeout, max_pages=config.max_pages)
    if target_type == TargetType.GITHUB:
        return GithubTarget(
            raw,
            max_files=min(config.max_files, 300),
            max_file_bytes=config.max_file_size,
            timeout=config.timeout,
        )
    raise TargetError(f"Unsupported target type: {target_type}")


def scan(
    raw_target: str,
    config: ScanConfig | None = None,
    target_type: TargetType | None = None,
) -> ScanResult:
    config = config or ScanConfig()
    resolved_type = target_type or detect_target_type(raw_target)
    target = _build_target(raw_target, resolved_type, config)
    corpus = target.collect()
    return run_pipeline(corpus, target=raw_target, target_type=resolved_type, config=config)
