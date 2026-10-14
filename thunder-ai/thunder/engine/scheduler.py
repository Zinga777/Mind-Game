"""Candle-close clock and keep-awake helper."""
from __future__ import annotations

import os
import subprocess
import sys

from ..exchanges.base import TIMEFRAME_MS


def next_poll_ms(now_ms: int, timeframe: str = "5m", delay_ms: int = 12_000) -> int:
    """Shortly after the next candle close."""
    tf = TIMEFRAME_MS[timeframe]
    return (now_ms // tf + 1) * tf + delay_ms


def feature_anchor_ms(bar_open_ms: int, lookback_days: int = 45, block_days: int = 10) -> int:
    """Deterministic feature-window start for a bar: >= lookback_days of history, aligned to
    block_days so results do not depend on when the engine was (re)started."""
    day = 86_400_000
    return ((bar_open_ms - lookback_days * day) // (block_days * day)) * block_days * day


_keep = None


def keep_awake() -> None:
    """Best-effort: ask the OS not to sleep while the engine runs."""
    global _keep
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
        elif sys.platform == "darwin" and _keep is None:
            _keep = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
    except Exception:
        pass
