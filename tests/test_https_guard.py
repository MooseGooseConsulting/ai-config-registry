import pytest

from registry_scanner import _assert_https_url


def test_assert_https_url_accepts_https():
    _assert_https_url("https://example.supabase.co/rest/v1/skills")


def test_assert_https_url_rejects_http():
    with pytest.raises(ValueError, match="non-HTTPS"):
        _assert_https_url("http://evil.example/rest/v1/skills")
