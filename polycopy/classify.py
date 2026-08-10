"""Trader classification heuristics.

Labels:
  ARB             — systematically holds both sides of markets (risk-free legs)
  SCALPER         — high-frequency; win rate is a market-making artifact
  INSIDER_SUSPECT — perfect record + low activity + concentrated in
                    geopolitics/war/politics + meaningful stakes (the cohort
                    the user wants to copy)
  PERFECT         — 100% record, but doesn't fit the insider profile
  NEAR_PERFECT    — win rate >= threshold with >= min resolved markets
  NORMAL          — everyone else
"""
from __future__ import annotations

from .config import Config
from .metrics import MarketPnl

GEO_KEYWORDS = (
    "war", "ceasefire", "truce", "ukraine", "russia", "putin", "zelensky",
    "nato", "israel", "iran", "gaza", "hamas", "hezbollah", "missile", "strike",
    "nuclear", "invade", "invasion", "sanction", "north korea", "taiwan",
    "syria", "houthi", "peace deal", "hostage", "military", "troops",
)
POLITICS_KEYWORDS = (
    "trump", "election", "president", "nominee", "impeach", "congress", "senate",
    "supreme court", "cabinet", "resign", "prime minister", "chancellor", "coup",
    "tariff", "executive order", "fed ", "powell",
)
SPORTS_CRYPTO_KEYWORDS = (
    "bitcoin", "ethereum", "up or down", "price of", " vs ", "vs.", "win the",
    "league", "cup", "nba", "nfl", "mlb", "ufc", "f1", "premier", "champion",
)


def categorize(title: str) -> str:
    t = (title or "").lower()
    if any(k in t for k in GEO_KEYWORDS):
        return "geopolitics"
    if any(k in t for k in POLITICS_KEYWORDS):
        return "politics"
    if any(k in t for k in SPORTS_CRYPTO_KEYWORDS):
        return "sports_crypto"
    return "other"


def classify(stats: dict, mpnls: list[MarketPnl], cfg: Config) -> tuple[str, int, list[str]]:
    reasons: list[str] = []
    n_markets = len(mpnls) or 1
    geo_share = sum(1 for m in mpnls if categorize(m.title) in ("geopolitics", "politics")) / n_markets

    if stats["both_sides_share"] >= cfg.arb_both_sides_share:
        return "ARB", 0, [f"holds both sides in {stats['both_sides_share']:.0%} of markets"]
    if stats["trade_count"] >= cfg.scalper_min_trades:
        return "SCALPER", 0, [f"{stats['trade_count']} trades — market-maker/scalper profile"]
    if stats["resolved_n"] < cfg.min_resolved_markets:
        return "NORMAL", 0, [f"only {stats['resolved_n']} resolved markets — not enough history"]

    perfect = stats["losses"] == 0 and stats["wins"] >= cfg.min_resolved_markets
    score = 0
    if perfect:
        score += 2
        reasons.append(f"perfect record: {stats['wins']}W/0L")
    elif stats["win_rate"] >= cfg.near_perfect_win_rate:
        score += 1
        reasons.append(f"near-perfect: {stats['win_rate']:.0%} over {stats['resolved_n']} resolved")
    if stats["trade_count"] <= cfg.insider_max_trades:
        score += 1
        reasons.append(f"low activity ({stats['trade_count']} trades)")
    if stats["avg_stake"] >= cfg.insider_min_avg_stake:
        score += 1
        reasons.append(f"meaningful stakes (avg ${stats['avg_stake']:,.0f}/market)")
    if stats["median_entry_price"] <= cfg.insider_max_entry_price:
        score += 1
        reasons.append(f"buys uncertainty (median entry {stats['median_entry_price']:.2f})")
    if geo_share >= cfg.insider_geo_share:
        score += 1
        reasons.append(f"geo/politics concentration {geo_share:.0%}")
    mh = stats.get("median_hours_to_close")
    if mh is not None and mh <= cfg.insider_late_entry_hours:
        score += 1
        reasons.append(f"late entries (median {mh:.0f}h before close)")

    if perfect and score >= cfg.insider_min_score:
        return "INSIDER_SUSPECT", score, reasons
    if perfect:
        return "PERFECT", score, reasons
    if stats["win_rate"] >= cfg.near_perfect_win_rate:
        return "NEAR_PERFECT", score, reasons
    return "NORMAL", score, reasons


QUALIFIED_LABELS = {"INSIDER_SUSPECT", "PERFECT", "NEAR_PERFECT"}
