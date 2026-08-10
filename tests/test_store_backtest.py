import json
import unittest

from polycopy import backtest
from polycopy.config import Config
from polycopy.store import Store, trade_id


def raw_trade(wallet, cid, asset, side, price, size, ts, idx=0, tx="0xabc"):
    return {"proxyWallet": wallet, "conditionId": cid, "asset": asset, "side": side,
            "price": price, "size": size, "timestamp": ts, "outcome": "Yes",
            "outcomeIndex": idx, "title": "Will the ceasefire hold?",
            "eventSlug": "ev", "transactionHash": tx}


def gamma_market(cid, assets, prices, closed=True):
    return {"conditionId": cid, "question": "Will the ceasefire hold?", "slug": "s",
            "endDate": "2026-08-01T00:00:00Z", "closed": closed,
            "closedTime": "2026-08-01 00:00:00+00", "negRisk": False,
            "outcomes": '["Yes", "No"]', "outcomePrices": json.dumps([str(p) for p in prices]),
            "clobTokenIds": json.dumps(assets), "takerBaseFee": 0,
            "umaResolutionStatus": "resolved" if closed else "",
            "events": [{"slug": "ev"}]}


class TestStoreAndBacktest(unittest.TestCase):
    def test_trade_dedupe(self):
        store = Store(":memory:")
        t = raw_trade("0xw", "c1", "a1", "BUY", 0.4, 100, 1000)
        self.assertEqual(len(store.insert_trades([t])), 1)
        self.assertEqual(len(store.insert_trades([t])), 0)
        self.assertNotEqual(trade_id(t), trade_id({**t, "timestamp": 1001}))

    def test_backtest_end_to_end(self):
        store = Store(":memory:")
        cfg = Config(backtest_adverse_bps=0)
        store.upsert_market(gamma_market("c1", ["a1", "a2"], [1.0, 0.0]), "geopolitics")
        store.insert_trades([raw_trade("0xw", "c1", "a1", "BUY", 0.40, 1000, 1000)])
        stats = dict(trade_count=10, resolved_n=6, wins=6, losses=0, open_n=0,
                     realized_pnl=5000, win_rate=1.0)
        store.upsert_wallet_stats("0xw", "ins", "", stats, "INSIDER_SUSPECT", 7, [], True)

        rep = backtest.run(store, cfg)
        fills = store.fills("backtest")
        # all 3 strategies copy an INSIDER_SUSPECT
        self.assertEqual({f["strategy"] for f in fills}, {"s10", "s100", "perfect100"})
        s10 = next(f for f in fills if f["strategy"] == "s10")
        self.assertEqual(s10["status"], "closed")
        self.assertEqual(s10["exit_reason"], "resolution")
        # $10 at 0.40 -> 25 shares -> $25 payout -> +$15
        self.assertAlmostEqual(s10["pnl"], 15.0, places=2)
        self.assertIn("s10", rep)

    def test_backtest_trader_exit(self):
        store = Store(":memory:")
        cfg = Config(backtest_adverse_bps=0)
        store.upsert_market(gamma_market("c1", ["a1", "a2"], [0.6, 0.4], closed=False), "geopolitics")
        store.insert_trades([
            raw_trade("0xw", "c1", "a1", "BUY", 0.40, 1000, 1000, tx="0x1"),
            raw_trade("0xw", "c1", "a1", "SELL", 0.80, 1000, 2000, tx="0x2"),
        ])
        stats = dict(trade_count=10, resolved_n=6, wins=6, losses=0, open_n=0,
                     realized_pnl=5000, win_rate=1.0)
        store.upsert_wallet_stats("0xw", "ins", "", stats, "INSIDER_SUSPECT", 7, [], True)
        backtest.run(store, cfg)
        s10 = next(f for f in store.fills("backtest") if f["strategy"] == "s10")
        self.assertEqual(s10["exit_reason"], "trader_exit")
        # $10 at 0.40 = 25 sh, exit 0.80 -> $20 -> +$10
        self.assertAlmostEqual(s10["pnl"], 10.0, places=2)


if __name__ == "__main__":
    unittest.main()
