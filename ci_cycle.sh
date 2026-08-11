#!/bin/bash
# One bounded collection cycle for CI (GitHub Actions).
# First run (no DB): full discovery seed. Every run: small geo/politics
# re-sweep, one watch pass (alerts on new trades of qualified wallets),
# backtest + status report written into data/.
set -euo pipefail
cd "$(dirname "$0")"
export POLYCOPY_DB="${POLYCOPY_DB:-data/polycopy.db}"
mkdir -p data

if [ ! -f "$POLYCOPY_DB" ]; then
  echo "== first run: full discovery seed =="
  python3 -m polycopy discover --recent 5 --limit 60
else
  python3 -m polycopy discover --recent 2 --no-leaderboard --limit 15
fi

python3 -m polycopy watch --once

python3 -m polycopy backtest > data/BACKTEST.txt || true
python3 -m polycopy export --dir data
{
  echo "# polycopy status — $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo
  echo '## Qualified wallets'
  echo '```'
  python3 -m polycopy wallets
  echo '```'
  echo '## Copy-simulation P&L'
  echo '```'
  python3 -m polycopy report --refresh
  echo '```'
} > data/REPORT.md
echo "cycle done"
