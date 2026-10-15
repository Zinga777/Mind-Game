"""Typed configuration (pydantic). Every default here is documented in the spec
(Section 5) or in docs/DECISIONS.md. Loading/saving lives in thunder.config.loader.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ExchangeCfg(BaseModel):
    name: Literal["coindcx"] = "coindcx"
    margin_currency: Literal["INR", "USDT"] = "INR"
    instruments: list[str] = Field(default_factory=lambda: ["B-BTC_USDT", "B-ETH_USDT"])
    # INR value of 1 USDT used by CoinDCX for INR-margined futures.
    # UNVERIFIED_AGAINST_LIVE_EXCHANGE — read the real rate from the exchange when live.
    usdt_inr_rate: float = Field(default=88.0, gt=0)
    requests_per_second: float = Field(default=5.0, gt=0, le=20)
    api_base: str = "https://api.coindcx.com"
    public_base: str = "https://public.coindcx.com"


class TimeframeCfg(BaseModel):
    decision: str = "5m"
    context: list[str] = Field(default_factory=lambda: ["15m", "1h"])
    history_days: int = Field(default=365, ge=7)


class CapitalCfg(BaseModel):
    starting_paper_equity_inr: float = Field(default=3000.0, gt=0)
    allocated_live_cap_inr: float = Field(default=3000.0, gt=0)
    deposit_shock_pct: float = Field(default=0.25, gt=0, le=5)
    # Edge is measured in R at a capital where the minimum order size does not bind; the
    # capital-scaling test then shows what is feasible at each real account size.
    research_equity_inr: float = Field(default=100_000.0, gt=0)
    scaling_ladder_inr: list[float] = Field(default_factory=lambda: [3_000.0, 10_000.0, 25_000.0, 100_000.0, 500_000.0])


class RiskCfg(BaseModel):
    risk_pct: float = Field(default=0.005, gt=0, le=0.02)
    max_risk_per_trade_inr: Optional[float] = Field(default=None, gt=0)
    daily_loss_stop_pct: float = Field(default=0.02, gt=0, le=0.2)
    max_drawdown_pct: float = Field(default=0.10, gt=0, le=0.5)
    max_open_positions: int = Field(default=1, ge=1, le=5)
    max_leverage_used: float = Field(default=5.0, gt=0, le=20)
    max_fraction_of_exchange_leverage: float = 0.5
    margin_free_fraction: float = 0.5
    min_rr_net: float = Field(default=1.2, gt=0)
    max_cost_r: float = Field(default=0.30, gt=0, le=1)
    max_depth_fraction: float = 0.20
    max_volume_fraction: float = 0.05
    stop_to_liq_max_fraction: float = 0.5
    recovery_policy: Literal["A", "B", "C"] = "A"
    stale_multiple: float = 2.0
    blackout_windows_utc: list[str] = Field(default_factory=list)  # e.g. ["23:55-00:05"]

    @field_validator("recovery_policy")
    @classmethod
    def _no_martingale(cls, v: str) -> str:  # H2
        if v.upper() in ("D", "MARTINGALE"):
            raise ValueError("Classic Martingale can never be selected (rule H2).")
        return v


class CostCfg(BaseModel):
    maker_fee: float = Field(default=0.0002, ge=0, le=0.01)
    taker_fee: float = Field(default=0.0005, ge=0, le=0.01)
    gst: float = Field(default=0.18, ge=0, le=0.5)
    slip_market_bps: float = Field(default=2.0, ge=0)
    slip_stop_bps: float = Field(default=5.0, ge=0)
    high_vol_slip_multiplier: float = Field(default=2.0, ge=1)
    funding_rate_per_interval: float = 0.0001   # used only when the exchange value is unknown
    funding_interval_hours: float = 8.0
    tax_rate: float = 0.30
    tds_rate: float = 0.01


class CouncilCfg(BaseModel):
    mode: Literal["rules_only", "rules_plus_llm"] = "rules_only"
    threshold: int = Field(default=70, ge=0, le=100)
    llm_model: str = "claude-opus-5-5"
    max_llm_calls_per_day: int = 50
    max_llm_cost_usd_per_day: float = 1.0


class GatesCfg(BaseModel):
    min_oos_trades: int = 100
    tentative_oos_trades: int = 30
    min_profit_factor: float = 1.2
    max_dd: float = 0.10
    p_value: float = 0.05
    paper_days: int = 30
    paper_trades: int = 50
    relaxed: bool = False  # set only with a typed confirmation


class AlertsCfg(BaseModel):
    telegram_enabled: bool = False
    email_enabled: bool = False


class DashboardCfg(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8501
    remote_access: bool = False


class Config(BaseModel):
    exchange: ExchangeCfg = Field(default_factory=ExchangeCfg)
    timeframes: TimeframeCfg = Field(default_factory=TimeframeCfg)
    capital: CapitalCfg = Field(default_factory=CapitalCfg)
    risk: RiskCfg = Field(default_factory=RiskCfg)
    costs: CostCfg = Field(default_factory=CostCfg)
    council: CouncilCfg = Field(default_factory=CouncilCfg)
    gates: GatesCfg = Field(default_factory=GatesCfg)
    alerts: AlertsCfg = Field(default_factory=AlertsCfg)
    dashboard: DashboardCfg = Field(default_factory=DashboardCfg)
    data_mode: Literal["demo", "real"] = "demo"
    seed: int = 7
