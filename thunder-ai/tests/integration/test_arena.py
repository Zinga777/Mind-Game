"""Arena end-to-end on SAMPLE DATA: controls behave, verdict is honest, results stored with labels."""
import json

import numpy as np
import pytest

from thunder.backtest import promotion
from thunder.backtest.arena import run_arena
from thunder.config import Config
from thunder.data.downloader import load_demo
from thunder.insights import report


@pytest.mark.slow
def test_arena_on_sample_data(con):
    cfg = Config()
    load_demo(con, ["B-ETH_USDT"], days=75, seed=3, future_days=1)
    res = run_arena(con, cfg, pairs=["B-ETH_USDT"], strategy_ids=["S1", "S4"], lab_paths=300)
    s, b = res["summary"], res["benchmarks"]["B-ETH_USDT"]
    # control: random entry has no edge after costs
    assert b["c1_trades"] > 50 and b["c1_expectancy_r"] < 0.05
    for sid, v in s.items():
        assert v["status"] in promotion.LADDER
        assert v["trial_count"] >= 1 and len(v["gates"]) >= 5
    meta = json.loads(con.execute("SELECT value FROM kv WHERE key='arena_meta'").fetchone()[0])
    assert meta["sample_data"] is True
    # results are stored as BACKTEST and flagged as sample data
    modes = {r[0] for r in con.execute("SELECT DISTINCT mode FROM trades")}
    assert modes <= {"backtest"}
    assert con.execute("SELECT COUNT(*) FROM trades WHERE sample_data=0").fetchone()[0] == 0
    ins = report.generate(con, "backtest")
    assert "SAMPLE DATA" in ins["markdown"] or not ins["rows"]


def test_no_edge_message_is_shown_when_true():
    assert "No strategy has shown a net edge yet" in promotion.NO_EDGE_MESSAGE
    _ = np
