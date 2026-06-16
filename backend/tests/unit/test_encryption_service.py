from app.services.encryption_service import decrypt_value, encrypt_value


def test_encrypt_decrypt_roundtrip():
    original = "notion-secret-token-12345"
    encrypted = encrypt_value(original)
    assert encrypted != original
    assert decrypt_value(encrypted) == original
