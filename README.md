# polycopy

Polymarket perfect-trader copy-alert MVP: discover wallets with perfect/near-perfect
records, classify them (arb / scalper / **insider-suspect**), watch their new trades,
send Telegram alerts, and simulate copy-trading P&L ($10, $100, all-perfect-$100)
including fees, spread, order-book slippage, and mark-to-market.

**Simulation only.** This tool never places orders. Whether copying is actually
profitable depends heavily on detection latency — informed flow moves prices within
seconds — which is exactly what the live watch mode measures honestly (it fills you
at the *current* order book, not the insider's price).

Pure stdlib (Python 3.11+), single SQLite file, no dependencies.

## Quickstart

```bash
# 1. Find candidates (seeds from PnL leaderboards; add suspects you found manually)
python3 -m polycopy discover --limit 100 --addr 0xSUSPECT_WALLET

# 2. Inspect / rescan any wallet
python3 -m polycopy scan 0xWALLET
python3 -m polycopy wallets            # qualified only; --all for everything
python3 -m polycopy qualify 0xWALLET   # hand-pick a copy target (--off to remove)

# 3. Replay their stored history as if you had copied every entry
python3 -m polycopy backtest

# 4. Watch qualified wallets live (60s poll), alert + open sim fills
export TELEGRAM_BOT_TOKEN=...          # from @BotFather
export TELEGRAM_CHAT_ID=...            # your chat id
python3 -m polycopy watch              # --dry-run prints alerts instead
python3 -m polycopy report --refresh   # live + backtest P&L, marked to market
```

Tests: `python3 -m unittest discover -s tests`

## How it works

| Stage | Mechanics |
|---|---|
| Ingest | Data-API `/trades` (paginated, checkpointed in SQLite), Gamma `/markets` for resolutions, CLOB `/book` for depth. All idempotent upserts. |
| Win record | Per market: sell proceeds − buy cost + resolution payout of remaining shares. Win = resolved market with PnL > $0.01. |
| Classify | `ARB` (holds both sides ≥30% of markets), `SCALPER` (≥800 trades), `INSIDER_SUSPECT` (perfect record + score ≥5 from: low activity, avg stake ≥$200, median entry ≤0.75, geo/politics concentration ≥40%, entries ≤96h before close), `PERFECT`, `NEAR_PERFECT` (≥90%). |
| Watch | Polls each qualified wallet's `/trades` every 60s, dedupes vs stored ids, alerts via Telegram (stdout if unconfigured). |
| Copy sim | On their BUY: walk the live ask book with $10/$100, add 50bps adverse slippage, apply taker fees (`bps/10⁴ · min(p,1−p) · shares`; default 0 — Gamma's `takerBaseFee` field is a signed max, not the charged rate, opt in via `use_market_fee_field`). Exit when the trader sells (at best bid) or at resolution payout. Open fills marked at best bid. |
| Backtest | Replays stored history; entry = trader's price +150bps adverse (no historical books exist — be skeptical of backtest numbers, live watch numbers are the real experiment). |

Strategies: `s10` / `s100` copy INSIDER_SUSPECT wallets only; `perfect100` copies
every qualified wallet at $100.

## Honest limitations

- **Data-API trade pagination caps at ~1000 rows/wallet** — fine for the low-activity
  insider cohort we target; high-volume wallets get excluded as SCALPER anyway (their
  stats over a truncated window would be wrong).
- One sim fill per (strategy, wallet, token): re-entries after a full exit are not
  re-copied (keeps the ledger simple, avoids doubling into one market).
- Backtest entry prices are optimistic even with the adverse-bps penalty: after a big
  informed buy the book may be far thinner than +150bps. Treat the **live** watch
  results (real books at detection time) as the actual experiment.
- Win rate ≠ skill: survivorship, martingale sizing, and one-sided books can fake it.
  The classifier filters the obvious cases (arb, scalpers) but is heuristic.
- Discovery seeds from leaderboards, so a quiet insider who never hit a leaderboard
  window won't be found automatically — add suspects via `--addr` / `scan`.

## Free deployment: GitHub Actions collector

`.github/workflows/collect.yml` runs [ci_cycle.sh](ci_cycle.sh) every 30 min on
GitHub's runners (useful where local ISPs block the domain — runners sit in
regions with unrestricted access): first run does a full discovery seed, then each
cycle re-sweeps recent geo/politics fills, watch-passes qualified wallets, and
commits the research record back to the repo. Add repo secrets
`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` for phone alerts; without them alerts
land in the run log + REPORT history. Note scheduled runs give ~30–60 min
detection latency — the copy-sim prices at the book seen *at detection*, so
results honestly reflect what a free pipeline could capture.

State persistence matters more than it looks: the SQLite DB rides
`actions/cache` between runs (committing a ~20MB binary that churns 48×/day
would bloat the repo), and the analysis rows are committed as text so they
survive cache eviction:

| file | what |
|---|---|
| `data/wallets.csv` | every wallet scanned, with label, record and why it scored |
| `data/fills.csv` | every simulated copy fill — entry, exit, fees, P&L |
| `data/qualified_trades.csv` | the copied traders' own trades (their entry vs ours = the latency cost) |
| `data/REPORT.md`, `data/BACKTEST.txt` | human-readable snapshot each cycle |

If a cycle ever logs `first run: full discovery seed` when a DB should exist,
persistence is broken and the experiment is silently collecting nothing.

## Manifold port (play money — legal everywhere, full loop)

The same pipeline runs against Manifold Markets, including optional **real
play-money execution** (mana has no monetary value), which exercises the whole
phase-2 copy loop end to end:

```bash
python3 -m polycopy mf-discover --pages 3 --min-mana 200   # seed + classify
python3 -m polycopy mf-scan some_username                  # scan specific users
python3 -m polycopy mf-qualify some_username               # hand-pick copy targets
export MANIFOLD_API_KEY=...                                # from manifold.markets profile
python3 -m polycopy mf-watch --execute                     # copy bets with real mana
python3 -m polycopy mf-report
```

Uses `manifold.db` by default; bets/markets are normalized into the same store
schema, so metrics, classification, simulation and backtest are shared code.

## Config

Optional `polycopy.toml` in the working directory overrides any `Config` field
(see `polycopy/config.py`): thresholds, poll interval, slippage/fee assumptions,
`db_path`. Env: `POLYCOPY_DB`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## Not in scope (phase 2, only if the experiment wins)

Real order execution via the CLOB API — deliberately excluded from the MVP. Also note
Polymarket ToS geo-restrictions and that copying public on-chain flow is legal but
latency-sensitive.
