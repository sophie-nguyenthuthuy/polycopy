"""Replay stored history of qualified wallets as if we had copied every entry.

No historical order books exist, so entries are modeled at the trader's own
fill price plus `backtest_adverse_bps` (you always get a worse price than the
insider — they moved the market). Exits: trader's sell (same penalty),
else resolution payout, else current market price (unrealized).
"""
from __future__ import annotations

import json
import time

from . import simulate
from .config import Config
from .simulate import STRATEGIES
from .store import Store


def _current_price(market_row, asset: str) -> float | None:
    idx = simulate._asset_index(market_row, asset)
    if idx is None or not market_row["outcome_prices"]:
        return None
    try:
        return float(json.loads(market_row["outcome_prices"])[idx])
    except (ValueError, IndexError, TypeError):
        return None


def run(store: Store, cfg: Config) -> str:
    store.clear_fills("backtest")
    resolutions = store.resolutions()
    adverse = cfg.backtest_adverse_bps / 10_000
    wallets = {w["address"]: w for w in store.wallets(qualified_only=True)}

    for addr, w in wallets.items():
        for t in store.wallet_trades(addr):
            market = store.market(t["condition_id"])
            fee_bps = market["taker_fee_bps"] if market else cfg.default_fee_bps
            if t["side"] == "BUY" and 0.005 <= t["price"] <= cfg.max_entry_price:
                entry = min(0.999, t["price"] * (1 + adverse))
                for strat, usd, labels in STRATEGIES:
                    if w["label"] in labels:
                        simulate.open_copy_fill(store, strat, "backtest", t, usd,
                                                book=None, fee_bps=fee_bps, slippage_bps=0,
                                                fallback_price=entry)
            elif t["side"] == "SELL":
                exit_p = max(0.001, t["price"] * (1 - adverse))
                for f in store.open_fills(mode="backtest"):
                    if f["wallet"] == addr and f["asset"] == t["asset"]:
                        simulate.close_at(store, f, exit_p, t["ts"], "trader_exit", fee_bps)

    # settle what's left
    for f in store.open_fills(mode="backtest"):
        market = store.market(f["condition_id"])
        if f["condition_id"] in resolutions:
            idx = simulate._asset_index(market, f["asset"])
            payout = resolutions[f["condition_id"]][idx] if idx is not None else 0.0
            simulate.close_at(store, f, payout, int(time.time()), "resolution")
        else:
            p = _current_price(market, f["asset"])
            if p is not None:
                store.mark_fill(f["id"], p)

    return simulate.report(store, "backtest")
