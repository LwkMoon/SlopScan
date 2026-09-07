"""Determine what kind of target the user gave us (spec section 3)."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from slopscan.core.models import TargetType

_GITHUB_HOST_RE = re.compile(r"^(www\.)?github\.com$", re.IGNORECASE)


def detect_target_type(raw: str) -> TargetType:
    parsed = urlparse(raw)
    if parsed.scheme in ("http", "https"):
        host = (parsed.hostname or "").lower()
        if _GITHUB_HOST_RE.match(host):
            return TargetType.GITHUB
        return TargetType.URL

    path = Path(raw)
    if path.suffix.lower() == ".zip":
        return TargetType.ARCHIVE
    if path.is_dir() or (not path.exists() and not path.suffix):
        return TargetType.LOCAL_DIR
    if path.is_file() and path.suffix.lower() == ".zip":
        return TargetType.ARCHIVE

    # Fall back on existence checks for edge cases (e.g. relative paths that
    # don't exist yet at detection time but look directory-like).
    if path.exists():
        return TargetType.LOCAL_DIR if path.is_dir() else TargetType.ARCHIVE
    return TargetType.LOCAL_DIR
