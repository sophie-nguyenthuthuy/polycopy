"""Telegram alerts via Bot API. Without a token, alerts print to stdout (dry run)."""
from __future__ import annotations

import json
import urllib.request


def send(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        print(f"[alert:dryrun]\n{text}\n")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode()).get("ok", False)
    except Exception as e:  # noqa: BLE001 — alerting must never crash the watch loop
        print(f"[alert:error] {e}")
        return False


def format_alert(wallet_row: dict, trade: dict, sims: list[str]) -> str:
    name = wallet_row.get("name") or wallet_row.get("pseudonym") or trade["wallet"][:10]
    wr = wallet_row.get("win_rate") or 0
    arrow = "🟢 BUY" if trade["side"] == "BUY" else "🔴 SELL"
    slug = trade.get("event_slug") or ""
    url = slug if slug.startswith("http") else f"https://polymarket.com/event/{slug}"
    lines = [
        f"🚨 {wallet_row.get('label', '?')} trader moved",
        f"{name} — {wr:.0%} win rate, {wallet_row.get('wins', 0)}W/{wallet_row.get('losses', 0)}L",
        f"{arrow} '{trade.get('outcome')}' @ {trade['price']:.3f} — ${trade['usd']:,.0f}",
        f"{trade.get('title')}",
        url,
    ]
    lines += sims
    return "\n".join(lines)
