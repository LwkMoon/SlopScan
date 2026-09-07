"""The unit of content that analyzers operate on.

Every target type (local dir, zip, URL, GitHub repo) ultimately produces a
list of `SourceFile` objects. This is the seam that lets analyzers stay
completely target-agnostic: an HTML analyzer doesn't know or care whether
its input came from disk or from a live HTTP fetch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceKind(str, Enum):
    HTML = "html"
    CSS = "css"
    JS = "js"
    JSX = "jsx"
    PY = "py"
    JSON = "json"
    MARKDOWN = "markdown"
    TEXT = "text"
    OTHER = "other"


_EXTENSION_MAP: dict[str, SourceKind] = {
    ".html": SourceKind.HTML,
    ".htm": SourceKind.HTML,
    ".css": SourceKind.CSS,
    ".scss": SourceKind.CSS,
    ".sass": SourceKind.CSS,
    ".less": SourceKind.CSS,
    ".js": SourceKind.JS,
    ".mjs": SourceKind.JS,
    ".cjs": SourceKind.JS,
    ".ts": SourceKind.JS,
    ".jsx": SourceKind.JSX,
    ".tsx": SourceKind.JSX,
    ".vue": SourceKind.JSX,
    ".svelte": SourceKind.JSX,
    ".py": SourceKind.PY,
    ".json": SourceKind.JSON,
    ".md": SourceKind.MARKDOWN,
    ".markdown": SourceKind.MARKDOWN,
}


def kind_for_path(path: str) -> SourceKind:
    lower = path.lower()
    for ext, kind in _EXTENSION_MAP.items():
        if lower.endswith(ext):
            return kind
    return SourceKind.OTHER


@dataclass
class SourceFile:
    """A single scannable file, wherever it came from.

    `path` is the traceable locator shown in findings (e.g.
    "src/components/Hero.tsx" or "https://example.com" for the page itself).
    """

    path: str
    content: str
    kind: SourceKind
    size_bytes: int = 0

    def __post_init__(self) -> None:
        if not self.size_bytes:
            self.size_bytes = len(self.content.encode("utf-8", errors="ignore"))


@dataclass
class ScanCorpus:
    """All source files collected for one scan, plus lightweight metadata."""

    files: list[SourceFile] = field(default_factory=list)
    rendered: bool = False
    source_available: bool = True
    skipped_count: int = 0
    truncated: bool = False

    def by_kind(self, *kinds: SourceKind) -> list[SourceFile]:
        return [f for f in self.files if f.kind in kinds]

    @property
    def total_bytes(self) -> int:
        return sum(f.size_bytes for f in self.files)
