import json
import unittest

from polycopy.manifold import market_to_gamma, norm_bet
from polycopy.store import Store


def bet(amount=50.0, shares=100.0, outcome="YES", redemption=False, ts=1786341980121):
    return {"betId": "b1", "userId": "u1", "contractId": "c1", "amount": amount,
            "shares": shares, "outcome": outcome, "isRedemption": redemption,
            "createdTime": ts, "probAfter": 0.5}


class TestManifold(unittest.TestCase):
    def test_norm_buy(self):
        t = norm_bet(bet(), "Q?", "slug")
        self.assertEqual(t["side"], "BUY")
        self.assertAlmostEqual(t["price"], 0.5)
        self.assertEqual(t["asset"], "c1:YES")
        self.assertEqual(t["outcomeIndex"], 0)
        self.assertEqual(t["timestamp"], 1786341980)

    def test_norm_sell_and_skips(self):
        t = norm_bet(bet(amount=-30, shares=-60), "Q?", "s")
        self.assertEqual(t["side"], "SELL")
        self.assertAlmostEqual(t["price"], 0.5)
        self.assertIsNone(norm_bet(bet(redemption=True), "Q?", "s"))
        self.assertIsNone(norm_bet(bet(shares=0), "Q?", "s"))
        self.assertIsNone(norm_bet({**bet(), "outcome": "MKT"}, "Q?", "s"))

    def test_market_resolutions(self):
        base = {"id": "c1", "outcomeType": "BINARY", "question": "Q?", "slug": "q",
                "closeTime": 1786341980121}
        yes = market_to_gamma({**base, "isResolved": True, "resolution": "YES"})
        self.assertEqual(json.loads(yes["outcomePrices"]), ["1.0", "0.0"])
        self.assertEqual(yes["umaResolutionStatus"], "resolved")
        mkt = market_to_gamma({**base, "isResolved": True, "resolution": "MKT",
                               "resolutionProbability": 0.3})
        self.assertEqual(json.loads(mkt["outcomePrices"]), ["0.3", "0.7"])
        open_ = market_to_gamma({**base, "isResolved": False, "probability": 0.62})
        self.assertEqual(open_["umaResolutionStatus"], "")
        self.assertIsNone(market_to_gamma({**base, "outcomeType": "MULTIPLE_CHOICE"}))

    def test_roundtrip_into_store_metrics(self):
        from polycopy.metrics import market_pnls, wallet_stats
        store = Store(":memory:")
        store.upsert_market(market_to_gamma(
            {"id": "c1", "outcomeType": "BINARY", "question": "Will X invade?",
             "slug": "x", "isResolved": True, "resolution": "YES",
             "closeTime": 1786341980121}), "geopolitics")
        rows = [norm_bet(bet(), "Will X invade?", "x")]
        store.insert_trades(rows)
        mp = market_pnls(store.wallet_trades("u1"), store.resolutions())[0]
        self.assertTrue(mp.resolved)
        self.assertAlmostEqual(mp.pnl, 50.0)  # 100 sh @0.5 cost 50 -> payout 100
        self.assertEqual(wallet_stats([mp])["wins"], 1)


if __name__ == "__main__":
    unittest.main()
