import unittest

from polycopy import simulate
from polycopy.store import Store


def trade(wallet="0xw", asset="tokA", cid="c1", price=0.40, size=100.0, ts=1000):
    return dict(wallet=wallet, asset=asset, condition_id=cid, side="BUY",
                price=price, size=size, usd=price * size, ts=ts,
                outcome="Yes", title="Test market")


class TestSimulate(unittest.TestCase):
    def test_walk_book_single_level(self):
        qty, avg = simulate.walk_book([{"price": "0.50", "size": "1000"}], 100, "BUY")
        self.assertAlmostEqual(qty, 200.0)
        self.assertAlmostEqual(avg, 0.50)

    def test_walk_book_multi_level_price_impact(self):
        asks = [{"price": "0.60", "size": "50"}, {"price": "0.50", "size": "100"}]
        qty, avg = simulate.walk_book(asks, 80, "BUY")  # $50 @0.5 then $30 @0.6
        self.assertAlmostEqual(qty, 100 + 50)
        self.assertAlmostEqual(avg, 80 / 150)

    def test_fee_formula(self):
        # 1000 bps on min(p,1-p): 0.1 * min(0.9,0.1) * 100 shares = $1
        self.assertAlmostEqual(simulate.fee_usd(1000, 0.9, 100), 1.0)
        self.assertAlmostEqual(simulate.fee_usd(0, 0.5, 100), 0.0)

    def test_open_and_close_fill(self):
        store = Store(":memory:")
        book = {"asks": [{"price": "0.50", "size": "1000"}]}
        f = simulate.open_copy_fill(store, "s10", "live", trade(), 10.0, book,
                                    fee_bps=0, slippage_bps=0)
        self.assertIsNotNone(f)
        self.assertAlmostEqual(f["entry_price"], 0.50)
        self.assertAlmostEqual(f["qty"], 20.0)
        # duplicate (same strategy/wallet/asset) is ignored
        self.assertIsNone(simulate.open_copy_fill(store, "s10", "live", trade(), 10.0,
                                                  book, 0, 0))
        opened = store.open_fills("live")[0]
        simulate.close_at(store, opened, 1.0, 2000, "resolution")
        closed = store.fills("live")[0]
        self.assertEqual(closed["status"], "closed")
        self.assertAlmostEqual(closed["pnl"], 20.0 * 1.0 - 10.0)

    def test_slippage_applied(self):
        store = Store(":memory:")
        book = {"asks": [{"price": "0.50", "size": "1000"}]}
        f = simulate.open_copy_fill(store, "s10", "live", trade(), 10.0, book,
                                    fee_bps=0, slippage_bps=100)
        self.assertAlmostEqual(f["entry_price"], 0.505)

    def test_fallback_price_when_no_book(self):
        store = Store(":memory:")
        f = simulate.open_copy_fill(store, "s10", "backtest", trade(price=0.40), 10.0,
                                    book=None, fee_bps=0, slippage_bps=0,
                                    fallback_price=0.406)
        self.assertAlmostEqual(f["entry_price"], 0.406)

    def test_report_totals(self):
        store = Store(":memory:")
        book = {"asks": [{"price": "0.50", "size": "1000"}]}
        f = simulate.open_copy_fill(store, "s10", "live", trade(), 10.0, book, 0, 0)
        simulate.close_at(store, store.open_fills("live")[0], 1.0, 2000, "resolution")
        rep = simulate.report(store, "live")
        self.assertIn("s10", rep)
        self.assertIn("$+10.00", rep.replace(",", ""))


if __name__ == "__main__":
    unittest.main()
