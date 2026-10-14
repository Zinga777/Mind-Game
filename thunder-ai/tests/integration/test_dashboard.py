"""Streamlit AppTest smoke tests for every page in demo mode (no exceptions, honest labels present)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from thunder.backtest.arena import run_arena
from thunder.config import Config
from thunder.data.downloader import load_demo
from thunder.db import connect, kv_set
from thunder.engine.main import Engine

PAGES = Path(__file__).resolve().parents[2] / "thunder" / "dashboard" / "pages"


@pytest.fixture(scope="module")
def demo_db():
    # uses the session-wide THUNDER_DATA_DIR set in conftest
    con = connect()
    cfg = Config()
    load_demo(con, cfg.exchange.instruments, days=60, seed=2, future_days=5)
    run_arena(con, cfg, strategy_ids=["S1", "S2"], lab_paths=200)
    kv_set(con, "engine_running", True)
    eng = Engine(con, cfg, demo_bars_per_tick=300)
    for _ in range(3):
        eng.tick()
    from thunder.insights import report
    report.generate(con, "backtest")
    kv_set(con, "setup_done", True)
    yield con


@pytest.mark.parametrize("page", sorted(p.name for p in PAGES.glob("*.py")))
def test_page_renders(demo_db, page):
    at = AppTest.from_file(str(PAGES / page), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_home_shows_mode_ribbon_and_verdict(demo_db):
    at = AppTest.from_file(str(PAGES / "home.py"), default_timeout=60).run()
    html = " ".join(m.value for m in at.markdown)
    assert "SAMPLE DATA" in html and "PAPER" in html
    assert "Verdict" in " ".join(h.value for h in at.subheader)


def test_live_page_locked(demo_db):
    at = AppTest.from_file(str(PAGES / "live.py"), default_timeout=60).run()
    arm = [b for b in at.button if b.label == "ARM LIVE TRADING"]
    assert arm and arm[0].disabled
    assert "REAL MONEY" in " ".join(m.value for m in at.markdown)


def test_setup_wizard_first_run(demo_db):
    kv_set(demo_db, "setup_done", False)
    try:
        at = AppTest.from_file(str(PAGES / "home.py"), default_timeout=60).run()
        assert "Welcome to THUNDER" in at.title[0].value
    finally:
        kv_set(demo_db, "setup_done", True)
