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


def test_live_disabled_by_default_and_every_gate_required(con, monkeypatch):
    cfg = Config()
    card = _card(cfg)
    monkeypatch.setattr(live, "recomputed_status", lambda *a: "PAPER_PROVEN")
    with pytest.raises(live.LiveLocked):
        live.require_live(con, cfg, card)
    # satisfy gates one by one; live stays locked until ALL pass and it is armed
    con.execute("INSERT INTO trades(mode,strategy_id,exit_time,net_pnl,r_multiple,sample_data) VALUES('paper','S1',?,1,0.1,0)",
                (__import__("thunder.db", fromlist=["now_ms"]).now_ms(),))
    kv_set(con, "live_conn_test", {"ok": True})
    kv_set(con, "live_phrase_ok", True)
    assert not live.live_enabled(con, cfg, card)              # smoke test missing
    kv_set(con, "live_smoke_ok", {"ok": True})
    assert not live.live_enabled(con, cfg, card)              # not armed
    kv_set(con, "live_armed", True)
    assert live.live_enabled(con, cfg, card)
    monkeypatch.setattr(live, "recomputed_status", lambda *a: "CONFIRMED_BACKTEST")
    assert not live.live_enabled(con, cfg, card)                               # status gate (recomputed)
    monkeypatch.setattr(live, "recomputed_status", lambda *a: "PAPER_PROVEN")
    sample = card.model_copy(update={"sample_data": True})
    assert not live.live_enabled(con, cfg, sample)
    kv_set(con, "live_halted", True)
    assert not live.live_enabled(con, cfg, card)


def test_config_alone_cannot_enable_live():
    assert not any("live" in k and "enable" in k for k in Config().model_dump(mode="json").get("risk", {}))
    assert "live_enabled" not in json.dumps(Config().model_dump(mode="json"))


@pytest.fixture(autouse=True)
def _proven(monkeypatch, request):
    if "unproven" not in request.keywords:
        monkeypatch.setattr(live, "recomputed_status", lambda *a: "PAPER_PROVEN")


def _live_setup(con, mock):
    cfg = Config()
    card = _card(cfg)
    con.execute("INSERT INTO trades(mode,strategy_id,exit_time,net_pnl,r_multiple,sample_data) VALUES('paper','S1',?,1,0.1,0)",
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
    ex = live.LiveExecutor(con, cfg, card, priv, sleep=lambda s: None)
    res = ex.open_position("B-BTC_USDT", "long", 0.001, 90, 110, 5)
    assert res["protected"] is True
    bad = CoinDCXPrivate(m.api_key, "wrong-secret", Http(session=m, sleep=lambda s: None))
    with pytest.raises(Exception):
        bad.balances()


def test_protective_order_failure_exits_and_halts(con):
    m = MockCoinDCX(fail_tpsl=True)
    cfg, card, priv = _live_setup(con, m)
    ex = live.LiveExecutor(con, cfg, card, priv, sleep=lambda s: None)
    res = ex.open_position("B-BTC_USDT", "long", 0.001, 90, 110, 5)
    assert res["protected"] is False and res["status"] == "exited"
    assert not m.positions                                   # market-exited
    assert not live.live_enabled(con, cfg, card)             # halted & disarmed
    assert ("POST", "/exchange/v1/derivatives/futures/positions/exit") in m.calls


def test_exit_all_and_halt_and_never_moves_money(con):
    m = MockCoinDCX()
    cfg, card, priv = _live_setup(con, m)
    ex = live.LiveExecutor(con, cfg, card, priv, sleep=lambda s: None)
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
    ex = live.LiveExecutor(con, cfg, card, priv, sleep=lambda s: None)
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


@pytest.mark.unproven
def test_imported_card_status_is_not_trusted(con):
    cfg = Config()
    forged = _card(cfg, "PAPER_PROVEN")           # claims PAPER_PROVEN with no evidence behind it
    assert live.recomputed_status(con, cfg, forged) == "RESEARCH"
    g = live.gate_status(con, cfg, forged)[0]
    assert not g.passed and "RESEARCH" in g.plain


def test_relaxed_gates_block_live(con):
    m = MockCoinDCX()
    cfg, card, priv = _live_setup(con, m)
    cfg.gates.min_oos_trades = 10
    assert not live.live_enabled(con, cfg, card)


def test_unfilled_limit_entry_is_cancelled_not_left_unprotected(con):
    m = MockCoinDCX()
    cfg, card, priv = _live_setup(con, m)
    ex = live.LiveExecutor(con, cfg, card, priv, sleep=lambda s: None)
    res = ex.open_position("B-BTC_USDT", "long", 0.001, 90, 110, 5, limit_price=95.0)
    assert res["status"] == "cancelled" and not m.positions
    assert all(o["status"] == "cancelled" for o in m.orders.values())


def test_live_never_adds_to_an_open_position(con):
    m = MockCoinDCX()
    cfg, card, priv = _live_setup(con, m)
    ex = live.LiveExecutor(con, cfg, card, priv, sleep=lambda s: None)
    ex.open_position("B-BTC_USDT", "long", 0.001, 90, 110, 5)
    with pytest.raises(live.LiveLocked):
        ex.open_position("B-BTC_USDT", "long", 0.001, 90, 110, 5)
    assert abs(next(iter(m.positions.values()))["active_pos"] - 0.001) < 1e-12


def test_unreachable_exchange_clock_blocks_orders(con, monkeypatch):
    m = MockCoinDCX(fail_status={"/exchange/v1/time": 500})
    cfg, card, priv = _live_setup(con, m)
    ex = live.LiveExecutor(con, cfg, card, priv, sleep=lambda s: None)
    with pytest.raises(live.LiveLocked):
        ex.open_position("B-BTC_USDT", "long", 0.001, 90, 110, 5)


def test_bridge_sizes_from_real_balance_and_enforces_live_killswitch(con):
    from tests.conftest import unit_spec
    from thunder.engine.live_bridge import LiveBridge
    from thunder.risk.killswitch import AccountState
    from thunder.backtest.runner import StrategyRunner
    m = MockCoinDCX(price=100.0)                     # exchange wallet holds 2500.5 INR
    cfg, card, priv = _live_setup(con, m)
    cfg.capital.starting_paper_equity_inr = 10_000_000.0    # huge PAPER balance must not leak into live size
    shadow = StrategyRunner(strategies.get("S1"), unit_spec(pair="B-BTC_USDT", qty_step=0.001, min_qty=0.001),
                            cfg, AccountState(starting_equity=10_000_000.0))
    kv_set(con, "market_now", {"B-BTC_USDT": {"close": 100.0}})
    b = LiveBridge(con, cfg, card, priv, shadow, sleep=lambda s: None)
    plan = {"pair": "B-BTC_USDT", "side": "long", "stop": 98.0, "target": 106.0, "max_entry": 100.5, "ts": 0}
    ok, why, size = b._plan_ok(plan)
    assert ok, why
    assert size.realised_risk <= 2500.5 * cfg.risk.risk_pct + 1e-9     # sized from the REAL balance
    b._send(plan)
    assert "B-BTC_USDT" in b.expected
    ok2, why2, _ = b._plan_ok(plan)
    assert not ok2 and "already open" in why2
    # a big real loss trips the LIVE kill-switch and flattens
    b.acct.peak = 5000.0
    b.refresh_account()
    assert b.acct.halted and not m.positions and not live.live_enabled(con, cfg, card)


def test_bridge_rejects_stale_price(con):
    from tests.conftest import unit_spec
    from thunder.engine.live_bridge import LiveBridge
    from thunder.risk.killswitch import AccountState
    from thunder.backtest.runner import StrategyRunner
    m = MockCoinDCX(price=100.0)
    cfg, card, priv = _live_setup(con, m)
    shadow = StrategyRunner(strategies.get("S1"), unit_spec(pair="B-BTC_USDT"), cfg, AccountState(starting_equity=1000.0))
    kv_set(con, "market_now", {"B-BTC_USDT": {"close": 103.0}})       # ran past the chase limit
    b = LiveBridge(con, cfg, card, priv, shadow, sleep=lambda s: None)
    ok, why, _ = b._plan_ok({"pair": "B-BTC_USDT", "side": "long", "stop": 98.0, "target": 106.0, "max_entry": 100.5, "ts": 0})
    assert not ok and "chase" in why


def test_engine_exit_all_really_exits(con, monkeypatch):
    from thunder.engine import main as M
    m = MockCoinDCX()
    cfg, card, priv = _live_setup(con, m)
    cards.save(con, card)
    ex = live.LiveExecutor(con, cfg, card, priv, sleep=lambda s: None)
    ex.open_position("B-BTC_USDT", "long", 0.001, 90, 110, 5)
    assert m.positions
    eng = M.Engine.__new__(M.Engine)
    eng.con, eng.cfg, eng.bridge = con, cfg, None
    monkeypatch.setattr(M.Engine, "_live_executor", lambda self: ex)
    eng._exec("EXIT_ALL_HALT", {})
    assert not m.positions and not live.live_enabled(con, cfg, card)
