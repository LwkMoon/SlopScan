from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from slopscan.targets.archive import ArchiveTarget
from slopscan.targets.base import TargetError


def _make_zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return path


def test_rejects_path_traversal_entry(tmp_path):
    zpath = _make_zip(tmp_path / "evil.zip", {"../../etc/passwd": b"pwned"})
    with pytest.raises(TargetError, match="traversal"):
        ArchiveTarget(zpath).collect()


def test_rejects_absolute_path_entry(tmp_path):
    zip_path = tmp_path / "evil_abs.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        info = zipfile.ZipInfo("/etc/passwd")
        zf.writestr(info, b"pwned")
    with pytest.raises(TargetError, match="absolute"):
        ArchiveTarget(zip_path).collect()


def test_rejects_suspicious_compression_ratio(tmp_path):
    # A file that compresses extremely well but claims a huge uncompressed size
    zip_path = tmp_path / "bomb.zip"
    huge_content = b"0" * (5_000_000)  # highly compressible, ~5MB of zeros
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bomb.txt", huge_content)
    with pytest.raises(TargetError, match="compression ratio|safety limit"):
        ArchiveTarget(zip_path, max_file_bytes=1_000).collect()


def test_valid_archive_extracts_successfully(tmp_path):
    zpath = _make_zip(
        tmp_path / "good.zip",
        {
            "index.html": b"<html><body><h1>Hi</h1></body></html>",
            "styles.css": b".a { color: red; }",
            "node_modules/ignored.js": b"should be ignored",
        },
    )
    corpus = ArchiveTarget(zpath).collect()
    paths = {f.path for f in corpus.files}
    assert "index.html" in paths
    assert "styles.css" in paths
    assert not any("node_modules" in p for p in paths)


def test_rejects_missing_file(tmp_path):
    with pytest.raises(TargetError, match="not found"):
        ArchiveTarget(tmp_path / "does-not-exist.zip").collect()


def test_rejects_non_zip_file(tmp_path):
    fake = tmp_path / "not-a-zip.zip"
    fake.write_text("this is not a zip file")
    with pytest.raises(TargetError, match="valid ZIP"):
        ArchiveTarget(fake).collect()


def test_symlink_entries_are_skipped_not_followed(tmp_path):
    zip_path = tmp_path / "symlink.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        info = zipfile.ZipInfo("evil_link.html")
        info.external_attr = (0xA000 | 0o777) << 16  # S_IFLNK
        zf.writestr(info, "/etc/passwd")
        zf.writestr("real.html", "<html>ok</html>")
    corpus = ArchiveTarget(zip_path).collect()
    paths = {f.path for f in corpus.files}
    assert "evil_link.html" not in paths
    assert "real.html" in paths
