"""Copy-trade simulation: order-book fills, fees, slippage, MTM, reports.

Fee formula (Polymarket CLOB): fee = base_rate_bps/10000 * min(p, 1-p) * shares.
Most markets have 0 bps; the 5-minute crypto markets carry taker fees.

Strategies (mode='live' fills created by watch; mode='backtest' by replay):
  s10        — $10 per copied entry, INSIDER_SUSPECT wallets only
  s100       — $100 per copied entry, INSIDER_SUSPECT wallets only
  perfect100 — $100 per copied entry, all qualified (perfect/near-perfect) wallets
"""
from __future__ import annotations

import time

STRATEGIES = (
    ("s10", 10.0, ("INSIDER_SUSPECT",)),
    ("s100", 100.0, ("INSIDER_SUSPECT",)),
    ("perfect100", 100.0, ("INSIDER_SUSPECT", "PERFECT", "NEAR_PERFECT")),
)


def fee_usd(bps: int, price: float, qty: float) -> float:
    return (bps / 10_000) * min(price, 1 - price) * qty


def walk_book(levels: list[dict], usd: float, side: str = "BUY") -> tuple[float, float]:
    """Fill `usd` notional against book levels; returns (qty, avg_price).
    For BUY walk asks ascending; for SELL walk bids descending (usd = qty*price proceeds target unused; SELL walks by qty elsewhere)."""
    if not levels:
        return 0.0, 0.0
    lv = sorted(((float(l["price"]), float(l["size"])) for l in levels),
                key=lambda x: x[0], reverse=(side == "SELL"))
    remaining, qty, cost = usd, 0.0, 0.0
    for price, size in lv:
        if price <= 0:
            continue
        take_usd = min(remaining, price * size)
        qty += take_usd / price
        cost += take_usd
        remaining -= take_usd
        if remaining <= 1e-9:
            break
    return (qty, cost / qty) if qty else (0.0, 0.0)


def best_bid(book: dict) -> float:
    bids = book.get("bids") or []
    return max((float(b["price"]) for b in bids), default=0.0)


def open_copy_fill(store, strategy: str, mode: str, trade: dict, usd: float,
                   book: dict | None, fee_bps: int, slippage_bps: int,
                   fallback_price: float | None = None, entry_ts: int | None = None) -> dict | None:
    """Simulate copying a BUY. Uses live book when given, else trader's own price + adverse bps."""
    if book and book.get("asks"):
        qty, avg = walk_book(book["asks"], usd, "BUY")
    else:
        avg = (fallback_price if fallback_price is not None else trade["price"])
        qty = 0.0
    if avg <= 0:
        return None
    avg = min(0.999, avg * (1 + slippage_bps / 10_000))
    qty = usd / avg
    fee = fee_usd(fee_bps, avg, qty)
    fill = dict(strategy=strategy, mode=mode, wallet=trade["wallet"],
                condition_id=trade["condition_id"], asset=trade["asset"],
                outcome=trade.get("outcome"), title=trade.get("title"),
                qty=qty, entry_price=avg, notional=usd, fee_usd=fee,
                entry_ts=entry_ts or trade["ts"])
    return fill if store.insert_fill(**fill) else None


def close_at(store, fill: dict, price: float, ts: int, reason: str, fee_bps: int = 0):
    proceeds = fill["qty"] * price
    fee = fee_usd(fee_bps, price, fill["qty"]) if 0 < price < 1 else 0.0
    pnl = proceeds - fill["notional"] - fill["fee_usd"] - fee
    store.close_fill(fill["id"], price, ts, reason, pnl)


def refresh_marks(store, api, cfg):
    """Close open live fills on resolved markets; mark the rest at best bid."""
    resolutions = store.resolutions()
    for fill in store.open_fills(mode="live"):
        cid = fill["condition_id"]
        if cid in resolutions:
            m = store.market(cid)
            idx = _asset_index(m, fill["asset"])
            payout = resolutions[cid][idx] if idx is not None else 0.0
            close_at(store, fill, payout, int(time.time()), "resolution")
        else:
            book = api.book(fill["asset"])
            bid = best_bid(book)
            if bid:
                store.mark_fill(fill["id"], bid)


def _asset_index(market_row, asset: str) -> int | None:
    import json
    if not market_row:
        return None
    try:
        tokens = json.loads(market_row["clob_token_ids"] or "[]")
        return tokens.index(asset)
    except (ValueError, TypeError):
        return None


def report(store, mode: str) -> str:
    lines = []
    for strat, usd, _labels in STRATEGIES:
        fills = [f for f in store.fills(mode) if f["strategy"] == strat]
        if not fills:
            lines.append(f"{strat:<11} no fills yet")
            continue
        closed = [f for f in fills if f["status"] == "closed"]
        opened = [f for f in fills if f["status"] == "open"]
        invested = sum(f["notional"] for f in fills)
        fees = sum(f["fee_usd"] or 0 for f in fills)
        realized = sum(f["pnl"] or 0 for f in closed)
        open_cost = sum(f["notional"] for f in opened)
        open_value = sum((f["mark_price"] or f["entry_price"]) * f["qty"] for f in opened)
        total = realized + (open_value - open_cost)
        w = sum(1 for f in closed if (f["pnl"] or 0) > 0)
        lines.append(
            f"{strat:<11} fills={len(fills):>3} (closed {len(closed)}, open {len(opened)}) "
            f"invested=${invested:,.0f} fees=${fees:,.2f} realized=${realized:+,.2f} "
            f"openMTM=${open_value - open_cost:+,.2f} total=${total:+,.2f} "
            f"({total / invested * 100 if invested else 0:+.1f}%) win {w}/{len(closed)}")
    return "\n".join(lines)
