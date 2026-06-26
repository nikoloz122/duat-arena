"""Local JSON persistence for user-registered BYOA remote agents."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.byoa_crypto import decrypt_secret, encrypt_secret
from agents.byoa_http import AUTH_NONE, AUTH_TYPES

_STORE_FILENAME = "byoa_agents.json"
_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class BYOAgentRecord:
    id: str
    name: str
    description: str
    endpoint: str
    auth_type: str = AUTH_NONE
    secret_encrypted: str = ""
    timeout: float = 5.0
    enabled: bool = True
    connection_status: str = "offline"
    last_latency_ms: Optional[float] = None
    last_tested_at: Optional[str] = None
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def to_public_dict(self, *, include_secret: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "endpoint": self.endpoint,
            "auth_type": self.auth_type,
            "timeout": self.timeout,
            "enabled": self.enabled,
            "kind": "remote",
            "connection_status": self.connection_status,
            "last_latency_ms": self.last_latency_ms,
            "last_tested_at": self.last_tested_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "has_secret": bool(self.secret_encrypted),
        }
        if include_secret and self.secret_encrypted:
            payload["secret"] = decrypt_secret(self.secret_encrypted)
        return payload

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "BYOAgentRecord":
        auth_type = raw.get("auth_type", AUTH_NONE)
        if auth_type not in AUTH_TYPES:
            auth_type = AUTH_NONE
        return cls(
            id=str(raw["id"]),
            name=str(raw.get("name", "")),
            description=str(raw.get("description", "")),
            endpoint=str(raw.get("endpoint", "")),
            auth_type=auth_type,
            secret_encrypted=str(raw.get("secret_encrypted", "")),
            timeout=float(raw.get("timeout", 5.0)),
            enabled=bool(raw.get("enabled", True)),
            connection_status=str(raw.get("connection_status", "offline")),
            last_latency_ms=raw.get("last_latency_ms"),
            last_tested_at=raw.get("last_tested_at"),
            created_at=str(raw.get("created_at", _utc_now())),
            updated_at=str(raw.get("updated_at", _utc_now())),
        )


class BYOAgentStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._records: Dict[str, BYOAgentRecord] = {}

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> None:
        with _lock:
            if not self._path.is_file():
                self._records = {}
                return
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            agents = raw.get("agents", []) if isinstance(raw, dict) else raw
            self._records = {
                item["id"]: BYOAgentRecord.from_dict(item)
                for item in agents
                if isinstance(item, dict) and item.get("id")
            }

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"agents": [asdict(record) for record in self._records.values()]}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list(self) -> List[BYOAgentRecord]:
        return list(self._records.values())

    def get(self, agent_id: str) -> Optional[BYOAgentRecord]:
        return self._records.get(agent_id)

    def upsert(self, record: BYOAgentRecord) -> BYOAgentRecord:
        with _lock:
            record.updated_at = _utc_now()
            self._records[record.id] = record
            self.save()
            return record

    def delete(self, agent_id: str) -> bool:
        with _lock:
            if agent_id not in self._records:
                return False
            del self._records[agent_id]
            self.save()
            return True

    def set_secret(self, agent_id: str, secret: Optional[str]) -> None:
        with _lock:
            record = self._records[agent_id]
            record.secret_encrypted = encrypt_secret(secret or "")
            record.updated_at = _utc_now()
            self.save()

    def decrypted_secret(self, agent_id: str) -> str:
        record = self._records.get(agent_id)
        if record is None or not record.secret_encrypted:
            return ""
        return decrypt_secret(record.secret_encrypted)


def default_store_path(log_dir: str = "logs") -> Path:
    return Path(log_dir) / _STORE_FILENAME


_default_store: Optional[BYOAgentStore] = None


def get_byoa_store(log_dir: str = "logs") -> BYOAgentStore:
    global _default_store
    if _default_store is None:
        _default_store = BYOAgentStore(default_store_path(log_dir))
        _default_store.load()
    return _default_store
