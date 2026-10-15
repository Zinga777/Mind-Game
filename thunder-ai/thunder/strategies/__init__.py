"""Strategy registry."""
from .base import Candidate, Strategy
from .controls import RandomEntry
from .s1_trend_pullback import TrendPullback
from .s2_volume_breakout import VolumeBreakout
from .s3_range_mean_reversion import RangeMeanReversion
from .s4_candle_at_level import CandleAtLevel
from .s5_failed_breakout import FailedBreakout
from .s6_momentum import MomentumContinuation
from .s7_vwap import VwapStrategy
from .s8_session_open import SessionOpenBreakout

REGISTRY: dict[str, type[Strategy]] = {c.id: c for c in (
    TrendPullback, VolumeBreakout, RangeMeanReversion, CandleAtLevel, FailedBreakout,
    MomentumContinuation, VwapStrategy, SessionOpenBreakout, RandomEntry)}

TRADING_IDS = [k for k, v in REGISTRY.items() if not v.is_control]


def get(strategy_id: str, **params) -> Strategy:
    if strategy_id.upper() in ("D", "MARTINGALE"):
        raise ValueError("Martingale is not a strategy and can never be selected (H2).")
    return REGISTRY[strategy_id](**params)
