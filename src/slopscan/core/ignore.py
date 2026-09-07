"""Ignore-pattern handling for local/archive scanning (spec section 30)."""

from __future__ import annotations

import fnmatch
from pathlib import Path

DEFAULT_IGNORED_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    ".cache",
    "__pycache__",
    "venv",
    ".venv",
    "coverage",
    ".next",
    "target",
    ".turbo",
    ".parcel-cache",
    "vendor",
    ".pytest_cache",
    "site-packages",
    ".mypy_cache",
    ".tox",
    "out",
}

# Extensions SlopScan actually knows how to analyze. Everything else is
# skipped early rather than loaded into memory for nothing.
SUPPORTED_EXTENSIONS = {
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".vue", ".svelte",
    ".py", ".json", ".md", ".markdown",
    "package.json", "requirements.txt", "pyproject.toml", "package-lock.json",
    "pnpm-lock.yaml", "yarn.lock", "cargo.toml", "go.mod",
}

MAX_FILE_BYTES_DEFAULT = 2_000_000  # 2MB -- spec section 70 default


def load_slopscanignore(root: Path) -> list[str]:
    ignore_file = root / ".slopscanignore"
    if not ignore_file.exists():
        return []
    patterns = []
    for line in ignore_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def is_ignored(rel_path: str, extra_patterns: list[str] | None = None) -> bool:
    parts = Path(rel_path).parts
    if any(p in DEFAULT_IGNORED_DIRS for p in parts):
        return True
    for pattern in extra_patterns or []:
        pattern = pattern.rstrip("/")
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, f"{pattern}/*") or any(
            fnmatch.fnmatch(part, pattern) for part in parts
        ):
            return True
    return False


def is_supported_file(path: str) -> bool:
    name = Path(path).name.lower()
    if name in SUPPORTED_EXTENSIONS:
        return True
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS
