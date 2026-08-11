"""Manifold Markets (play-money) port — same pipeline, legal everywhere, free.

Bets/markets are normalized into the exact shapes the Polymarket pipeline
stores, so Store, metrics, classify, simulate and backtest work unchanged:
  wallet        = Manifold userId
  condition_id  = contractId          asset = contractId + ":YES"/":NO"
  price         = |amount| / |shares| (actual avg fill price in prob space)
  resolutions   = YES -> [1,0], NO -> [0,1], MKT -> [p, 1-p]

Optional real play-money execution (POST /v0/bet) with MANIFOLD_API_KEY —
mana only, no monetary value.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from . import simulate, telegram
from .classify import categorize
from .config import Config
from .simulate import STRATEGIES
from .store import Store

BASE = "https://api.manifold.markets/v0"
_UA = "polycopy-manifold/0.1 (research)"


class ManifoldAPI:
    def __init__(self, rate_limit_sec: float = 0.15, timeout: float = 20.0, api_key: str = ""):
        self.rate_limit_sec = rate_limit_sec
        self.timeout = timeout
        self.api_key = api_key
        self._last = 0.0

    def _req(self, path: str, params: dict | None = None, body: dict | None = None, tries: int = 4):
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        headers = {"User-Agent": _UA, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
            if self.api_key:
                headers["Authorization"] = f"Key {self.api_key}"
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(tries):
            wait = self.rate_limit_sec - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            try:
                req = urllib.request.Request(url, data=data, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < tries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError):
                if attempt < tries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

    def bets(self, user_id: str | None = None, limit: int = 1000, before: str | None = None) -> list[dict]:
        params: dict = {"limit": limit}
        if user_id:
            params["userId"] = user_id
        if before:
            params["before"] = before
        return self._req("/bets", params) or []

    def user_bets_all(self, user_id: str, max_n: int = 2000) -> list[dict]:
        out: list[dict] = []
        before = None
        while len(out) < max_n:
            batch = self.bets(user_id=user_id, limit=min(1000, max_n - len(out)), before=before)
            out.extend(batch)
            if len(batch) < 1000:
                break
            before = batch[-1]["betId"]
        return out

    def market(self, contract_id: str) -> dict:
        return self._req(f"/market/{contract_id}") or {}

    def user_by_id(self, user_id: str) -> dict:
        return self._req(f"/user/by-id/{user_id}") or {}

    def user_by_name(self, username: str) -> dict:
        return self._req(f"/user/{username}") or {}

    # play-money execution (requires api_key)
    def place_bet(self, contract_id: str, outcome: str, amount: float) -> dict:
        return self._req("/bet", body={"contractId": contract_id, "outcome": outcome,
                                       "amount": round(amount)})


# -- normalization -----------------------------------------------------------

def norm_bet(b: dict, question: str, slug: str) -> dict | None:
    """Manifold bet -> data-api-shaped raw trade (store.insert_trades format)."""
    shares, amount = b.get("shares") or 0.0, b.get("amount") or 0.0
    if b.get("isRedemption") or abs(shares) < 1e-9 or abs(amount) < 1e-9:
        return None
    if b.get("outcome") not in ("YES", "NO"):
        return None  # binary markets only in the MVP
    price = min(0.999, max(0.001, abs(amount) / abs(shares)))
    return {
        "proxyWallet": b["userId"], "conditionId": b["contractId"],
        "asset": f'{b["contractId"]}:{b["outcome"]}',
        "side": "BUY" if amount > 0 else "SELL",
        "price": price, "size": abs(shares),
        "timestamp": int(b["createdTime"] // 1000),
        "outcome": b["outcome"], "outcomeIndex": 0 if b["outcome"] == "YES" else 1,
        "title": question, "eventSlug": slug, "transactionHash": b["betId"],
    }


def market_to_gamma(m: dict) -> dict | None:
    """Manifold market -> gamma-shaped dict for store.upsert_market."""
    if m.get("outcomeType") != "BINARY":
        return None
    cid = m["id"]
    resolved = bool(m.get("isResolved")) and m.get("resolution") in ("YES", "NO", "MKT")
    if resolved:
        if m["resolution"] == "YES":
            prices = [1.0, 0.0]
        elif m["resolution"] == "NO":
            prices = [0.0, 1.0]
        else:
            p = float(m.get("resolutionProbability") or 0.5)
            prices = [p, 1.0 - p]
    else:
        p = float(m.get("probability") or 0.5)
        prices = [p, 1.0 - p]
    # Manifold allows "never closes" markets with absurd closeTime (year 10000+),
    # which datetime cannot represent — treat those as no close date.
    close_iso = ""
    ts = m.get("resolutionTime") or m.get("closeTime")
    if ts:
        try:
            close_iso = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OverflowError, OSError):
            close_iso = ""
    return {
        "conditionId": cid, "question": m.get("question"), "slug": m.get("slug"),
        "closed": bool(m.get("isResolved")), "closedTime": close_iso, "endDate": close_iso,
        "negRisk": False, "outcomes": '["Yes", "No"]',
        "outcomePrices": json.dumps([str(p) for p in prices]),
        "clobTokenIds": json.dumps([f"{cid}:YES", f"{cid}:NO"]),
        "takerBaseFee": 0,
        "umaResolutionStatus": "resolved" if resolved else "",
        "events": [{"slug": m.get("url") or m.get("slug") or ""}],
    }


# -- pipeline ----------------------------------------------------------------

def sync_market(store: Store, api: ManifoldAPI, contract_id: str, force: bool = False):
    row = store.market(contract_id)
    if row and row["resolved"] and not force:
        return row
    g = market_to_gamma(api.market(contract_id))
    if g:
        store.upsert_market(g, categorize(g.get("question") or ""))
    return store.market(contract_id)


def scan_user(store: Store, api: ManifoldAPI, cfg: Config, user_id: str,
              verbose: bool = False) -> dict:
    from .classify import QUALIFIED_LABELS, classify
    from .discover import _close_ts
    from .metrics import market_pnls, wallet_stats

    raw = api.user_bets_all(user_id, cfg.max_trades_per_wallet)
    cache: dict[str, tuple] = {}
    rows = []
    for b in raw:
        cid = b.get("contractId")
        if not cid:
            continue
        if cid not in cache:
            r = sync_market(store, api, cid)
            cache[cid] = (r["question"], r["event_slug"]) if r else ("", "")
        nb = norm_bet(b, *cache[cid])
        if nb:
            rows.append(nb)
    store.insert_trades(rows)

    trades = store.wallet_trades(user_id)
    close_times = {}
    for cid in {t["condition_id"] for t in trades}:
        row = store.market(cid)
        ts = _close_ts(row) if row else None
        if ts:
            close_times[cid] = ts
    mpnls = market_pnls(trades, store.resolutions(), close_times)
    stats = wallet_stats(mpnls, cfg.pnl_epsilon)
    label, score, reasons = classify(stats, mpnls, cfg)
    qualified = label in QUALIFIED_LABELS
    u = api.user_by_id(user_id)
    store.upsert_wallet_stats(user_id, u.get("username", ""), u.get("name", ""),
                              stats, label, score, reasons, qualified)
    result = dict(address=user_id, name=u.get("username", ""), label=label, score=score,
                  reasons=reasons, qualified=qualified, **stats)
    if verbose:
        print(f"\n{u.get('username')} ({user_id})")
        print(f"  label={label} score={score} qualified={qualified}")
        print(f"  {stats['wins']}W/{stats['losses']}L over {stats['resolved_n']} resolved "
              f"({stats['win_rate']:.0%}), {stats['trade_count']} bets, "
              f"realized M${stats['realized_pnl']:+,.0f}")
        for r in reasons:
            print(f"  - {r}")
    return result


def discover(store: Store, api: ManifoldAPI, cfg: Config, pages: int = 3,
             min_mana: float = 100.0, limit: int | None = None) -> list[dict]:
    seen: dict[str, float] = {}
    before = None
    for _ in range(pages):
        batch = api.bets(limit=1000, before=before)
        if not batch:
            break
        for b in batch:
            if not b.get("isRedemption") and abs(b.get("amount") or 0) >= min_mana:
                seen[b["userId"]] = seen.get(b["userId"], 0) + abs(b["amount"])
        before = batch[-1]["betId"]
    seeds = [u for u, _ in sorted(seen.items(), key=lambda kv: -kv[1])]
    if limit:
        seeds = seeds[:limit]
    print(f"Scanning {len(seeds)} candidate users (from {pages}k recent bets, >=M${min_mana:.0f})...")
    results = []
    for i, uid in enumerate(seeds, 1):
        try:
            r = scan_user(store, api, cfg, uid)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] scan {uid}: {e}")
            continue
        flag = " ***" if r["qualified"] else ""
        print(f"[{i}/{len(seeds)}] {r['name'] or uid[:10]:<20} {r['label']:<15} "
              f"{r['wins']}W/{r['losses']}L wr={r['win_rate']:.0%} bets={r['trade_count']}{flag}")
        results.append(r)
    return results


def _entry_price(market_row, outcome: str, slippage_bps: int) -> float | None:
    try:
        prices = [float(x) for x in json.loads(market_row["outcome_prices"])]
    except (ValueError, TypeError):
        return None
    p = prices[0] if outcome == "YES" else prices[1]
    return min(0.999, max(0.001, p * (1 + slippage_bps / 10_000)))


def poll_once(store: Store, api: ManifoldAPI, cfg: Config, dry_run: bool = False,
              execute: bool = False) -> int:
    n_new = 0
    for w in store.wallets(qualified_only=True):
        try:
            raw = api.bets(user_id=w["address"], limit=100)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] poll {w['name'] or w['address'][:10]}: {e}")
            continue
        fresh_raw = [b for b in raw if int(b["createdTime"] // 1000) > w["last_trade_ts"]]
        rows = []
        for b in fresh_raw:
            cid = b.get("contractId")
            if not cid:
                continue
            m = sync_market(store, api, cid, force=True)
            nb = norm_bet(b, m["question"] if m else "", m["event_slug"] if m else "")
            if nb:
                rows.append(nb)
        fresh = store.insert_trades(rows)
        if not fresh:
            if raw:
                store.set_last_trade_ts(w["address"], max(int(b["createdTime"] // 1000) for b in raw))
            continue
        for t in sorted(fresh, key=lambda x: x["ts"]):
            _process(store, api, cfg, w, t, dry_run, execute)
            n_new += 1
        store.set_last_trade_ts(w["address"], max(t["ts"] for t in fresh))
    return n_new


def _process(store: Store, api: ManifoldAPI, cfg: Config, w: dict, t: dict,
             dry_run: bool, execute: bool):
    market = store.market(t["condition_id"])
    new_fills, exec_lines = [], []
    if t["side"] == "BUY" and t["price"] <= cfg.max_entry_price and market:
        entry = _entry_price(market, t["outcome"], cfg.slippage_extra_bps)
        if entry:
            for strat, usd, labels in STRATEGIES:
                if w["label"] in labels:
                    f = simulate.open_copy_fill(store, strat, "live", t, usd, book=None,
                                                fee_bps=0, slippage_bps=0,
                                                fallback_price=entry, entry_ts=int(time.time()))
                    if f:
                        new_fills.append(f)
            if execute and api.api_key and new_fills:
                try:
                    r = api.place_bet(t["condition_id"], t["outcome"], new_fills[0]["notional"])
                    exec_lines.append(f"EXECUTED play-money: M${new_fills[0]['notional']:.0f} "
                                      f"{t['outcome']} (bet {r.get('betId', '?')})")
                except Exception as e:  # noqa: BLE001
                    exec_lines.append(f"execute failed: {e}")
    elif t["side"] == "SELL":
        for f in store.open_fills(mode="live"):
            if f["wallet"] == t["wallet"] and f["asset"] == t["asset"] and market:
                px = _entry_price(market, t["outcome"], 0) or t["price"]
                simulate.close_at(store, f, px, int(time.time()), "trader_exit")

    sims = [f"sim {f['strategy']}: {f['qty']:.1f} sh @ {f['entry_price']:.3f} (M${f['notional']:.0f})"
            for f in new_fills] + exec_lines
    text = "[manifold] " + telegram.format_alert(w, t, sims)
    if store.record_alert(t["wallet"], t["id"], not dry_run, text):
        telegram.send("" if dry_run else cfg.telegram_token, cfg.telegram_chat_id, text)


def refresh_marks(store: Store, api: ManifoldAPI):
    for f in store.open_fills(mode="live"):
        m = sync_market(store, api, f["condition_id"], force=True)
        if not m:
            continue
        try:
            prices = [float(x) for x in json.loads(m["outcome_prices"])]
        except (ValueError, TypeError):
            continue
        idx = 0 if f["asset"].endswith(":YES") else 1
        if m["resolved"]:
            simulate.close_at(store, f, prices[idx], int(time.time()), "resolution")
        else:
            store.mark_fill(f["id"], prices[idx])


def watch(store: Store, api: ManifoldAPI, cfg: Config, once: bool = False,
          dry_run: bool = False, execute: bool = False):
    wallets = store.wallets(qualified_only=True)
    if not wallets:
        print("No qualified users. Run: polycopy mf-discover")
        return
    for w in wallets:
        if not w["last_trade_ts"]:
            store.set_last_trade_ts(w["address"], int(time.time()))
    print(f"Watching {len(wallets)} qualified Manifold users (poll {cfg.poll_sec}s"
          f"{', EXECUTE play-money ON' if execute and api.api_key else ''})")
    cycles = 0
    while True:
        try:
            n = poll_once(store, api, cfg, dry_run, execute)
            cycles += 1
            if n:
                print(f"[{time.strftime('%H:%M:%S')}] {n} new bets processed")
            if cycles % 10 == 0:
                refresh_marks(store, api)
        except Exception as e:  # noqa: BLE001 — one bad market must not end the watch
            print(f"[{time.strftime('%H:%M:%S')}] [warn] cycle failed: {type(e).__name__}: {e}")
            if once:
                raise
        if once:
            break
        time.sleep(cfg.poll_sec)
