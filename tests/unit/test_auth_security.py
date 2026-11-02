import pytest
from app.modules.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    password = "MySecurePassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_verify_password_invalid_hash_does_not_crash():
    assert verify_password("any_password", "not_a_valid_hash") is False
    assert verify_password("any_password", "") is False


def test_create_and_decode_access_token():
    user_id = 42
    email = "journalist@example.com"
    role = "journalist"

    token = create_access_token(user_id=user_id, email=email, role=role)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert payload["role"] == role
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload
