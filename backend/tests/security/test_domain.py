from app.utils.domain import is_domain_allowed


def test_exact_domain_match():
    assert is_domain_allowed("https://app.example.com", ["example.com"])


def test_wildcard_subdomain():
    assert is_domain_allowed("https://app.example.com", ["*.example.com"])


def test_suffix_bypass_blocked():
    assert not is_domain_allowed("https://evil-example.com", ["example.com"])


def test_empty_allowlist_permits():
    assert is_domain_allowed("https://anywhere.com", [])
