from __future__ import annotations

from slopscan.core.models import TargetType
from slopscan.targets.detect import detect_target_type
from slopscan.targets.github import parse_github_url


def test_detects_https_url():
    assert detect_target_type("https://example.com") == TargetType.URL


def test_detects_http_url():
    assert detect_target_type("http://example.com/page") == TargetType.URL


def test_detects_github_repo_url():
    assert detect_target_type("https://github.com/psf/requests") == TargetType.GITHUB


def test_detects_github_repo_url_with_tree():
    assert detect_target_type("https://github.com/psf/requests/tree/main") == TargetType.GITHUB


def test_detects_zip_archive_by_extension(tmp_path):
    z = tmp_path / "project.zip"
    z.write_bytes(b"PK\x03\x04")
    assert detect_target_type(str(z)) == TargetType.ARCHIVE


def test_detects_local_directory(tmp_path):
    assert detect_target_type(str(tmp_path)) == TargetType.LOCAL_DIR


def test_detects_local_directory_relative_path():
    assert detect_target_type("./my-project") == TargetType.LOCAL_DIR


def test_parses_github_owner_repo():
    parsed = parse_github_url("https://github.com/psf/requests")
    assert parsed.owner == "psf"
    assert parsed.repo == "requests"
    assert parsed.ref is None


def test_parses_github_url_with_ref():
    parsed = parse_github_url("https://github.com/psf/requests/tree/v2.0")
    assert parsed.owner == "psf"
    assert parsed.repo == "requests"
    assert parsed.ref == "v2.0"


def test_parses_github_url_with_git_suffix():
    parsed = parse_github_url("https://github.com/psf/requests.git")
    assert parsed.owner == "psf"
    assert parsed.repo == "requests"
