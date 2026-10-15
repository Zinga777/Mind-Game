import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_TMP = tempfile.mkdtemp(prefix="thunder-test-")
os.environ["THUNDER_DATA_DIR"] = _TMP
os.environ["THUNDER_CONFIG"] = str(Path(_TMP) / "config.yaml")
os.environ["THUNDER_NO_KEYRING"] = "1"

from thunder.config import Config  # noqa: E402
from thunder.exchanges.base import InstrumentSpec  # noqa: E402
from thunder.strategies.base import Candidate, Strategy  # noqa: E402

T0 = 1_735_689_600_000  # 2025-01-01 00:00 UTC
TF = 300_000


@pytest.fixture
def cfg():
    return Config()


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("THUNDER_DATA_DIR", str(tmp_path))
    from thunder.db import connect
    c = connect(tmp_path / "t.db")
    yield c
    c.close()


def unit_spec(**kw) -> InstrumentSpec:
    d = dict(pair="TEST", min_qty=1.0, qty_step=1.0, tick=0.01, contract_value=1.0, max_leverage=20,
             quote_to_inr=1.0, min_notional=0.0)
    d.update(kw)
    return InstrumentSpec(**d)


def make_df(n: int = 600, price: float = 100.0, seed: int = 0, vol: float = 0.0015) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    c = price * np.exp(np.cumsum(rng.normal(0, vol, n)))
    o = np.concatenate([[price], c[:-1]])
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, vol / 2, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, vol / 2, n)))
    return pd.DataFrame({"open_time": T0 + np.arange(n) * TF, "open": o, "high": h, "low": l, "close": c,
                         "volume": (rng.lognormal(0, 0.3, n) + 1) * 1000})


class OneShot(Strategy):
    """Test strategy: emits one candidate at bar `at` with fixed stop/target distances."""
    id = "S1"  # reuse a registered id so desk/trade code paths are the real ones
    name = "test one-shot"
    is_control = True  # skip score threshold; hard rules still apply
    min_stop_atr_h1 = 0.0

    def __init__(self, at: int, direction: str = "long", stop_pct: float = 0.01, target_pct: float = 0.03,
                 entry_type: str = "market", time_stop: int = 50, breakeven=None):
        super().__init__()
        self.at, self.dir, self.sp, self.tp, self.et, self.ts, self.be = at, direction, stop_pct, target_pct, entry_type, time_stop, breakeven

    def detect(self, F, i):
        if i != self.at:
            return None
        c = float(F["close"][i])
        s = c * (1 - self.sp) if self.dir == "long" else c * (1 + self.sp)
        t = c * (1 + self.tp) if self.dir == "long" else c * (1 - self.tp)
        return Candidate(self.id, i, self.dir, self.et, c, s, t, c * 1.01 if self.dir == "long" else c * 0.99,
                         self.ts, 2, self.be, ["test"], "", str(F["regime"][i]))

    def checklist_plain(self):
        return ["test"]
