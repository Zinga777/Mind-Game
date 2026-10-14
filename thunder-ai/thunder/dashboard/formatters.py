"""Number/time formatting: INR with Indian digit grouping, signed %, R-multiples, IST times."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def indian_group(n: int) -> str:
    s = str(abs(int(n)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def inr(x: float | None, decimals: int = 2, sign: bool = False) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    neg = x < 0
    q = round(abs(x), decimals)
    whole = int(q)
    frac = f"{q - whole:.{decimals}f}"[1:] if decimals else ""
    s = f"₹{indian_group(whole)}{frac}"
    if neg:
        return "−" + s if not sign else "▼ −" + s
    return ("▲ +" + s) if sign and x > 0 else s


def pct(x: float | None, decimals: int = 1, sign: bool = True) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    v = x * 100
    if round(v, decimals) == 0:
        v = 0.0  # never print "-0%"
    if not sign:
        return f"{v:.{decimals}f}%"
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.{decimals}f}%"


def r_mult(x: float | None, decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{'+' if x > 0 else '−' if x < 0 else ''}{abs(x):.{decimals}f}R"


def arrow(x: float | None) -> str:
    if x is None or x == 0 or (isinstance(x, float) and not math.isfinite(x)):
        return "•"
    return "▲" if x > 0 else "▼"


def ist(ts_ms: int | None, fmt: str = "%d %b %Y, %H:%M IST") -> str:
    if not ts_ms:
        return "—"
    return datetime.fromtimestamp(ts_ms / 1000, tz=IST).strftime(fmt)


def utc(ts_ms: int | None) -> str:
    if not ts_ms:
        return "—"
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def ago(ms: int | None, now_ms: int) -> str:
    if not ms:
        return "never"
    s = max(0, (now_ms - ms) // 1000)
    if s < 90:
        return f"{s} s ago"
    if s < 5400:
        return f"{s // 60} min ago"
    if s < 172800:
        return f"{s // 3600} h ago"
    return f"{s // 86400} days ago"
