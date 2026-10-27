"""Encrypt adapter credentials at rest with Fernet."""

from __future__ import annotations

import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class CredentialsError(RuntimeError):
    pass


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().credentials_key.encode()
    try:
        return Fernet(key)
    except Exception as exc:  # noqa: BLE001
        raise CredentialsError(
            "CREDENTIALS_KEY is not a valid Fernet key. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"`."
        ) from exc


def encrypt_json(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    return _fernet().encrypt(raw).decode()


def decrypt_json(token: str) -> dict:
    try:
        raw = _fernet().decrypt(token.encode())
    except InvalidToken as exc:
        raise CredentialsError("Could not decrypt adapter config. CREDENTIALS_KEY may have changed.") from exc
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise CredentialsError("Decrypted adapter config is not an object.")
    return data
