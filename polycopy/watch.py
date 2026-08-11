"""Watch loop: poll qualified wallets, alert on new trades, open/close sim fills."""
from __future__ import annotations

import time

from . import simulate, telegram
from .api import PolymarketAPI
from .config import Config
from .discover import sync_markets
from .store import Store


def _sim_lines(fills: list[dict]) -> list[str]:
    return [f"sim {f['strategy']}: {f['qty']:.1f} sh @ {f['entry_price']:.3f} "
            f"(${f['notional']:.0f} + ${f['fee_usd']:.2f} fee)" for f in fills]


def process_new_trade(store: Store, api: PolymarketAPI, cfg: Config,
                      wallet_row: dict, trade: dict, dry_run: bool) -> None:
    market = store.market(trade["condition_id"])
    fee_bps = (market["taker_fee_bps"] if market and cfg.use_market_fee_field
               else cfg.default_fee_bps)

    new_fills = []
    if trade["side"] == "BUY" and trade["price"] <= cfg.max_entry_price:
        book = api.book(trade["asset"])
        for strat, usd, labels in simulate.STRATEGIES:
            if wallet_row["label"] in labels:
                f = simulate.open_copy_fill(
                    store, strat, "live", trade, usd, book, fee_bps,
                    cfg.slippage_extra_bps, entry_ts=int(time.time()))
                if f:
                    new_fills.append(f)
    elif trade["side"] == "SELL":
        # trader is exiting: close any open sim fills on the same token
        for f in store.open_fills(mode="live"):
            if f["wallet"] == trade["wallet"] and f["asset"] == trade["asset"]:
                book = api.book(trade["asset"])
                bid = simulate.best_bid(book) or trade["price"]
                simulate.close_at(store, f, bid, int(time.time()), "trader_exit", fee_bps)

    text = telegram.format_alert(wallet_row, trade, _sim_lines(new_fills))
    if store.record_alert(trade["wallet"], trade["id"], not dry_run, text):
        token = "" if dry_run else cfg.telegram_token
        telegram.send(token, cfg.telegram_chat_id, text)


def poll_once(store: Store, api: PolymarketAPI, cfg: Config, dry_run: bool = False) -> int:
    n_new = 0
    for w in store.wallets(qualified_only=True):
        try:
            raw = api.trades(user=w["address"], limit=100)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] poll {w['address'][:10]}: {e}")
            continue
        fresh = store.insert_trades([t for t in raw if int(t["timestamp"]) > w["last_trade_ts"]])
        if not fresh:
            if raw:
                store.set_last_trade_ts(w["address"], max(int(t["timestamp"]) for t in raw))
            continue
        sync_markets(store, api, [t["condition_id"] for t in fresh])
        for t in sorted(fresh, key=lambda x: x["ts"]):
            process_new_trade(store, api, cfg, w, t, dry_run)
            n_new += 1
        store.set_last_trade_ts(w["address"], max(t["ts"] for t in fresh))
    return n_new


def watch(store: Store, api: PolymarketAPI, cfg: Config, once: bool = False,
          dry_run: bool = False, baseline: bool = True):
    wallets = store.wallets(qualified_only=True)
    if not wallets:
        print("No qualified wallets. Run: polycopy discover  (or polycopy scan <addr>)")
        return
    if baseline:
        # first pass: checkpoint to 'now' so we only alert on genuinely new trades
        for w in wallets:
            if not w["last_trade_ts"]:
                store.set_last_trade_ts(w["address"], int(time.time()))
        print(f"Watching {len(wallets)} qualified wallets (poll every {cfg.poll_sec}s, "
              f"{'DRY RUN' if dry_run else 'telegram ' + ('ON' if cfg.telegram_token else 'unconfigured -> stdout')})")
    cycles = 0
    while True:
        try:
            n = poll_once(store, api, cfg, dry_run)
            cycles += 1
            if n:
                print(f"[{time.strftime('%H:%M:%S')}] {n} new trades processed")
            if cycles % 10 == 0:  # refresh resolutions + marks every ~10 polls
                sync_markets(store, api, store.unresolved_condition_ids())
                simulate.refresh_marks(store, api, cfg)
        except Exception as e:  # noqa: BLE001 — one bad market must not end the watch
            print(f"[{time.strftime('%H:%M:%S')}] [warn] cycle failed: {type(e).__name__}: {e}")
            if once:
                raise
        if once:
            break
        time.sleep(cfg.poll_sec)
