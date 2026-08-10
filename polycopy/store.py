"""SQLite persistence + checkpoints. Single file DB, safe to re-run any command."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS markets (
  condition_id TEXT PRIMARY KEY, question TEXT, slug TEXT, event_slug TEXT,
  category TEXT, end_date TEXT, closed INTEGER, closed_time TEXT,
  neg_risk INTEGER, outcomes TEXT, outcome_prices TEXT, clob_token_ids TEXT,
  taker_fee_bps INTEGER DEFAULT 0, resolved INTEGER DEFAULT 0, updated_at INTEGER
);
CREATE TABLE IF NOT EXISTS trades (
  id TEXT PRIMARY KEY, wallet TEXT, condition_id TEXT, asset TEXT,
  side TEXT, price REAL, size REAL, usd REAL, ts INTEGER,
  outcome TEXT, outcome_index INTEGER, title TEXT, event_slug TEXT, tx TEXT
);
CREATE INDEX IF NOT EXISTS idx_trades_wallet_ts ON trades (wallet, ts);
CREATE TABLE IF NOT EXISTS wallets (
  address TEXT PRIMARY KEY, name TEXT, pseudonym TEXT,
  trade_count INTEGER, resolved_n INTEGER, wins INTEGER, losses INTEGER,
  open_n INTEGER, realized_pnl REAL, win_rate REAL,
  label TEXT, score INTEGER, reasons TEXT, qualified INTEGER DEFAULT 0,
  last_scan INTEGER, last_trade_ts INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, wallet TEXT, trade_id TEXT UNIQUE,
  ts INTEGER, sent INTEGER, text TEXT
);
CREATE TABLE IF NOT EXISTS fills (
  id INTEGER PRIMARY KEY AUTOINCREMENT, strategy TEXT, mode TEXT,
  wallet TEXT, condition_id TEXT, asset TEXT, outcome TEXT, title TEXT,
  qty REAL, entry_price REAL, notional REAL, fee_usd REAL, entry_ts INTEGER,
  status TEXT DEFAULT 'open', exit_price REAL, exit_ts INTEGER, exit_reason TEXT,
  mark_price REAL, mark_ts INTEGER, pnl REAL,
  UNIQUE (strategy, mode, wallet, asset)
);
"""


def trade_id(t: dict) -> str:
    key = f"{t.get('transactionHash','')}|{t['proxyWallet']}|{t['asset']}|{t['side']}|{t['price']}|{t['size']}|{t['timestamp']}"
    return hashlib.sha1(key.encode()).hexdigest()


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # -- meta ----------------------------------------------------------------
    def get_meta(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, str(value)))
        self.db.commit()

    # -- markets -------------------------------------------------------------
    def upsert_market(self, m: dict, category: str):
        prices = m.get("outcomePrices") or "[]"
        resolved = 1 if (m.get("closed") and m.get("umaResolutionStatus") == "resolved") else 0
        self.db.execute(
            """INSERT OR REPLACE INTO markets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (m["conditionId"], m.get("question"), m.get("slug"),
             (m.get("events") or [{}])[0].get("slug", ""), category,
             m.get("endDate"), 1 if m.get("closed") else 0, m.get("closedTime"),
             1 if m.get("negRisk") else 0, m.get("outcomes"), prices,
             m.get("clobTokenIds"), int(m.get("takerBaseFee") or 0), resolved,
             int(time.time())))
        self.db.commit()

    def market(self, condition_id: str):
        return self.db.execute("SELECT * FROM markets WHERE condition_id=?", (condition_id,)).fetchone()

    def missing_condition_ids(self, condition_ids: list[str]) -> list[str]:
        known = {r["condition_id"] for r in self.db.execute("SELECT condition_id FROM markets")}
        return [c for c in dict.fromkeys(condition_ids) if c not in known]

    def unresolved_condition_ids(self) -> list[str]:
        return [r["condition_id"] for r in self.db.execute("SELECT condition_id FROM markets WHERE resolved=0")]

    def resolutions(self) -> dict:
        """condition_id -> list of final outcome prices (only resolved markets)."""
        out = {}
        for r in self.db.execute("SELECT condition_id, outcome_prices FROM markets WHERE resolved=1"):
            try:
                out[r["condition_id"]] = [float(x) for x in json.loads(r["outcome_prices"])]
            except (ValueError, TypeError):
                pass
        return out

    # -- trades --------------------------------------------------------------
    def insert_trades(self, raw_trades: list[dict]) -> list[dict]:
        """Insert, return only the previously-unseen rows (as normalized dicts)."""
        new = []
        for t in raw_trades:
            tid = trade_id(t)
            row = dict(
                id=tid, wallet=t["proxyWallet"], condition_id=t["conditionId"],
                asset=t["asset"], side=t["side"], price=float(t["price"]),
                size=float(t["size"]), usd=float(t["price"]) * float(t["size"]),
                ts=int(t["timestamp"]), outcome=t.get("outcome"),
                outcome_index=t.get("outcomeIndex"), title=t.get("title"),
                event_slug=t.get("eventSlug"), tx=t.get("transactionHash"))
            cur = self.db.execute(
                "INSERT OR IGNORE INTO trades VALUES (:id,:wallet,:condition_id,:asset,:side,"
                ":price,:size,:usd,:ts,:outcome,:outcome_index,:title,:event_slug,:tx)", row)
            if cur.rowcount:
                new.append(row)
        self.db.commit()
        return new

    def wallet_trades(self, address: str) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM trades WHERE wallet=? ORDER BY ts", (address,))]

    # -- wallets -------------------------------------------------------------
    def upsert_wallet_stats(self, address: str, name: str, pseudonym: str, stats: dict,
                            label: str, score: int, reasons: list[str], qualified: bool):
        prev = self.db.execute("SELECT last_trade_ts FROM wallets WHERE address=?", (address,)).fetchone()
        last_ts = prev["last_trade_ts"] if prev else 0
        self.db.execute(
            "INSERT OR REPLACE INTO wallets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (address, name, pseudonym, stats["trade_count"], stats["resolved_n"],
             stats["wins"], stats["losses"], stats["open_n"], stats["realized_pnl"],
             stats["win_rate"], label, score, json.dumps(reasons), 1 if qualified else 0,
             int(time.time()), last_ts))
        self.db.commit()

    def wallets(self, qualified_only: bool = False) -> list[dict]:
        q = "SELECT * FROM wallets" + (" WHERE qualified=1" if qualified_only else "") + " ORDER BY score DESC, win_rate DESC"
        return [dict(r) for r in self.db.execute(q)]

    def set_last_trade_ts(self, address: str, ts: int):
        self.db.execute("UPDATE wallets SET last_trade_ts=? WHERE address=?", (ts, address))
        self.db.commit()

    # -- alerts / fills ------------------------------------------------------
    def record_alert(self, wallet: str, trade_id_: str, sent: bool, text: str) -> bool:
        cur = self.db.execute(
            "INSERT OR IGNORE INTO alerts (wallet, trade_id, ts, sent, text) VALUES (?,?,?,?,?)",
            (wallet, trade_id_, int(time.time()), 1 if sent else 0, text))
        self.db.commit()
        return bool(cur.rowcount)

    def insert_fill(self, **kw) -> bool:
        cols = ("strategy", "mode", "wallet", "condition_id", "asset", "outcome", "title",
                "qty", "entry_price", "notional", "fee_usd", "entry_ts")
        cur = self.db.execute(
            f"INSERT OR IGNORE INTO fills ({','.join(cols)}) VALUES ({','.join(':'+c for c in cols)})",
            {c: kw[c] for c in cols})
        self.db.commit()
        return bool(cur.rowcount)

    def open_fills(self, mode: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM fills WHERE status='open'", []
        if mode:
            q += " AND mode=?"
            args.append(mode)
        return [dict(r) for r in self.db.execute(q, args)]

    def close_fill(self, fill_id: int, exit_price: float, exit_ts: int, reason: str, pnl: float):
        self.db.execute(
            "UPDATE fills SET status='closed', exit_price=?, exit_ts=?, exit_reason=?, pnl=? WHERE id=?",
            (exit_price, exit_ts, reason, pnl, fill_id))
        self.db.commit()

    def mark_fill(self, fill_id: int, mark_price: float):
        self.db.execute("UPDATE fills SET mark_price=?, mark_ts=? WHERE id=?",
                        (mark_price, int(time.time()), fill_id))
        self.db.commit()

    def fills(self, mode: str) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM fills WHERE mode=?", (mode,))]

    def clear_fills(self, mode: str):
        self.db.execute("DELETE FROM fills WHERE mode=?", (mode,))
        self.db.commit()
