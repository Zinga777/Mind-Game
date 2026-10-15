"""Load / save config.yaml and locate the data folder."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import yaml

from .schema import Config

ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    d = Path(os.environ.get("THUNDER_DATA_DIR", ROOT / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return Path(os.environ.get("THUNDER_CONFIG", ROOT / "config.yaml"))


def load_config(path: Path | None = None) -> Config:
    p = path or config_path()
    if p.exists():
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return Config.model_validate(raw)
    return Config()


def save_config(cfg: Config, path: Path | None = None) -> None:
    p = path or config_path()
    p.write_text(yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False), encoding="utf-8")


def config_hash(cfg: Config | dict) -> str:
    d = cfg.model_dump(mode="json") if isinstance(cfg, Config) else cfg
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]
