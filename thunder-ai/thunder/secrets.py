"""Secret storage and scrubbing (H12, spec Section 18).

Secrets live in the OS keyring when available, otherwise in data/secrets.json
with owner-only permissions. They are never written to logs, the DB, errors or
exports: every string that leaves the process through our logging/event paths
passes through `scrub()`.
"""
from __future__ import annotations

import json
import logging
import os
import re
import stat
from pathlib import Path
from typing import Optional

from .config.loader import data_dir

SERVICE = "thunder-ai"
_KNOWN: set[str] = set()
_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(api[_-]?secret|api[_-]?key|x-auth-signature|x-auth-apikey|token|password)(\"?\s*[:=]\s*\"?)([^\s\",}]+)"),
]


def register_secret(value: Optional[str]) -> None:
    if value and len(value) >= 6:
        _KNOWN.add(value)


def scrub(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    for s in sorted(_KNOWN, key=len, reverse=True):
        text = text.replace(s, "***")
    text = _PATTERNS[0].sub("***", text)
    text = _PATTERNS[1].sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    return text


class ScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = scrub(record.getMessage())
        record.args = ()
        return True


def _file() -> Path:
    return data_dir() / "secrets.json"


def _keyring():
    if os.environ.get("THUNDER_NO_KEYRING"):
        return None
    try:
        import keyring
        from keyring.backends import fail
        kr = keyring.get_keyring()
        if isinstance(kr, fail.Keyring):
            return None
        return keyring
    except Exception:
        return None


def set_secret(name: str, value: str) -> None:
    register_secret(value)
    kr = _keyring()
    if kr is not None:
        try:
            kr.set_password(SERVICE, name, value)
            return
        except Exception:
            pass
    f = _file()
    data = json.loads(f.read_text()) if f.exists() else {}
    data[name] = value
    f.write_text(json.dumps(data))
    try:
        os.chmod(f, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def get_secret(name: str) -> Optional[str]:
    env = os.environ.get(f"THUNDER_{name.upper()}")
    if env:
        register_secret(env)
        return env
    kr = _keyring()
    if kr is not None:
        try:
            v = kr.get_password(SERVICE, name)
            if v:
                register_secret(v)
                return v
        except Exception:
            pass
    f = _file()
    if f.exists():
        v = json.loads(f.read_text()).get(name)
        register_secret(v)
        return v
    return None


def delete_secret(name: str) -> None:
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(SERVICE, name)
        except Exception:
            pass
    f = _file()
    if f.exists():
        data = json.loads(f.read_text())
        data.pop(name, None)
        f.write_text(json.dumps(data))


def mask(value: Optional[str]) -> str:
    if not value:
        return "(not set)"
    return value[:3] + "•" * 6 + value[-2:]
