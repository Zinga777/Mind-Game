"""Strategy Cards (spec 14.3): versioned, exchange-tagged, secret-free JSON with a
tamper check. The engine refuses a card whose code/config hashes do not match."""
from __future__ import annotations

import hashlib
import html
import inspect
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .. import __version__, strategies
from ..config.schema import Config
from ..db import now_ms

CORE_MODULES = ["thunder.backtest.runner", "thunder.trade.builder", "thunder.trade.sizing", "thunder.trade.costs",
                "thunder.risk.guard", "thunder.desk.protocol", "thunder.execution.fills"]


class StrategyCard(BaseModel):
    card_id: str
    name: str
    strategy_id: str
    version: str
    status: str
    exchange: str = "coindcx"
    instruments: list[str]
    timeframe: str = "5m"
    regimes_allowed: list[str]
    rule_text: str
    parameters: dict
    rules: dict
    risk: dict
    cost_assumptions: dict
    validated_capital_range: Optional[list[float]] = None
    council_mode: str = "rules_only"
    evidence: dict
    checklist_plain: list[str]
    known_weaknesses: list[str] = Field(default_factory=list)
    code_hash: str
    config_hash: str
    created_at: int
    sample_data: bool = False


def code_hash(strategy_id: str) -> str:
    import importlib
    h = hashlib.sha256()
    h.update(inspect.getsource(strategies.REGISTRY[strategy_id]).encode())
    for m in CORE_MODULES:
        h.update(inspect.getsource(importlib.import_module(m)).encode())
    return h.hexdigest()[:20]


def card_config(cfg: Config) -> dict:
    return {"risk": cfg.risk.model_dump(), "costs": cfg.costs.model_dump(), "threshold": cfg.council.threshold}


def cfg_hash(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:20]


def build_card(strategy_id: str, summary: dict, cfg: Config, sample_data: bool) -> StrategyCard:
    cls = strategies.REGISTRY[strategy_id]
    s = cls(**summary.get("params", {}))
    cc = card_config(cfg)
    weaknesses = []
    for reg, v in (summary.get("regime_breakdown") or {}).items():
        if v["n"] >= 10 and v["mean_r"] < 0:
            weaknesses.append(f"Lost money in {reg} ({v['mean_r']:+.2f}R over {v['n']} trades).")
    if sample_data:
        weaknesses.insert(0, "Evidence comes from SAMPLE (synthetic) data — not valid for real money.")
    return StrategyCard(
        card_id=uuid.uuid4().hex[:12], name=cls.name, strategy_id=strategy_id, version=__version__,
        status=summary.get("status", "RESEARCH"), instruments=cfg.exchange.instruments,
        regimes_allowed=list(cls.regimes_allowed), rule_text=cls.description_plain, parameters=s.params,
        rules={"entry": cls.entry_method, "stop": "structural level + buffer, never tighter than "
               f"{cls.min_stop_atr_h1} x 1h ATR", "target": "declared R multiple / structural level",
               "time_stop_bars": s.params.get("time_stop_bars"), "min_rr_net": max(cls.min_net_reward_after_costs, cfg.risk.min_rr_net)},
        risk={"risk_pct": cfg.risk.risk_pct, "recovery_policy": cfg.risk.recovery_policy,
              "daily_stop": cfg.risk.daily_loss_stop_pct, "max_dd": cfg.risk.max_drawdown_pct,
              "max_leverage": cfg.risk.max_leverage_used},
        cost_assumptions=cfg.costs.model_dump(), validated_capital_range=summary.get("validated_capital_range"),
        council_mode=cfg.council.mode,
        evidence={k: summary.get(k) for k in ("oos_trades", "expectancy_r", "ci", "profit_factor", "max_dd",
                                              "trial_count", "walk_forward", "evidence", "gates")},
        checklist_plain=s.checklist_plain(), known_weaknesses=weaknesses, code_hash=code_hash(strategy_id),
        config_hash=cfg_hash(cc), created_at=now_ms(), sample_data=sample_data)


def verify(card: StrategyCard, cfg: Config) -> tuple[bool, str]:
    if card.exchange != "coindcx":
        return False, "card was validated on another exchange — re-validate before use"
    if card.strategy_id not in strategies.REGISTRY:
        return False, "unknown strategy"
    if code_hash(card.strategy_id) != card.code_hash:
        return False, "strategy or core code changed since this card was validated (tamper check failed)"
    if cfg_hash(card_config(cfg)) != card.config_hash:
        return False, "risk/cost settings differ from those the card was validated with"
    return True, "hashes verified"


def save(con: sqlite3.Connection, card: StrategyCard) -> None:
    con.execute("INSERT OR REPLACE INTO strategy_cards(card_id,strategy_id,version,status,card_json,created_at) VALUES(?,?,?,?,?,?)",
                (card.card_id, card.strategy_id, card.version, card.status, card.model_dump_json(), card.created_at))


def load_all(con: sqlite3.Connection) -> list[StrategyCard]:
    return [StrategyCard.model_validate_json(r[0]) for r in
            con.execute("SELECT card_json FROM strategy_cards ORDER BY created_at DESC").fetchall()]


def export_json(card: StrategyCard) -> str:
    return card.model_dump_json(indent=2)


def import_json(text: str) -> StrategyCard:
    d = json.loads(text)
    for k in list(d):
        if any(w in k.lower() for w in ("secret", "api_key", "token", "password")):
            d.pop(k)
    return StrategyCard.model_validate(d)


def printable_html(card: StrategyCard) -> str:
    e = html.escape
    items = "".join(f"<li>{e(x)}</li>" for x in card.checklist_plain)
    weak = "".join(f"<li>{e(x)}</li>" for x in card.known_weaknesses) or "<li>None recorded</li>"
    ev = card.evidence
    banner = "<p style='background:#eee;padding:8px'><b>SAMPLE DATA</b> — not real evidence</p>" if card.sample_data else ""
    return (f"<!doctype html><meta charset='utf-8'><title>{e(card.name)} card</title>"
            "<style>body{font-family:system-ui;max-width:720px;margin:2rem auto;padding:0 16px}</style>"
            f"{banner}<h1>{e(card.strategy_id)} {e(card.name)}</h1><p>Status: <b>{e(card.status)}</b> · "
            f"exchange {e(card.exchange)} · {', '.join(map(e, card.instruments))} · {e(card.timeframe)}</p>"
            f"<p>{e(card.rule_text)}</p><h2>What to look for</h2><ul>{items}</ul>"
            f"<h2>Evidence (out-of-sample)</h2><p>{ev.get('oos_trades')} trades, "
            f"{(ev.get('expectancy_r') or 0):+.3f}R per trade after costs; parameter sets tried: {ev.get('trial_count')}</p>"
            f"<h2>Known weaknesses</h2><ul>{weak}</ul><p><small>code {e(card.code_hash)} · config {e(card.config_hash)}</small></p>"
            "<p><small>Backtest and paper results do not guarantee future profit.</small></p>")


def export_dir(card: StrategyCard, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{card.strategy_id}-{card.card_id}.json"
    p.write_text(export_json(card), encoding="utf-8")
    return p
