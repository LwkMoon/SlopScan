"""Configuration loading (spec section 70/71).

Precedence, lowest to highest: built-in defaults -> .slopscan.toml in the
scan root (or cwd) -> environment variables -> explicit CLI flags. Basic
usage never requires a config file or environment variables at all.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from slopscan.core.ignore import MAX_FILE_BYTES_DEFAULT


class AIConfig(BaseModel):
    enabled: bool = False
    provider: str = "anthropic"
    model: str | None = None
    api_key: str | None = None  # never persisted to disk by SlopScan itself


class ScoreConfig(BaseModel):
    fail_under: int | None = None
    weights: dict[str, float] = Field(default_factory=dict)  # category -> weight override


class ScanConfig(BaseModel):
    timeout: float = 15.0
    max_file_size: int = MAX_FILE_BYTES_DEFAULT
    max_files: int = 3000
    exclude: list[str] = Field(default_factory=list)
    crawl: bool = False
    max_pages: int = 1
    ai: AIConfig = Field(default_factory=AIConfig)
    score: ScoreConfig = Field(default_factory=ScoreConfig)


def _load_toml_file(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_config(search_root: Path | None = None) -> ScanConfig:
    search_root = search_root or Path.cwd()
    raw: dict = {}
    for candidate in (search_root / ".slopscan.toml", Path.cwd() / ".slopscan.toml"):
        data = _load_toml_file(candidate)
        if data:
            raw = data
            break

    scan_section = raw.get("scan", {})
    score_section = raw.get("score", {})
    ai_section = raw.get("ai", {})

    config = ScanConfig(
        timeout=scan_section.get("timeout", 15.0),
        max_file_size=scan_section.get("max_file_size", MAX_FILE_BYTES_DEFAULT),
        max_files=scan_section.get("max_files", 3000),
        exclude=scan_section.get("exclude", []),
        crawl=scan_section.get("crawl", False),
        max_pages=scan_section.get("max_pages", 1),
        score=ScoreConfig(
            fail_under=score_section.get("fail_under"),
            weights=score_section.get("weights", {}),
        ),
        ai=AIConfig(
            enabled=ai_section.get("enabled", False),
            provider=ai_section.get("provider", "anthropic"),
            model=ai_section.get("model"),
        ),
    )

    # Environment variables can override AI settings (never the API key from
    # the TOML file -- keys should only ever come from the environment or a
    # session-only flag; see spec section 41).
    env_provider = os.environ.get("SLOPSCAN_AI_PROVIDER")
    env_model = os.environ.get("SLOPSCAN_AI_MODEL")
    env_key = os.environ.get("SLOPSCAN_AI_API_KEY")
    if env_provider:
        config.ai.provider = env_provider
    if env_model:
        config.ai.model = env_model
    if env_key:
        config.ai.api_key = env_key

    return config
