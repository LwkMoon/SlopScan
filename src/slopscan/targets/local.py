"""Local directory scanning (spec section 30)."""

from __future__ import annotations

from pathlib import Path

from slopscan.core.ignore import (
    MAX_FILE_BYTES_DEFAULT,
    is_ignored,
    is_supported_file,
    load_slopscanignore,
)
from slopscan.core.source import ScanCorpus, SourceFile, kind_for_path
from slopscan.targets.base import Target, TargetError


class LocalDirTarget(Target):
    def __init__(
        self,
        root: str | Path,
        max_file_bytes: int = MAX_FILE_BYTES_DEFAULT,
        max_files: int = 3000,
        extra_ignore: list[str] | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.max_file_bytes = max_file_bytes
        self.max_files = max_files
        self.extra_ignore = extra_ignore or []

    def collect(self) -> ScanCorpus:
        if not self.root.exists():
            raise TargetError(f"Path does not exist: {self.root}")
        if not self.root.is_dir():
            raise TargetError(f"Not a directory: {self.root}")

        patterns = self.extra_ignore + load_slopscanignore(self.root)
        corpus = ScanCorpus(rendered=False, source_available=True)

        for path in sorted(self.root.rglob("*")):
            if len(corpus.files) >= self.max_files:
                corpus.truncated = True
                break
            if not path.is_file():
                continue
            rel = str(path.relative_to(self.root))
            if is_ignored(rel, patterns):
                continue
            if not is_supported_file(rel):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > self.max_file_bytes:
                corpus.skipped_count += 1
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                corpus.skipped_count += 1
                continue
            corpus.files.append(SourceFile(path=rel, content=content, kind=kind_for_path(rel), size_bytes=size))

        return corpus
