"""Per-wallet performance from raw fills + market resolutions.

Win definition: a *resolved* market where the wallet's realized PnL
(sell proceeds - buy cost + resolution payout of remaining shares) > epsilon.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field


@dataclass
class MarketPnl:
    condition_id: str
    title: str = ""
    resolved: bool = False
    pnl: float = 0.0
    invested: float = 0.0
    n_trades: int = 0
    both_sides: bool = False
    entry_prices: list = field(default_factory=list)
    first_ts: int = 0
    last_ts: int = 0
    hours_to_close: float | None = None


def market_pnls(trades: list[dict], resolutions: dict[str, list[float]],
                close_times: dict[str, int] | None = None) -> list[MarketPnl]:
    """trades: normalized rows (store format). resolutions: condition_id -> outcome prices."""
    by_market: dict[str, dict] = {}
    for t in trades:
        m = by_market.setdefault(t["condition_id"], {"tokens": {}, "title": t.get("title") or "", "ts": []})
        tok = m["tokens"].setdefault(t["asset"], {"qty": 0.0, "cash": 0.0, "idx": t.get("outcome_index"), "buys": []})
        if t["side"] == "BUY":
            tok["qty"] += t["size"]
            tok["cash"] -= t["usd"]
            tok["buys"].append((t["price"], t["usd"]))
        else:
            tok["qty"] -= t["size"]
            tok["cash"] += t["usd"]
        m["ts"].append(t["ts"])

    out = []
    for cid, m in by_market.items():
        mp = MarketPnl(condition_id=cid, title=m["title"])
        mp.n_trades = sum(1 for _ in m["ts"])
        mp.first_ts, mp.last_ts = min(m["ts"]), max(m["ts"])
        prices = resolutions.get(cid)
        mp.resolved = prices is not None
        sides_held = 0
        for tok in m["tokens"].values():
            bought = sum(usd for _, usd in tok["buys"])
            mp.invested += bought
            if bought > 0:
                sides_held += 1
            mp.entry_prices.extend(p for p, _ in tok["buys"])
            pnl = tok["cash"]
            if mp.resolved:
                idx = tok["idx"]
                payout = prices[idx] if (idx is not None and idx < len(prices)) else 0.0
                pnl += max(tok["qty"], 0.0) * payout
            mp.pnl += pnl
        mp.both_sides = sides_held >= 2
        if mp.resolved and close_times and cid in close_times:
            mp.hours_to_close = max(0.0, (close_times[cid] - mp.first_ts) / 3600)
        out.append(mp)
    return out


def wallet_stats(mpnls: list[MarketPnl], epsilon: float = 0.01) -> dict:
    resolved = [m for m in mpnls if m.resolved]
    wins = sum(1 for m in resolved if m.pnl > epsilon)
    losses = sum(1 for m in resolved if m.pnl < -epsilon)
    judged = wins + losses
    entry_prices = [p for m in mpnls for p in m.entry_prices]
    stakes = [m.invested for m in mpnls if m.invested > 0]
    late = [m.hours_to_close for m in resolved if m.hours_to_close is not None]
    return {
        "trade_count": sum(m.n_trades for m in mpnls),
        "markets_n": len(mpnls),
        "resolved_n": len(resolved),
        "open_n": len(mpnls) - len(resolved),
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / judged) if judged else 0.0,
        "realized_pnl": sum(m.pnl for m in resolved),
        "avg_stake": statistics.fmean(stakes) if stakes else 0.0,
        "median_entry_price": statistics.median(entry_prices) if entry_prices else 0.0,
        "both_sides_share": (sum(1 for m in mpnls if m.both_sides) / len(mpnls)) if mpnls else 0.0,
        "median_hours_to_close": statistics.median(late) if late else None,
    }
