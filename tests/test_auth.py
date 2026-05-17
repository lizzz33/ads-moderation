"""Тесты для auth: verify_password, hash_password, AuthService"""

from datetime import timedelta, datetime, timezone

import jwt
import pytest
from fastapi import HTTPException

from app.clients.settings import ALGORITHM, SECRET_KEY
from app.services.auth import AuthService, auth_service, hash_password, verify_password


# ── verify_password / hash_password ───────────────────────────────


@pytest.mark.unit
def test_verify_password_correct():
    hashed = hash_password("my_secret")
    assert verify_password("my_secret", hashed) is True


@pytest.mark.unit
def test_verify_password_incorrect():
    hashed = hash_password("my_secret")
    assert verify_password("wrong_password", hashed) is False


@pytest.mark.unit
def test_hash_password_different_hashes():
    h1 = hash_password("same_password")
    h2 = hash_password("same_password")
    assert h1 != h2  # bcrypt генерирует разный salt


@pytest.mark.unit
def test_hash_password_stored_hash_verifies():
    hashed = hash_password("test123")
    assert verify_password("test123", hashed) is True
    assert verify_password("other", hashed) is False


# ── AuthService.create_access_token ───────────────────────────────


@pytest.mark.unit
def test_create_access_token_default_expiry():
    token = auth_service.create_access_token(data={"sub": "1", "login": "test@test.com"})
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == "1"
    assert payload["login"] == "test@test.com"
    assert "exp" in payload


@pytest.mark.unit
def test_create_access_token_custom_expiry():
    delta = timedelta(minutes=5)
    token = auth_service.create_access_token(
        data={"sub": "1", "login": "t@t.com"}, expires_delta=delta
    )
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert "exp" in payload
    expected_exp = datetime.now(timezone.utc) + delta
    actual_exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert abs((actual_exp - expected_exp).total_seconds()) < 5


# ── AuthService.decode_token ──────────────────────────────────────


@pytest.mark.unit
def test_decode_token_valid():
    token = auth_service.create_access_token(data={"sub": "42", "login": "a@b.com"})
    token_data = auth_service.decode_token(token)

    assert token_data.user_id == 42
    assert token_data.login == "a@b.com"


@pytest.mark.unit
def test_decode_token_expired():
    token = auth_service.create_access_token(
        data={"sub": "1", "login": "a@b.com"}, expires_delta=timedelta(seconds=-1)
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_service.decode_token(token)

    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


@pytest.mark.unit
def test_decode_token_no_sub():
    token = jwt.encode({"login": "a@b.com", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, SECRET_KEY, algorithm=ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        auth_service.decode_token(token)

    assert exc_info.value.status_code == 401


@pytest.mark.unit
def test_decode_token_invalid_signature():
    token = jwt.encode({"sub": "1", "login": "x"}, "wrong_secret", algorithm=ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        auth_service.decode_token(token)

    assert exc_info.value.status_code == 401


@pytest.mark.unit
def test_decode_token_alg_none_attack():
    header = {"alg": "none", "typ": "JWT"}
    import json, base64

    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps({"sub": "1"}).encode()).rstrip(b"=").decode()
    token = f"{h}.{p}."

    with pytest.raises(HTTPException) as exc_info:
        auth_service.decode_token(token)

    assert exc_info.value.status_code == 401


@pytest.mark.unit
def test_decode_token_malformed():
    with pytest.raises(HTTPException) as exc_info:
        auth_service.decode_token("not.a.valid.token")

    assert exc_info.value.status_code == 401
