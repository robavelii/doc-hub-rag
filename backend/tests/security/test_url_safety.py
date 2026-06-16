import pytest

from app.utils.url_safety import UnsafeUrlError, validate_url_for_fetch


def test_blocks_metadata_ip():
    with pytest.raises(UnsafeUrlError):
        validate_url_for_fetch("http://169.254.169.254/latest/meta-data/")


def test_blocks_localhost():
    with pytest.raises(UnsafeUrlError):
        validate_url_for_fetch("http://localhost/admin")


def test_allows_public_https(monkeypatch):
    monkeypatch.setattr(
        "app.utils.url_safety.resolve_hostname",
        lambda _h: ["93.184.216.34"],
    )
    url = validate_url_for_fetch("https://example.com/page")
    assert url.startswith("https://")
