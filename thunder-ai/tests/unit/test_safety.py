"""Hard rules H1-H14 that are not covered elsewhere: Martingale, LLM limits, secrets, live lock, card tamper."""
import json
import logging

import pytest
from pydantic import ValidationError

from thunder import cards, strategies
from thunder.config.schema import Config, RiskCfg
from thunder.db import kv_set, log_event
from thunder.desk.council_llm import Council, CouncilOutcome, LLMVerdict, enforce_h10
from thunder.exchanges.coindcx import CoinDCXPrivate
from thunder.exchanges.coindcx.auth import sign, signed_request
from thunder.exchanges.coindcx.http import Http
from thunder.exchanges.groww_stub import GrowwAdapter
from thunder.exchanges.mock_server import MockCoinDCX
from thunder.execution import live
from thunder.risk.recovery import policy_multiplier
from thunder.risk.killswitch import AccountState
from thunder.secrets import ScrubFilter, register_secret, scrub


# ---- H2 Martingale --------------------------------------------------------------------
def test_martingale_not_selectable_anywhere():
    with pytest.raises(ValidationError):
        RiskCfg(recovery_policy="D")
    with pytest.raises(ValueError):
        strategies.get("MARTINGALE")
    with pytest.raises(ValueError):
        policy_multiplier("D", AccountState(starting_equity=1000))


def test_policy_b_caps_and_c_derisks():
    a = AccountState(starting_equity=1000)
    a.recent_r = [0.5] * 20
    a.consecutive_losses, a.loss_streak_regime = 2, "RANGE"
    d = policy_multiplier("B", a, regime="RANGE", score=80, threshold=70)
    assert d.multiplier == pytest.approx(1.5)
    a.consecutive_losses = 3
    assert policy_multiplier("B", a, regime="RANGE", score=80).multiplier <= 1.5
    assert policy_multiplier("B", a, regime="TREND_UP", score=80).multiplier == 1.0  # regime changed
    a.consecutive_losses = 4
    assert policy_multiplier("B", a, regime="RANGE", score=80).cooldown_ms > 0
    a.consecutive_losses = 3
    assert policy_multiplier("C", a, score=75, threshold=70).multiplier == 0.5
    assert policy_multiplier("B", a, regime="RANGE", score=80, live_initial_stage=True).multiplier == 1.0


# ---- H10 LLM ------------------------------------------------------------------------------
def test_llm_cannot_increase_size():
    assert enforce_h10(LLMVerdict(verdict="approve", size_factor=1.0)).size_factor == 1.0
    assert enforce_h10(LLMVerdict(verdict="reduce_size", size_factor=0.4)).size_factor == 0.4
    assert enforce_h10(LLMVerdict(verdict="veto")).size_factor == 0.0
    assert enforce_h10(None).verdict == "no_opinion"
    with pytest.raises(ValidationError):
        LLMVerdict(verdict="approve", size_factor=2.0)
    with pytest.raises(ValidationError):
        LLMVerdict(verdict="increase_size")


def test_llm_without_key_is_no_opinion_and_rules_only_works(con):
    c = Council(con, "claude-opus-5-5", 10, 1.0, api_key=None)
    out = c.review({"x": 1})
    assert out.verdict == "no_opinion" and out.size_factor == 1.0


def test_llm_bad_output_is_never_approval_and_cached(con):
    class Boom:
        class messages:
            @staticmethod
            def parse(**kw):
                raise ValueError("invalid json")
    c = Council(con, "claude-opus-5-5", 10, 1.0, client=Boom())
    assert c.review({"a": 1}).verdict == "no_opinion"

    class Good:
        calls = 0

        class messages:
            @staticmethod
            def parse(**kw):
                Good.calls += 1

                class U:
                    input_tokens, output_tokens = 1000, 100

                class R:
                    usage, stop_reason = U, "end_turn"
                    parsed_output = LLMVerdict(verdict="reduce_size", size_factor=0.5, key_risk="thin volume")
                return R
    c2 = Council(con, "claude-opus-5-5", 10, 1.0, client=Good())
    o1, o2 = c2.review({"p": 2}), c2.review({"p": 2})
    assert o1.size_factor == 0.5 and o2.cached and Good.calls == 1  # deterministic cache by packet hash


def test_llm_budget_cap(con):
    c = Council(con, "claude-opus-5-5", 0, 1.0, client=object())
    assert c.review({"z": 1}).key_risk == "daily LLM budget reached"


def test_guard_llm_veto_rejects():
    from thunder.risk import guard as G
    from thunder.trade.sizing import SizeResult
    from tests.conftest import unit_spec
    ok_size = SizeResult(True, 1, 1, 10, 9, 100, 20, 5)
    base = dict(halted=False, data_fresh=True, daily_stop_hit=False, open_positions=0, max_open_positions=1, size=ok_size,
                entry=100, stop=99, leverage_for_liq=5, spec=unit_spec(), cost_r=0.1, rr_net=2, max_cost_r=0.3, min_rr_net=1.2)
    assert G.check(G.GuardInput(**base)).ok
    r = G.check(G.GuardInput(**base, llm_verdict="veto"))
    assert not r.ok and r.reason == "LLM council vetoed"


def test_guard_does_not_import_strategy_code():
    import inspect
    from thunder.risk import guard
    src = inspect.getsource(guard)
    assert "strategies" not in src


# ---- H12 secrets ----------------------------------------------------------------------------
def test_scrubber_removes_secrets(con, caplog):
    secret = "SUPERSECRET-abc123xyz"
    register_secret(secret)
    assert secret not in scrub(f"oops {secret} leaked")
    assert "zzz999" not in scrub('{"api_secret": "zzz999"}')
    assert "sk-ant-abcdefghijk" not in scrub("key sk-ant-abcdefghijk")
    log_event(con, "ERROR", "test", f"failure with {secret}")
    rows = " ".join(r[0] for r in con.execute("SELECT message FROM events"))
    assert secret not in rows
    lg = logging.getLogger("t-scrub")
    lg.addFilter(ScrubFilter())
    with caplog.at_level(logging.INFO, logger="t-scrub"):
        lg.info("header %s", secret)
    assert secret not in caplog.text
    dump = "\n".join(con.iterdump())
    assert secret not in dump


def test_card_contains_no_secrets_and_detects_tamper(con):
    cfg = Config()
    summ = {"status": "RESEARCH", "params": strategies.REGISTRY["S1"].defaults, "oos_trades": 0, "expectancy_r": 0}
    card = cards.build_card("S1", summ, cfg, sample_data=True)
    txt = cards.export_json(card)
    assert "secret" not in txt.lower() and "api_key" not in txt.lower()
    assert cards.verify(card, cfg)[0]
    bad = card.model_copy(update={"code_hash": "0" * 20})
    assert not cards.verify(bad, cfg)[0]
    cfg2 = cfg.model_copy(deep=True)
    cfg2.risk.risk_pct = 0.01
    assert not cards.verify(card, cfg2)[0]
    other = card.model_copy(update={"exchange": "groww"})
    assert not cards.verify(other, cfg)[0]
    d = json.loads(txt)
    d["api_secret"] = "x"
    assert "api_secret" not in cards.import_json(json.dumps(d)).model_dump()


# ---- H1 live lock ---------------------------------------------------------------------------
def _card(cfg, status="PAPER_PROVEN"):
    summ = {"status": status, "params": strategies.REGISTRY["S1"].defaults, "validated_capital_range": [1000, 500000]}
    return cards.build_card("S1", summ, cfg, sample_data=False)


def test_live_disabled_by_default_and_every_gate_required(con):
    cfg = Config()
    card = _card(cfg)
    with pytest.raises(live.LiveLocked):
        live.require_live(con, cfg, card)
    # satisfy gates one by one; live stays locked until ALL pass and it is armed
    con.execute("INSERT INTO trades(mode,strategy_id,exit_time,net_pnl,r_multiple) VALUES('paper','S1',?,1,0.1)",
                (__import__("thunder.db", fromlist=["now_ms"]).now_ms(),))
    kv_set(con, "live_conn_test", {"ok": True})
    kv_set(con, "live_phrase_ok", True)
    assert not live.live_enabled(con, cfg, card)              # smoke test missing
    kv_set(con, "live_smoke_ok", {"ok": True})
    assert not live.live_enabled(con, cfg, card)              # not armed
    kv_set(con, "live_armed", True)
    assert live.live_enabled(con, cfg, card)
    assert not live.live_enabled(con, cfg, _card(cfg, "CONFIRMED_BACKTEST"))  # status gate
    sample = card.model_copy(update={"sample_data": True})
    assert not live.live_enabled(con, cfg, sample)
    kv_set(con, "live_halted", True)
    assert not live.live_enabled(con, cfg, card)


def test_config_alone_cannot_enable_live():
    assert not any("live" in k and "enable" in k for k in Config().model_dump(mode="json").get("risk", {}))
    assert "live_enabled" not in json.dumps(Config().model_dump(mode="json"))


def _live_setup(con, mock):
    cfg = Config()
    card = _card(cfg)
    con.execute("INSERT INTO trades(mode,strategy_id,exit_time,net_pnl,r_multiple) VALUES('paper','S1',?,1,0.1)",
                (__import__("thunder.db", fromlist=["now_ms"]).now_ms(),))
    for k, v in (("live_conn_test", {"ok": True}), ("live_phrase_ok", True), ("live_smoke_ok", {"ok": True}), ("live_armed", True)):
        kv_set(con, k, v)
    priv = CoinDCXPrivate(mock.api_key, mock.api_secret, Http(session=mock, sleep=lambda s: None))
    return cfg, card, priv


def test_live_signing_matches_documented_hmac_and_mock_accepts(con):
    body = {"timestamp": 1700000000000, "order": {"side": "buy"}}
    import hashlib
    import hmac
    exp = hmac.new(b"sec", b'{"timestamp":1700000000000,"order":{"side":"buy"}}', hashlib.sha256).hexdigest()
    assert sign(body, "sec") == exp
    payload, headers = signed_request({"a": 1}, "k", "sec", 5)
    assert payload == '{"a":1,"timestamp":5}' and headers["X-AUTH-APIKEY"] == "k"
    m = MockCoinDCX()
    cfg, card, priv = _live_setup(con, m)
    ex = live.LiveExecutor(con, cfg, card, priv)
    res = ex.open_position("B-BTC_USDT", "long", 0.001, 90, 110, 5)
    assert res["protected"] is True
    bad = CoinDCXPrivate(m.api_key, "wrong-secret", Http(session=m, sleep=lambda s: None))
    with pytest.raises(Exception):
        bad.balances()


def test_protective_order_failure_exits_and_halts(con):
    m = MockCoinDCX(fail_tpsl=True)
    cfg, card, priv = _live_setup(con, m)
    ex = live.LiveExecutor(con, cfg, card, priv)
    res = ex.open_position("B-BTC_USDT", "long", 0.001, 90, 110, 5)
    assert res["protected"] is False and res["status"] == "exited"
    assert not m.positions                                   # market-exited
    assert not live.live_enabled(con, cfg, card)             # halted & disarmed
    assert ("POST", "/exchange/v1/derivatives/futures/positions/exit") in m.calls


def test_exit_all_and_halt_and_never_moves_money(con):
    m = MockCoinDCX()
    cfg, card, priv = _live_setup(con, m)
    ex = live.LiveExecutor(con, cfg, card, priv)
    ex.open_position("B-BTC_USDT", "long", 0.001, 90, 110, 5)
    ex.exit_all_and_halt()
    assert not m.positions and not live.live_enabled(con, cfg, card)
    assert not m.touched_forbidden()
    with pytest.raises(PermissionError):
        priv._post("/exchange/v1/wallets/transfer", {})
    assert not any(hasattr(priv, n) for n in ("withdraw", "transfer", "wallet_transfer"))


def test_live_paths_raise_when_locked(con):
    m = MockCoinDCX()
    cfg = Config()
    card = _card(cfg)
    priv = CoinDCXPrivate(m.api_key, m.api_secret, Http(session=m, sleep=lambda s: None))
    ex = live.LiveExecutor(con, cfg, card, priv)
    with pytest.raises(live.LiveLocked):
        ex.open_position("B-BTC_USDT", "long", 0.001, 90, 110, 5)
    assert not [c for c in m.calls if c[1].endswith("/orders/create")]


def test_smoke_test_against_mock(con):
    m = MockCoinDCX()
    priv = CoinDCXPrivate(m.api_key, m.api_secret, Http(session=m, sleep=lambda s: None))
    res = live.smoke_test(con, priv, "B-BTC_USDT", 10.0, 0.001)
    assert res["ok"], res


def test_reconciler_mismatch_halts(con):
    from thunder.execution.reconciler import check_live
    m = MockCoinDCX()
    priv = CoinDCXPrivate(m.api_key, m.api_secret, Http(session=m, sleep=lambda s: None))
    m.positions["p-X"] = {"id": "p-X", "pair": "B-XRP_USDT", "active_pos": 5, "avg_price": 1}
    probs = check_live(con, priv, set())
    assert probs and "does not know" in probs[0]


def test_groww_is_a_stub():
    with pytest.raises(NotImplementedError):
        GrowwAdapter().candles("X", "5m", 0, 1)


def test_outcome_types():
    assert CouncilOutcome("veto", 0.0).size_factor <= 1.0
