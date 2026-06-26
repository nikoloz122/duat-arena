"""Encrypt BYOA agent secrets at rest (stdlib-only).

Set ``DUAT_BYOA_KEY`` in every non-local deployment. Without it, dev uses a
key file under the replay log directory — never rely on that in production.
"""

import base64
import hashlib
import os
from pathlib import Path

_KEY_ENV = "DUAT_BYOA_KEY"
_DEV_KEY_FILE = ".byoa_key"


def _is_production() -> bool:
    return os.getenv("ENVIRONMENT", "development").strip().lower() == "production"


def _key_file_path() -> Path:
    log_dir = os.getenv("REPLAY_LOG_DIR", "logs")
    return Path(log_dir) / _DEV_KEY_FILE


def _load_or_create_dev_key() -> bytes:
    if _is_production():
        raise RuntimeError("DUAT_BYOA_KEY is required when ENVIRONMENT=production")
    path = _key_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        return path.read_bytes()
    raw = os.urandom(32)
    path.write_bytes(raw)
    return raw


def _derive_key() -> bytes:
    env_key = os.getenv(_KEY_ENV, "").strip()
    if env_key:
        return hashlib.sha256(env_key.encode("utf-8")).digest()
    return _load_or_create_dev_key()


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    key = _derive_key()
    data = plaintext.encode("utf-8")
    xored = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))
    return base64.urlsafe_b64encode(xored).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    key = _derive_key()
    xored = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    data = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(xored))
    return data.decode("utf-8")
