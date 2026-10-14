"""Optional LLM council ("rules_plus_llm", spec 9.6).

- Called only for candidates that already passed the rules desk (cost control).
- Strict JSON via pydantic; invalid output or a refusal => "no opinion", never approval.
- Deterministic cache keyed on the evidence-packet hash => reproducible, cheap backtests.
- H10: the verdict can only approve, veto or REDUCE size (factor clamped to [0, 1]).
  It cannot change entry/stop/target and cannot touch live mode.
- No secrets and no personal data are ever put in the packet.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from ..db import now_ms

log = logging.getLogger("thunder.council")

# USD per million tokens (input, output) — keep in sync with Anthropic pricing.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}

SYSTEM = (
    "You review one proposed crypto-futures trade. You receive a JSON evidence packet produced by deterministic "
    "analysts. You may approve it, veto it, or reduce its size. You can never increase size, move the stop or "
    "target, or bypass any rule. Veto if the evidence is contradictory or the counter-analyst's warning is "
    "serious. Be brief. Reply only in the requested JSON format."
)


class LLMVerdict(BaseModel):
    verdict: Literal["approve", "veto", "reduce_size"]
    size_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    adjusted_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    key_risk: str = Field(default="", max_length=400)


@dataclass
class CouncilOutcome:
    verdict: str              # approve | veto | reduce_size | no_opinion
    size_factor: float        # always <= 1.0
    key_risk: str = ""
    cached: bool = False
    cost_usd: float = 0.0


def packet_hash(packet: dict) -> str:
    return hashlib.sha256(json.dumps(packet, sort_keys=True, default=str).encode()).hexdigest()


def enforce_h10(v: LLMVerdict | None) -> CouncilOutcome:
    """Clamp whatever the model said into the allowed space (H10)."""
    if v is None:
        return CouncilOutcome("no_opinion", 1.0)
    if v.verdict == "veto":
        return CouncilOutcome("veto", 0.0, v.key_risk)
    factor = min(1.0, max(0.0, v.size_factor)) if v.verdict == "reduce_size" else 1.0
    return CouncilOutcome(v.verdict, factor, v.key_risk)


class Council:
    def __init__(self, con: sqlite3.Connection, model: str, max_calls_per_day: int, max_cost_usd_per_day: float,
                 api_key: Optional[str] = None, client=None):
        self.con, self.model = con, model
        self.max_calls, self.max_cost = max_calls_per_day, max_cost_usd_per_day
        self._client = client
        self._key = api_key

    def _today(self) -> tuple[int, float]:
        start = now_ms() - now_ms() % 86_400_000
        r = self.con.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM llm_calls WHERE ts>=? AND cache_hit=0",
                             (start,)).fetchone()
        return int(r[0]), float(r[1])

    def _cached(self, h: str) -> Optional[dict]:
        r = self.con.execute("SELECT response_json FROM llm_calls WHERE packet_hash=? AND model=? AND response_json IS NOT NULL "
                             "ORDER BY id DESC LIMIT 1", (h, self.model)).fetchone()
        return json.loads(r[0]) if r else None

    def client(self):
        if self._client is None:
            if not self._key:
                return None
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._key, timeout=30.0, max_retries=2)
        return self._client

    def review(self, packet: dict) -> CouncilOutcome:
        h = packet_hash(packet)
        hit = self._cached(h)
        if hit is not None:
            self.con.execute("INSERT INTO llm_calls(ts,packet_hash,model,input_tokens,output_tokens,cost_usd,cache_hit,response_json) "
                             "VALUES(?,?,?,?,?,?,?,?)", (now_ms(), h, self.model, 0, 0, 0.0, 1, json.dumps(hit)))
            try:
                out = enforce_h10(LLMVerdict.model_validate(hit))
            except ValidationError:
                out = CouncilOutcome("no_opinion", 1.0)
            out.cached = True
            return out
        calls, cost = self._today()
        if calls >= self.max_calls or cost >= self.max_cost:
            return CouncilOutcome("no_opinion", 1.0, "daily LLM budget reached")
        cl = self.client()
        if cl is None:
            return CouncilOutcome("no_opinion", 1.0, "no API key")
        verdict: Optional[LLMVerdict] = None
        in_tok = out_tok = 0
        try:
            resp = cl.messages.parse(
                model=self.model, max_tokens=2000, system=SYSTEM,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": json.dumps(packet, sort_keys=True, default=str)}],
                output_format=LLMVerdict,
            )
            in_tok, out_tok = resp.usage.input_tokens, resp.usage.output_tokens
            if resp.stop_reason != "refusal":
                verdict = resp.parsed_output
        except Exception as e:  # network, validation, refusal -> no opinion (never approval)
            log.warning("LLM council unavailable: %s", type(e).__name__)
        pin, pout = PRICES.get(self.model, (4.0, 20.0))
        c = in_tok / 1e6 * pin + out_tok / 1e6 * pout
        self.con.execute("INSERT INTO llm_calls(ts,packet_hash,model,input_tokens,output_tokens,cost_usd,cache_hit,response_json) "
                         "VALUES(?,?,?,?,?,?,?,?)", (now_ms(), h, self.model, in_tok, out_tok, c, 0,
                                                     verdict.model_dump_json() if verdict else None))
        out = enforce_h10(verdict)
        out.cost_usd = c
        return out


def estimate_monthly_cost_usd(calls_per_day: int, model: str, in_tok: int = 3000, out_tok: int = 400) -> float:
    pin, pout = PRICES.get(model, (4.0, 20.0))
    return calls_per_day * 30 * (in_tok / 1e6 * pin + out_tok / 1e6 * pout)
