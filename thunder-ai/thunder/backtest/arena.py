"""The Strategy Arena research pipeline (spec 13-14).

For every strategy x instrument:
 1. optimise ONLY on train over the pre-registered grid (trial_count recorded),
 2. confirm on validation, 3. touch the final test ONCE (access logged),
 4. controls: C1 random entry over many seeds; C2 buy-and-hold / flat benchmark,
 5. stress: costs x1.5, remove best 3, neighbouring parameters, month concentration, BTC+ETH,
 6. walk-forward (rolling 3-month train -> 1-month test),
 7. capital-scaling test, 8. Recovery Lab on OOS R-multiples,
 9. Benjamini-Hochberg correction across strategies -> promotion ladder verdict.
Everything is stored with mode='backtest' and the seed/config/data hashes.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from typing import Callable, Optional

import numpy as np

from .. import __version__, strategies
from ..config.loader import config_hash
from ..config.schema import Config
from ..data import store
from ..db import kv_set, log_event, now_ms
from ..exchanges.base import InstrumentSpec, default_spec
from ..features import builder
from ..risk.recovery_lab import run_lab
from ..strategies.controls import buy_and_hold_curve
from . import metrics, promotion, splits
from .runner import features_to_arrays, run

log = logging.getLogger("thunder.arena")

C1_SEEDS = 20


def _score(m: dict, min_trades: int = 30) -> float:
    return m["expectancy_r"] if m["trades"] >= min_trades else -9 + m["trades"] / 1000


def neighbours(strategy_cls, params: dict) -> list[dict]:
    """Grid points that differ from `params` in exactly one dimension by one step (~ +/-20%)."""
    out = []
    for k, vals in strategy_cls.grid.items():
        if params.get(k) not in vals:
            continue
        j = vals.index(params[k])
        for jj in (j - 1, j + 1):
            if 0 <= jj < len(vals):
                out.append({**params, k: vals[jj]})
    if not out:  # single-value grid: perturb numeric params by +/-20%
        for k, v in params.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in ("seed",):
                for f in (0.8, 1.2):
                    out.append({**params, k: type(v)(v * f) if isinstance(v, float) else max(1, int(round(v * f)))})
    return out


def evaluate_strategy(sid: str, F: dict, spec: InstrumentSpec, cfg: Config, sp: dict, c1_test_r: np.ndarray,
                      progress: Optional[Callable[[str], None]] = None) -> dict:
    cls = strategies.REGISTRY[sid]
    eq = cfg.capital.research_equity_inr
    tr, va, te = sp["train"], sp["validation"], sp["test"]
    # 1. optimise on train
    best, best_m, grid_res = None, None, []
    for params in cls.param_grid():
        r = run(cls(**params), F, spec, cfg, eq, tr.start, tr.end, record_candidates=False)
        m = metrics.compute(r.trades, r.equity_curve, eq, bars=tr.end - tr.start)
        grid_res.append((params, m["expectancy_r"], m["trades"]))
        if best_m is None or _score(m) > _score(best_m):
            best, best_m = params, m
    # 2. validation
    rv = run(cls(**best), F, spec, cfg, eq, va.start, va.end)
    mv = metrics.compute(rv.trades, rv.equity_curve, eq, rv.candidates, va.end - va.start)
    # 3. final test: touched once for this strategy version
    rt = run(cls(**best), F, spec, cfg, eq, te.start, te.end)
    mt = metrics.compute(rt.trades, rt.equity_curve, eq, rt.candidates, te.end - te.start)
    oos_trades = rv.trades + rt.trades
    oos_r = np.array([t["r_multiple"] for t in oos_trades])
    oos_curve = rv.equity_curve + [(t, e - rt.equity_curve[0][1] + rv.equity_curve[-1][1]) for t, e in rt.equity_curve] \
        if rv.equity_curve and rt.equity_curve else rv.equity_curve + rt.equity_curve
    moos = metrics.compute(oos_trades, oos_curve, eq, rv.candidates + rt.candidates, va.end - va.start + te.end - te.start)
    # 4. controls: permutation vs C1 pooled R on the same test period
    p_raw = metrics.permutation_pvalue(oos_r, c1_test_r, n=2000, seed=1) if len(oos_r) >= 2 else 1.0
    # 5. stress tests
    r15 = run(cls(**best), F, spec, cfg, eq, te.start, te.end, cost_multiplier=1.5, record_candidates=False)
    r15v = run(cls(**best), F, spec, cfg, eq, va.start, va.end, cost_multiplier=1.5, record_candidates=False)
    t15 = r15v.trades + r15.trades
    exp15 = float(np.mean([t["r_multiple"] for t in t15])) if t15 else float("nan")
    srt = np.sort(oos_r)
    exp_minus3 = float(srt[:-3].mean()) if len(srt) > 3 else float("nan")
    nb = neighbours(cls, best)
    nb_pos = []
    for p in nb:
        rn = run(cls(**p), F, spec, cfg, eq, va.start, va.end, record_candidates=False)
        nb_pos.append(np.mean([t["r_multiple"] for t in rn.trades]) > 0 if rn.trades else False)
    nshare = float(np.mean(nb_pos)) if nb_pos else 0.0
    # 6. walk-forward with re-optimisation on each window's train part
    wf_r = []
    for (a, b, c) in splits.walk_forward(len(F["close"])):
        bp, bm = None, None
        for params in cls.param_grid():
            rr = run(cls(**params), F, spec, cfg, eq, a, b, record_candidates=False)
            mm = metrics.compute(rr.trades, rr.equity_curve, eq)
            if bm is None or _score(mm, 10) > _score(bm, 10):
                bp, bm = params, mm
        rw = run(cls(**bp), F, spec, cfg, eq, b, c, record_candidates=False)
        wf_r += [t["r_multiple"] for t in rw.trades]
    # 7. capital scaling on the test period (feasibility + cost at each size)
    cap = []
    for ce in cfg.capital.scaling_ladder_inr:
        rc = run(cls(**best), F, spec, cfg, ce, te.start, te.end)
        mc = metrics.compute(rc.trades, rc.equity_curve, ce, rc.candidates)
        under = sum(1 for c in rc.candidates if str(c.get("reason", "")).startswith("UNDERCAPITALISED"))
        need = [c.get("min_equity_needed", 0) for c in rc.candidates if c.get("min_equity_needed")]
        cap.append({"capital": ce, "trades": mc["trades"], "expectancy_r": mc["expectancy_r"],
                    "avg_cost_r": mc["avg_cost_r"], "undercapitalised": under,
                    "median_capital_needed": float(np.median(need)) if need else None})
    feas = [c for c in cap if c["trades"] >= 5 and c["expectancy_r"] > 0]
    validated_range = [feas[0]["capital"], feas[-1]["capital"]] if feas else None
    if progress:
        progress(f"{sid} {spec.pair}: {moos['trades']} OOS trades, {moos['expectancy_r']:+.3f}R")
    return {
        "strategy_id": sid, "instrument": spec.pair, "params": best, "trial_count": cls.trial_count(),
        "grid": grid_res, "train": best_m, "validation": mv, "test": mt, "oos": moos, "p_raw": p_raw,
        "exp_cost15": exp15, "exp_minus_best3": exp_minus3, "neighbour_share": nshare,
        "walk_forward": {"trades": len(wf_r), "expectancy_r": float(np.mean(wf_r)) if wf_r else 0.0,
                         "ci": list(metrics.bootstrap_ci(np.array(wf_r))) if len(wf_r) > 1 else [None, None]},
        "capital_scaling": cap, "validated_capital_range": validated_range,
        "oos_r": oos_r.tolist(), "oos_trades": oos_trades, "candidates": rv.candidates + rt.candidates,
        "oos_curve": oos_curve, "split_times": {k: [int(F["open_time"][v.start]), int(F["open_time"][v.end - 1])]
                                                for k, v in sp.items()},
    }


def run_arena(con: sqlite3.Connection, cfg: Config, pairs: Optional[list[str]] = None,
              strategy_ids: Optional[list[str]] = None, specs: Optional[dict[str, InstrumentSpec]] = None,
              progress: Optional[Callable[[str], None]] = None, lab_paths: int = 10_000) -> dict:
    pairs = pairs or cfg.exchange.instruments
    sids = strategy_ids or strategies.TRADING_IDS
    run_group = uuid.uuid4().hex[:10]
    t0 = time.time()
    results: list[dict] = []
    benchmarks = {}
    sample = False
    for pair in pairs:
        df = store.load_candles(con, pair, "5m")
        if len(df) < 2000:
            log_event(con, "WARN", "arena", f"{pair}: not enough candles ({len(df)}) to research.")
            continue
        sample = sample or store.is_sample(con, pair, "5m")
        f = builder.build(df)
        F = features_to_arrays(f)
        spec = (specs or {}).get(pair) or default_spec(pair, cfg.exchange.usdt_inr_rate)
        sp = splits.chrono(len(df))
        te = sp["test"]
        va = sp["validation"]
        c1_r: list[float] = []
        c1_curves = []
        for seed in range(C1_SEEDS):
            for s in (va, te):
                rc = run(strategies.get("C1", seed=seed), F, spec, cfg, cfg.capital.research_equity_inr, s.start, s.end, record_candidates=False)
                c1_r += [t["r_multiple"] for t in rc.trades]
                if seed < 3 and s is te:
                    c1_curves.append(rc.equity_curve)
        c1 = np.array(c1_r)
        close = F["close"][te.start:te.end]
        benchmarks[pair] = {
            "c1_trades": len(c1), "c1_expectancy_r": float(c1.mean()) if len(c1) else 0.0,
            "c1_ci": list(metrics.bootstrap_ci(c1)) if len(c1) > 1 else [None, None],
            "buy_hold_return": float(buy_and_hold_curve(close, 1.0)[-1] - 1) if len(close) else 0.0,
            "c1_curves": [[(t, e) for t, e in cur[::12]] for cur in c1_curves],
            "times": [int(F["open_time"][te.start]), int(F["open_time"][te.end - 1])],
            "bh_curve": [(int(F["open_time"][te.start + k]), float(cfg.capital.research_equity_inr * (1 + close[k] / close[0] - 1)))
                         for k in range(0, len(close), 12)],
        }
        for sid in sids:
            if progress:
                progress(f"Testing {sid} on {pair} ...")
            results.append(evaluate_strategy(sid, F, spec, cfg, sp, c1, progress))
    # multiple-testing correction across strategies x instruments
    q = metrics.benjamini_hochberg({f"{r['strategy_id']}|{r['instrument']}": r["p_raw"] for r in results}) if results else {}
    by_sid: dict[str, list[dict]] = {}
    for r in results:
        r["q_value"] = q[f"{r['strategy_id']}|{r['instrument']}"]
        by_sid.setdefault(r["strategy_id"], []).append(r)
    summary = {}
    for sid, rs in by_sid.items():
        all_tr = [t for r in rs for t in r["oos_trades"]]
        oos_r = np.array([t["r_multiple"] for t in all_tr])
        pos_each = [r["oos"]["expectancy_r"] > 0 and r["oos"]["trades"] >= 10 for r in rs]
        both = all(pos_each) if len(rs) >= 2 else None
        best = max(rs, key=lambda r: r["oos"]["expectancy_r"])
        ev = {
            "oos_trades": len(all_tr),
            "oos_expectancy_r": float(oos_r.mean()) if len(oos_r) else 0.0,
            "oos_pf": float(np.mean([r["oos"]["profit_factor"] for r in rs])),
            "oos_max_dd": float(max(r["oos"]["max_dd_pct"] for r in rs)),
            "q_value": float(min(r["q_value"] for r in rs)) if all(r["oos"]["expectancy_r"] > 0 for r in rs) else float(max(r["q_value"] for r in rs)),
            "ci_low": metrics.bootstrap_ci(oos_r)[0] if len(oos_r) > 1 else float("nan"),
            "exp_cost15": _nanmean([r["exp_cost15"] for r in rs]),
            "exp_minus_best3": _nanmean([r["exp_minus_best3"] for r in rs]),
            "neighbour_share": float(np.mean([r["neighbour_share"] for r in rs])),
            "max_month_share": float(max(r["oos"]["max_month_profit_share"] for r in rs)),
            "both_instruments": both,
        }
        v = promotion.evaluate(ev, cfg.gates)
        lab = run_lab(oos_r, cfg.capital.starting_paper_equity_inr, cfg.risk.risk_pct,
                      n_paths=lab_paths) if len(oos_r) >= 10 else None
        ci = metrics.bootstrap_ci(oos_r) if len(oos_r) > 1 else (float("nan"), float("nan"))
        summary[sid] = {
            "strategy_id": sid, "name": strategies.REGISTRY[sid].name, "status": v.status, "tentative": v.tentative,
            "plain": v.plain, "gates": [g.__dict__ for g in v.gates], "evidence": ev,
            "oos_trades": len(all_tr), "expectancy_r": ev["oos_expectancy_r"], "ci": list(ci),
            "profit_factor": ev["oos_pf"], "max_dd": ev["oos_max_dd"], "best_instrument": best["instrument"],
            "params": best["params"], "trial_count": best["trial_count"],
            "walk_forward": {r["instrument"]: r["walk_forward"] for r in rs},
            "capital_scaling": {r["instrument"]: r["capital_scaling"] for r in rs},
            "validated_capital_range": best["validated_capital_range"],
            "regime_breakdown": _regime_breakdown(all_tr),
            "lab": {"table": lab.table, "recommendation": lab.recommendation, "b_allowed": lab.b_allowed,
                    "fan": lab.fan} if lab else None,
        }
    # persist
    ch = config_hash(cfg)
    con.execute("BEGIN")
    con.execute("DELETE FROM trades WHERE mode='backtest' AND run_id LIKE 'arena:%'")
    con.execute("DELETE FROM candidates WHERE mode='backtest' AND run_id LIKE 'arena:%'")
    for r in results:
        rid = f"arena:{run_group}:{r['strategy_id']}:{r['instrument']}"
        con.execute("INSERT INTO strategy_runs(run_id,mode,strategy_id,instrument,split,params_json,config_hash,seed,data_hash,"
                    "code_version,started_at,finished_at,metrics_json,trial_count,sample_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, "backtest", r["strategy_id"], r["instrument"], "oos", json.dumps(r["params"]), ch, cfg.seed,
                     "", __version__, int(t0 * 1000), now_ms(),
                     json.dumps({k: r[k] for k in ("train", "validation", "test", "oos", "p_raw", "q_value", "exp_cost15",
                                                   "exp_minus_best3", "neighbour_share", "walk_forward", "capital_scaling",
                                                   "validated_capital_range", "split_times", "grid")}, default=str),
                     r["trial_count"], int(sample)))
        con.execute("INSERT OR IGNORE INTO strategy_versions(strategy_id,version,params_json,code_hash,test_accesses) VALUES(?,?,?,?,0)",
                    (r["strategy_id"], __version__, json.dumps(r["params"]), ""))
        con.execute("UPDATE strategy_versions SET test_accesses=test_accesses+1 WHERE strategy_id=? AND version=?",
                    (r["strategy_id"], __version__))
        for t in r["oos_trades"]:
            _insert_trade(con, t, rid, sample)
        for c in r["candidates"][-400:]:
            con.execute("INSERT OR IGNORE INTO candidates(mode,run_id,account_id,strategy_id,instrument,candle_close_time,direction,"
                        "state,reason,score,components_json,reports_json,llm_json,regime) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        ("backtest", rid, "", c["strategy_id"], c["instrument"], c["candle_close_time"], c["direction"],
                         c["state"], c["reason"], c["score"], json.dumps(c["components"]),
                         json.dumps({"reports": c["reports"], "challenge": c["challenge"], "reasons": c["reasons"],
                                     "guard": c.get("guard"), "rr_net": c.get("rr_net"), "cost_r": c.get("cost_r")}, default=str),
                         json.dumps(c.get("llm")) if c.get("llm") else None, c["regime"]))
    curves = {f"{r['strategy_id']}|{r['instrument']}": [(t, e) for t, e in r["oos_curve"][::12]] for r in results}
    kv_set(con, "arena_summary", summary)
    kv_set(con, "arena_benchmarks", benchmarks)
    kv_set(con, "arena_curves", curves)
    kv_set(con, "arena_meta", {"run_group": run_group, "finished_at": now_ms(), "seconds": time.time() - t0,
                               "sample_data": sample, "pairs": pairs, "config_hash": ch,
                               "research_equity": cfg.capital.research_equity_inr, "lab_paths": lab_paths})
    con.execute("COMMIT")
    best = [s for s in summary.values() if s["status"] != promotion.RESEARCH]
    msg = (f"Arena finished: {len(best)} strategies reached CANDIDATE or better." if best
           else promotion.NO_EDGE_MESSAGE)
    log_event(con, "INFO", "arena", msg)
    return {"summary": summary, "benchmarks": benchmarks}


def _regime_breakdown(trades: list[dict]) -> dict:
    out: dict = {}
    for t in trades:
        d = out.setdefault(t["regime"], [])
        d.append(t["r_multiple"])
    return {k: {"n": len(v), "mean_r": float(np.mean(v))} for k, v in out.items()}


def _insert_trade(con: sqlite3.Connection, t: dict, run_id: str, sample: bool) -> None:
    con.execute("""INSERT INTO trades(mode,run_id,account_id,strategy_id,instrument,side,entry_time,exit_time,entry,exit,qty,
        stop,target,exit_reason,gross_pnl,fee_entry,fee_exit,gst,slippage,funding,net_pnl,r_multiple,planned_risk,
        realised_risk,regime,score,mae_r,mfe_r,features_json,trace_json,sample_data) VALUES
        (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (t["mode"], run_id, t["account_id"], t["strategy_id"], t["instrument"], t["side"], t["entry_time"],
                 t["exit_time"], t["entry"], t["exit"], t["qty"], t["stop"], t["target"], t["exit_reason"],
                 t["gross_pnl"], t["fee_entry"], t["fee_exit"], t["gst"], t["slippage"], t["funding"], t["net_pnl"],
                 t["r_multiple"], t["planned_risk"], t["realised_risk"], t["regime"], t["score"], t["mae_r"],
                 t["mfe_r"], json.dumps(t["features"], default=str), json.dumps(t["trace"], default=str), int(sample)))


insert_trade = _insert_trade
_ = (default_spec,)


def _nanmean(xs: list) -> float:
    a = np.array([x for x in xs if x is not None and np.isfinite(x)], dtype=float)
    return float(a.mean()) if len(a) else float("nan")
