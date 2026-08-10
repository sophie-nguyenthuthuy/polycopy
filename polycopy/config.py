"""Configuration: env vars override polycopy.toml override defaults."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields


@dataclass
class Config:
    db_path: str = "polycopy.db"
    # discovery
    leaderboard_limit: int = 50
    leaderboard_windows: tuple = ("7d", "30d", "all")
    max_trades_per_wallet: int = 1000  # data-api offset cap is ~1000 anyway
    min_resolved_markets: int = 5      # need this many resolved markets to judge a record
    near_perfect_win_rate: float = 0.90
    pnl_epsilon: float = 0.01          # |pnl| below this counts as neutral, not win/loss
    # insider heuristics
    insider_max_trades: int = 200
    insider_min_avg_stake: float = 200.0
    insider_max_entry_price: float = 0.75
    insider_geo_share: float = 0.40
    insider_late_entry_hours: float = 96.0
    insider_min_score: int = 5
    arb_both_sides_share: float = 0.30
    scalper_min_trades: int = 800
    # watch / simulation
    poll_sec: int = 60
    slippage_extra_bps: int = 50       # extra adverse bps on top of book walk
    backtest_adverse_bps: int = 150    # entry penalty vs trader's fill in backtests
    default_fee_bps: int = 0           # most Polymarket markets: no taker fee
    max_entry_price: float = 0.985     # don't copy buys of near-certain outcomes
    # telegram
    telegram_token: str = ""
    telegram_chat_id: str = ""
    # http
    rate_limit_sec: float = 0.25
    http_timeout: float = 20.0

    @classmethod
    def load(cls, path: str = "polycopy.toml") -> "Config":
        cfg = cls()
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = tomllib.load(f)
            for f_ in fields(cls):
                if f_.name in data:
                    setattr(cfg, f_.name, data[f_.name])
        env_map = {
            "POLYCOPY_DB": "db_path",
            "TELEGRAM_BOT_TOKEN": "telegram_token",
            "TELEGRAM_CHAT_ID": "telegram_chat_id",
        }
        for env, attr in env_map.items():
            if os.environ.get(env):
                setattr(cfg, attr, os.environ[env])
        return cfg
