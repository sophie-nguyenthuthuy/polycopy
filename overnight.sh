#!/bin/bash
# Overnight driver: initial discovery sweep, then 60s watch cycles.
# Re-sweeps recent large geo/politics fills every ~30 min so candidates
# keep accumulating even when the initial sweep finds no qualified wallets.
set -u
cd "$(dirname "$0")"

python3 -m polycopy discover --recent 5 --limit 100

n=0
while true; do
  python3 -m polycopy watch --once
  n=$((n + 1))
  if [ $((n % 30)) -eq 0 ]; then
    echo "== $(date '+%F %T') periodic re-sweep =="
    python3 -m polycopy discover --recent 2 --no-leaderboard
    python3 -m polycopy report --refresh
  fi
  sleep 60
done
