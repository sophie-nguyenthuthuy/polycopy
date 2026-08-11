import csv
import json
import os
import tempfile
import unittest

from polycopy.export import export_csv
from polycopy.store import Store


def raw_trade(wallet="0xw", cid="c1", asset="a1", side="BUY", price=0.4, size=100, ts=1000):
    return {"proxyWallet": wallet, "conditionId": cid, "asset": asset, "side": side,
            "price": price, "size": size, "timestamp": ts, "outcome": "Yes",
            "outcomeIndex": 0, "title": "Will the ceasefire hold?", "eventSlug": "ev",
            "transactionHash": "0xabc"}


class TestExport(unittest.TestCase):
    def _store(self):
        store = Store(":memory:")
        stats = dict(trade_count=10, resolved_n=6, wins=6, losses=0, open_n=0,
                     realized_pnl=500, win_rate=1.0)
        store.upsert_wallet_stats("0xw", "ins", "", stats, "INSIDER_SUSPECT", 7,
                                  ["perfect record: 6W/0L", "low activity"], True)
        store.upsert_wallet_stats("0xq", "other", "", stats, "SCALPER", 0, [], False)
        store.insert_trades([raw_trade()])
        store.insert_fill(strategy="s10", mode="live", wallet="0xw", condition_id="c1",
                          asset="a1", outcome="Yes", title="T", qty=25.0, entry_price=0.4,
                          notional=10.0, fee_usd=0.0, entry_ts=1000)
        return store

    def test_export_writes_expected_rows(self):
        store = self._store()
        with tempfile.TemporaryDirectory() as d:
            counts = export_csv(store, d)
            self.assertEqual(counts["wallets.csv"], 2)
            self.assertEqual(counts["fills.csv"], 1)
            self.assertEqual(counts["qualified_trades.csv"], 1)

            with open(os.path.join(d, "wallets.csv")) as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["address"], "0xw")           # sorted by score desc
            self.assertEqual(rows[0]["label"], "INSIDER_SUSPECT")
            self.assertIn("perfect record", rows[0]["reasons"])   # json -> readable text

            with open(os.path.join(d, "fills.csv")) as f:
                fills = list(csv.DictReader(f))
            self.assertEqual(fills[0]["strategy"], "s10")
            self.assertEqual(fills[0]["status"], "open")

            # only qualified wallets' trades are exported
            with open(os.path.join(d, "qualified_trades.csv")) as f:
                tr = list(csv.DictReader(f))
            self.assertTrue(all(t["wallet"] == "0xw" for t in tr))

    def test_export_empty_store(self):
        store = Store(":memory:")
        with tempfile.TemporaryDirectory() as d:
            counts = export_csv(store, d)
            self.assertEqual(counts["fills.csv"], 0)
            self.assertTrue(os.path.exists(os.path.join(d, "qualified_trades.csv")))

    def test_db_is_not_committed_but_data_dir_is(self):
        """Regression: unanchored 'polycopy.db' in .gitignore also matched
        data/polycopy.db, so CI never persisted state."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, ".gitignore")) as f:
            patterns = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        self.assertNotIn("polycopy.db", patterns, "unanchored pattern matches data/ too")
        self.assertIn("/polycopy.db", patterns)


if __name__ == "__main__":
    unittest.main()
