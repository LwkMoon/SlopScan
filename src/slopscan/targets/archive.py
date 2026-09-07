"""ZIP archive scanning with security protections (spec section 31/76).

Threats handled explicitly:
- path traversal (entries containing "../" or absolute paths, or resolving
  outside the extraction directory after normalization -- checked both by
  name and by resolved path)
- zip bombs (per-file and total uncompressed-size limits, plus a sane
  compression-ratio ceiling)
- entry-count limits
- symlink entries (rejected outright -- never followed)
- the archive is never executed or have its scripts run; contents are only
  read as text for supported extensions
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from slopscan.core.ignore import MAX_FILE_BYTES_DEFAULT
from slopscan.core.source import ScanCorpus
from slopscan.targets.base import Target, TargetError

MAX_TOTAL_UNCOMPRESSED = 200_000_000  # 200MB
MAX_ENTRY_COUNT = 20_000
MAX_COMPRESSION_RATIO = 200  # a single entry expanding >200x is almost certainly a bomb


class ArchiveTarget(Target):
    def __init__(
        self,
        zip_path: str | Path,
        max_file_bytes: int = MAX_FILE_BYTES_DEFAULT,
        max_files: int = 3000,
    ) -> None:
        self.zip_path = Path(zip_path)
        self.max_file_bytes = max_file_bytes
        self.max_files = max_files

    def collect(self) -> ScanCorpus:
        if not self.zip_path.exists():
            raise TargetError(f"Archive not found: {self.zip_path}")
        if not zipfile.is_zipfile(self.zip_path):
            raise TargetError(f"Not a valid ZIP archive: {self.zip_path}")

        tmp_dir = Path(tempfile.mkdtemp(prefix="slopscan-zip-"))
        try:
            self._safe_extract(tmp_dir)
            from slopscan.targets.local import LocalDirTarget

            local = LocalDirTarget(tmp_dir, max_file_bytes=self.max_file_bytes, max_files=self.max_files)
            return local.collect()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _safe_extract(self, dest: Path) -> None:
        dest = dest.resolve()
        with zipfile.ZipFile(self.zip_path) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ENTRY_COUNT:
                raise TargetError(f"Archive contains too many entries (> {MAX_ENTRY_COUNT}); refusing to extract.")

            total_uncompressed = 0
            safe_infos = []
            for info in infos:
                name = info.filename
                if name.startswith("/") or name.startswith("\\"):
                    raise TargetError(f"Refusing to extract absolute path entry: {name}")
                if ".." in Path(name).parts:
                    raise TargetError(f"Refusing to extract path-traversal entry: {name}")
                # Symlinks: upper 16 bits of external_attr hold unix mode; S_IFLNK == 0xA000
                mode = (info.external_attr >> 16) & 0xFFFF
                if mode and (mode & 0xF000) == 0xA000:
                    continue  # silently skip symlinks -- never follow them

                target_path = (dest / name).resolve()
                if dest not in target_path.parents and target_path != dest:
                    raise TargetError(f"Refusing to extract entry escaping the target directory: {name}")

                # Bomb detection must happen before the "skip huge entries"
                # check below -- otherwise a bomb just gets silently skipped
                # instead of being flagged, which defeats the point.
                if info.compress_size > 0 and info.file_size / max(info.compress_size, 1) > MAX_COMPRESSION_RATIO:
                    raise TargetError(
                        f"Refusing to extract entry with suspicious compression ratio "
                        f"(possible zip bomb): {name}"
                    )
                if info.file_size > self.max_file_bytes * 4:
                    # skip individual huge (but not bomb-flagged) entries rather
                    # than aborting the whole scan
                    continue
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_TOTAL_UNCOMPRESSED:
                    raise TargetError(
                        "Archive's total uncompressed size exceeds the safety limit; refusing to extract."
                    )
                safe_infos.append(info)

            for info in safe_infos:
                zf.extract(info, path=dest)
