"""CSV exports — the durable research record.

The SQLite DB is carried between CI runs by the Actions cache (committing a
binary that churns every 30 min would bloat the repo). Caches can be evicted,
so the analysis-relevant rows are exported here as text and committed: they
diff well, survive forever in git history, and are what the latency-survival
analysis actually reads.
"""
from __future__ import annotations

import csv
import json
import os

WALLET_COLS = ("address", "name", "label", "score", "qualified", "wins", "losses",
               "win_rate", "resolved_n", "open_n", "trade_count", "realized_pnl",
               "last_scan", "reasons")
FILL_COLS = ("id", "strategy", "mode", "wallet", "condition_id", "asset", "outcome",
             "title", "qty", "entry_price", "notional", "fee_usd", "entry_ts",
             "status", "exit_price", "exit_ts", "exit_reason", "mark_price", "pnl")


def export_csv(store, out_dir: str = "data") -> dict[str, int]:
    os.makedirs(out_dir, exist_ok=True)
    counts: dict[str, int] = {}

    rows = store.wallets()
    with open(os.path.join(out_dir, "wallets.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=WALLET_COLS, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: (-(x["score"] or 0), x["address"])):
            r = dict(r)
            r["reasons"] = "; ".join(json.loads(r.get("reasons") or "[]"))
            w.writerow(r)
    counts["wallets.csv"] = len(rows)

    fills = [dict(r) for r in store.db.execute("SELECT * FROM fills ORDER BY entry_ts, id")]
    with open(os.path.join(out_dir, "fills.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FILL_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(fills)
    counts["fills.csv"] = len(fills)

    # copied traders' own trades — needed to compare their entry vs ours (latency cost)
    trades = [dict(r) for r in store.db.execute(
        "SELECT t.* FROM trades t JOIN wallets w ON w.address = t.wallet "
        "WHERE w.qualified = 1 ORDER BY t.ts")]
    with open(os.path.join(out_dir, "qualified_trades.csv"), "w", newline="") as f:
        if trades:
            w = csv.DictWriter(f, fieldnames=list(trades[0].keys()), extrasaction="ignore")
            w.writeheader()
            w.writerows(trades)
        else:
            f.write("no qualified wallets yet\n")
    counts["qualified_trades.csv"] = len(trades)
    return counts
