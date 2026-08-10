"""Wallet discovery + scanning.

Seeds candidate wallets from the PnL/volume leaderboards (plus any manually
supplied addresses), pulls each wallet's trade history, resolves the markets
they touched, computes win records and classifies them.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .api import PolymarketAPI
from .classify import QUALIFIED_LABELS, categorize, classify
from .config import Config
from .metrics import market_pnls, wallet_stats
from .store import Store


def _close_ts(row) -> int | None:
    raw = row["closed_time"] or row["end_date"]
    if not raw:
        return None
    raw = raw.replace(" ", "T", 1).replace("+00", "+00:00").replace("Z", "+00:00")
    try:
        return int(datetime.fromisoformat(raw).timestamp())
    except ValueError:
        return None


def sync_markets(store: Store, api: PolymarketAPI, condition_ids: list[str]):
    """Fetch metadata for unknown markets; re-fetch unresolved ones to catch resolutions."""
    need = store.missing_condition_ids(condition_ids)
    stale = [c for c in store.unresolved_condition_ids() if c in set(condition_ids)]
    todo = list(dict.fromkeys(need + stale))
    if todo:
        for m in api.markets_by_condition(todo):
            store.upsert_market(m, categorize(m.get("question") or ""))


def scan_wallet(store: Store, api: PolymarketAPI, cfg: Config, address: str,
                verbose: bool = False) -> dict:
    raw = api.wallet_trades_all(address, cfg.max_trades_per_wallet)
    store.insert_trades(raw)
    trades = store.wallet_trades(address)
    sync_markets(store, api, [t["condition_id"] for t in trades])

    resolutions = store.resolutions()
    close_times = {}
    for cid in {t["condition_id"] for t in trades}:
        row = store.market(cid)
        ts = _close_ts(row) if row else None
        if ts:
            close_times[cid] = ts

    mpnls = market_pnls(trades, resolutions, close_times)
    stats = wallet_stats(mpnls, cfg.pnl_epsilon)
    label, score, reasons = classify(stats, mpnls, cfg)
    qualified = label in QUALIFIED_LABELS
    name = raw[0].get("name", "") if raw else ""
    pseudonym = raw[0].get("pseudonym", "") if raw else ""
    store.upsert_wallet_stats(address, name, pseudonym, stats, label, score, reasons, qualified)

    result = dict(address=address, name=name, label=label, score=score,
                  reasons=reasons, qualified=qualified, **stats)
    if verbose:
        print(f"\n{address} ({name or pseudonym})")
        print(f"  label={label} score={score} qualified={qualified}")
        print(f"  {stats['wins']}W/{stats['losses']}L over {stats['resolved_n']} resolved "
              f"({stats['win_rate']:.0%}), {stats['trade_count']} trades, "
              f"realized ${stats['realized_pnl']:+,.0f}")
        for r in reasons:
            print(f"  - {r}")
    return result


def seed_from_recent(api: PolymarketAPI, pages: int = 4, min_usd: float = 300.0) -> list[str]:
    """Wallets placing large fills on geopolitics/politics markets in the recent
    global trade feed — the cohort leaderboards never surface."""
    seen: list[str] = []
    for page in range(pages):
        for t in api.trades(limit=500, offset=page * 500):
            usd = float(t["price"]) * float(t["size"])
            if usd >= min_usd and categorize(t.get("title") or "") in ("geopolitics", "politics"):
                seen.append(t["proxyWallet"])
    return list(dict.fromkeys(seen))


def discover(store: Store, api: PolymarketAPI, cfg: Config,
             extra_addresses: list[str] | None = None, limit: int | None = None,
             recent_pages: int = 0, use_leaderboard: bool = True) -> list[dict]:
    seeds: list[str] = list(extra_addresses or [])
    if recent_pages:
        try:
            geo = seed_from_recent(api, recent_pages)
            print(f"Seeded {len(geo)} wallets from recent large geo/politics fills")
            seeds.extend(geo)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] recent-trades seed: {e}")
    if use_leaderboard:
        for window in cfg.leaderboard_windows:
            for rank_type in ("pnl",):
                try:
                    rows = api.leaderboard(window, rank_type, cfg.leaderboard_limit)
                except Exception as e:  # noqa: BLE001
                    print(f"[warn] leaderboard {window}/{rank_type}: {e}")
                    continue
                seeds.extend(r["proxyWallet"] for r in rows)
    seeds = list(dict.fromkeys(seeds))
    if limit:
        seeds = seeds[:limit]
    print(f"Scanning {len(seeds)} candidate wallets...")

    results = []
    for i, addr in enumerate(seeds, 1):
        try:
            r = scan_wallet(store, api, cfg, addr)
        except Exception as e:  # noqa: BLE001 — one bad wallet must not kill the sweep
            print(f"[warn] scan {addr}: {e}")
            continue
        flag = " ***" if r["qualified"] else ""
        print(f"[{i}/{len(seeds)}] {addr[:10]} {r['label']:<15} "
              f"{r['wins']}W/{r['losses']}L wr={r['win_rate']:.0%} trades={r['trade_count']}{flag}")
        results.append(r)
    return results


def print_wallets(store: Store, qualified_only: bool):
    rows = store.wallets(qualified_only)
    if not rows:
        print("No qualified wallets yet." if qualified_only and store.wallets()
              else "No wallets stored yet. Run: polycopy discover")
        return
    print(f"{'address':<44} {'label':<16} {'W':>3} {'L':>3} {'wr':>5} {'trades':>6} {'pnl':>12} q")
    for w in rows:
        print(f"{w['address']:<44} {w['label']:<16} {w['wins']:>3} {w['losses']:>3} "
              f"{w['win_rate']:>5.0%} {w['trade_count']:>6} {w['realized_pnl']:>12,.0f} "
              f"{'*' if w['qualified'] else ''}")
        for r in json.loads(w["reasons"] or "[]"):
            print(f"    - {r}")
