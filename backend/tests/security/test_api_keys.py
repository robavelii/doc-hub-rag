import time

import bcrypt

from app.services.auth_service import (
    API_KEY_KIND_PUBLISHABLE,
    api_key_needs_rehash,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)


def test_key_prefixes_identify_kind():
    assert generate_api_key().startswith("sk_")
    assert generate_api_key(API_KEY_KIND_PUBLISHABLE).startswith("pk_")
    assert len(generate_api_key()) == 3 + 64


def test_sha256_hash_verifies_and_rejects_wrong_key():
    key = generate_api_key()
    hashed = hash_api_key(key)
    assert verify_api_key(key, hashed)
    assert not verify_api_key(key + "x", hashed)
    assert not api_key_needs_rehash(hashed)


def test_legacy_bcrypt_hashes_still_verify_and_are_flagged_for_rehash():
    legacy_key = "a" * 64
    legacy_hash = bcrypt.hashpw(legacy_key.encode(), bcrypt.gensalt(rounds=4)).decode()
    assert verify_api_key(legacy_key, legacy_hash)
    assert not verify_api_key("b" * 64, legacy_hash)
    assert api_key_needs_rehash(legacy_hash)


def test_verification_is_fast_enough_for_every_request():
    key = generate_api_key()
    hashed = hash_api_key(key)
    start = time.perf_counter()
    for _ in range(1000):
        verify_api_key(key, hashed)
    assert time.perf_counter() - start < 0.5  # bcrypt would take minutes
