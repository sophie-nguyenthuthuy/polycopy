import unittest

from polycopy.classify import categorize, classify
from polycopy.config import Config
from polycopy.metrics import MarketPnl, wallet_stats


def mk(cid, title, pnl, resolved=True, invested=500.0, entries=(0.4,), n=2,
       both=False, hours=24.0):
    return MarketPnl(condition_id=cid, title=title, resolved=resolved, pnl=pnl,
                     invested=invested, n_trades=n, both_sides=both,
                     entry_prices=list(entries), first_ts=0, last_ts=0,
                     hours_to_close=hours if resolved else None)


class TestClassify(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_categorize(self):
        self.assertEqual(categorize("Will Russia and Ukraine reach a ceasefire?"), "geopolitics")
        self.assertEqual(categorize("Will Trump win the nomination?"), "politics")
        self.assertEqual(categorize("Bitcoin Up or Down 8PM"), "sports_crypto")

    def test_insider_suspect(self):
        mpnls = [mk(f"c{i}", "Will Israel strike Iran?", pnl=200) for i in range(6)]
        stats = wallet_stats(mpnls)
        label, score, reasons = classify(stats, mpnls, self.cfg)
        self.assertEqual(label, "INSIDER_SUSPECT")
        self.assertGreaterEqual(score, self.cfg.insider_min_score)

    def test_perfect_but_not_insider_profile(self):
        # sports markets, tiny stakes, favorites at 0.95 -> perfect but not suspect
        mpnls = [mk(f"c{i}", "Will Arsenal win the league cup?", pnl=5,
                    invested=20, entries=(0.95,), hours=500) for i in range(6)]
        stats = wallet_stats(mpnls)
        label, _, _ = classify(stats, mpnls, self.cfg)
        self.assertEqual(label, "PERFECT")

    def test_arb(self):
        mpnls = [mk(f"c{i}", "Any market", pnl=1, both=True) for i in range(6)]
        stats = wallet_stats(mpnls)
        self.assertEqual(classify(stats, mpnls, self.cfg)[0], "ARB")

    def test_scalper(self):
        mpnls = [mk(f"c{i}", "Bitcoin Up or Down", pnl=1, n=200) for i in range(6)]
        stats = wallet_stats(mpnls)
        self.assertEqual(classify(stats, mpnls, self.cfg)[0], "SCALPER")

    def test_not_enough_history(self):
        mpnls = [mk("c1", "Will X happen?", pnl=100)]
        stats = wallet_stats(mpnls)
        self.assertEqual(classify(stats, mpnls, self.cfg)[0], "NORMAL")

    def test_near_perfect(self):
        mpnls = [mk(f"c{i}", "Will Russia invade?", pnl=200) for i in range(9)]
        mpnls.append(mk("c9", "Will Russia invade?", pnl=-50))
        stats = wallet_stats(mpnls)
        label, _, _ = classify(stats, mpnls, self.cfg)
        self.assertEqual(label, "NEAR_PERFECT")


if __name__ == "__main__":
    unittest.main()
