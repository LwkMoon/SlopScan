from __future__ import annotations

import pytest

from slopscan.utils.security import UnsafeURLError, validate_url


def test_rejects_localhost():
    with pytest.raises(UnsafeURLError):
        validate_url("http://localhost:8000/")


def test_rejects_loopback_ip():
    with pytest.raises(UnsafeURLError):
        validate_url("http://127.0.0.1/")


def test_rejects_private_ip_class_a():
    with pytest.raises(UnsafeURLError):
        validate_url("http://10.0.0.5/")


def test_rejects_private_ip_class_b():
    with pytest.raises(UnsafeURLError):
        validate_url("http://172.16.0.5/")


def test_rejects_private_ip_class_c():
    with pytest.raises(UnsafeURLError):
        validate_url("http://192.168.1.1/")


def test_rejects_link_local_and_cloud_metadata():
    with pytest.raises(UnsafeURLError):
        validate_url("http://169.254.169.254/latest/meta-data/")


def test_rejects_dot_local_hostnames():
    with pytest.raises(UnsafeURLError):
        validate_url("http://myserver.local/")


def test_rejects_non_http_schemes():
    with pytest.raises(UnsafeURLError):
        validate_url("file:///etc/passwd")
    with pytest.raises(UnsafeURLError):
        validate_url("ftp://example.com/file")
    with pytest.raises(UnsafeURLError):
        validate_url("gopher://example.com/")


def test_rejects_url_with_no_hostname():
    with pytest.raises(UnsafeURLError):
        validate_url("http:///path-only")


def test_rejects_unresolvable_host():
    with pytest.raises(UnsafeURLError):
        validate_url("http://this-domain-should-not-exist-slopscan-test.invalid/")


def test_allows_public_looking_ip_literal():
    # 8.8.8.8 is a real public IP (Google DNS) -- should pass IP-range checks.
    # We don't assert it resolves further; this only tests the blocklist logic.
    result = validate_url("http://8.8.8.8/")
    assert result.ip_addresses == ["8.8.8.8"]
