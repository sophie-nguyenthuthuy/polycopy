import unittest

from polycopy.metrics import market_pnls, wallet_stats


def tr(cid, asset, side, price, size, ts=1000, idx=0, title="t"):
    return dict(condition_id=cid, asset=asset, side=side, price=price, size=size,
                usd=price * size, ts=ts, outcome_index=idx, title=title)


class TestMetrics(unittest.TestCase):
    def test_win_on_resolution(self):
        trades = [tr("c1", "a1", "BUY", 0.4, 100, idx=0)]
        mp = market_pnls(trades, {"c1": [1.0, 0.0]})[0]
        self.assertTrue(mp.resolved)
        self.assertAlmostEqual(mp.pnl, 60.0)  # -40 cost + 100 payout

    def test_loss_on_resolution(self):
        trades = [tr("c1", "a2", "BUY", 0.3, 100, idx=1)]
        mp = market_pnls(trades, {"c1": [1.0, 0.0]})[0]
        self.assertAlmostEqual(mp.pnl, -30.0)

    def test_partial_sell_plus_resolution(self):
        trades = [tr("c1", "a1", "BUY", 0.4, 100, ts=1000),
                  tr("c1", "a1", "SELL", 0.6, 50, ts=2000)]
        mp = market_pnls(trades, {"c1": [1.0, 0.0]})[0]
        self.assertAlmostEqual(mp.pnl, -40 + 30 + 50)

    def test_unresolved_market_not_judged(self):
        trades = [tr("c1", "a1", "BUY", 0.4, 100)]
        mp = market_pnls(trades, {})[0]
        self.assertFalse(mp.resolved)
        stats = wallet_stats([mp])
        self.assertEqual(stats["resolved_n"], 0)
        self.assertEqual(stats["open_n"], 1)

    def test_both_sides_flag(self):
        trades = [tr("c1", "a1", "BUY", 0.4, 10, idx=0),
                  tr("c1", "a2", "BUY", 0.55, 10, idx=1)]
        mp = market_pnls(trades, {})[0]
        self.assertTrue(mp.both_sides)

    def test_stats_win_rate(self):
        trades = [tr("c1", "a1", "BUY", 0.4, 100, idx=0),
                  tr("c2", "b1", "BUY", 0.3, 100, idx=1)]
        mps = market_pnls(trades, {"c1": [1.0, 0.0], "c2": [1.0, 0.0]})
        stats = wallet_stats(mps)
        self.assertEqual((stats["wins"], stats["losses"]), (1, 1))
        self.assertAlmostEqual(stats["win_rate"], 0.5)
        self.assertAlmostEqual(stats["realized_pnl"], 60 - 30)

    def test_hours_to_close(self):
        trades = [tr("c1", "a1", "BUY", 0.4, 100, ts=1000)]
        mp = market_pnls(trades, {"c1": [1.0, 0.0]}, {"c1": 1000 + 7200})[0]
        self.assertAlmostEqual(mp.hours_to_close, 2.0)


if __name__ == "__main__":
    unittest.main()
