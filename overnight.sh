#!/bin/bash
# Overnight driver: initial discovery sweep (retried until the API is reachable),
# then 60s watch cycles with a geo/politics re-sweep every ~30 min.
set -u
cd "$(dirname "$0")"
SEEDED=.overnight_seeded

n=0
while true; do
  if [ ! -f "$SEEDED" ]; then
    echo "== $(date '+%F %T') seed sweep =="
    out=$(python3 -m polycopy discover --recent 5 --limit 100 2>&1)
    echo "$out"
    if echo "$out" | grep -q "Scanning 0 candidate"; then
      echo "== seed sweep got nothing (API unreachable?) — retrying in 10 min =="
      sleep 600
      continue
    fi
    touch "$SEEDED"
  fi

  python3 -m polycopy watch --once
  n=$((n + 1))
  if [ $((n % 30)) -eq 0 ]; then
    echo "== $(date '+%F %T') periodic re-sweep =="
    python3 -m polycopy discover --recent 2 --no-leaderboard
    python3 -m polycopy report --refresh
  fi
  sleep 60
done
