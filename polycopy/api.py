"""Thin stdlib HTTP client for Polymarket public APIs (Gamma, Data-API, CLOB).

Endpoint shapes verified live 2026-08-10:
  gamma-api.polymarket.com/markets?condition_ids=0x..&closed=true|false
  data-api.polymarket.com/trades?user=0x..&limit=500&offset=..   (offset caps ~1000)
  data-api.polymarket.com/v1/leaderboard?window=30d&rankType=pnl&limit=50
  data-api.polymarket.com/positions?user=0x..
  clob.polymarket.com/book?token_id=..
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

GAMMA = "https://gamma-api.polymarket.com"
DATA = "https://data-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

_UA = "polycopy/0.1 (research; contact via github)"


class PolymarketAPI:
    def __init__(self, rate_limit_sec: float = 0.25, timeout: float = 20.0):
        self.rate_limit_sec = rate_limit_sec
        self.timeout = timeout
        self._last_call = 0.0

    def _get(self, url: str, params: dict | None = None, tries: int = 4):
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        for attempt in range(tries):
            wait = self.rate_limit_sec - (time.time() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()
            req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError):
                if attempt < tries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

    # -- gamma ---------------------------------------------------------------
    def markets_by_condition(self, condition_ids: list[str]) -> list[dict]:
        """Fetch market metadata. Gamma filters closed markets out by default,
        so query both closed=true and closed=false per chunk."""
        out: dict[str, dict] = {}
        for i in range(0, len(condition_ids), 20):
            chunk = condition_ids[i : i + 20]
            for closed in ("false", "true"):
                params = [("condition_ids", c) for c in chunk] + [("closed", closed), ("limit", "100")]
                url = GAMMA + "/markets?" + urllib.parse.urlencode(params)
                for m in self._get(url) or []:
                    out[m["conditionId"]] = m
        return list(out.values())

    # -- data-api ------------------------------------------------------------
    def trades(self, user: str | None = None, limit: int = 500, offset: int = 0) -> list[dict]:
        params: dict = {"limit": limit, "offset": offset}
        if user:
            params["user"] = user
        return self._get(DATA + "/trades", params) or []

    def wallet_trades_all(self, user: str, max_n: int = 1000) -> list[dict]:
        out: list[dict] = []
        offset = 0
        while offset < max_n:
            batch = self.trades(user=user, limit=min(500, max_n - offset), offset=offset)
            out.extend(batch)
            if len(batch) < 500:
                break
            offset += 500
        return out

    def leaderboard(self, window: str = "30d", rank_type: str = "pnl", limit: int = 50) -> list[dict]:
        return self._get(DATA + "/v1/leaderboard", {"window": window, "rankType": rank_type, "limit": limit}) or []

    def positions(self, user: str, limit: int = 100) -> list[dict]:
        return self._get(DATA + "/positions", {"user": user, "limit": limit}) or []

    # -- clob ----------------------------------------------------------------
    def book(self, token_id: str) -> dict:
        try:
            return self._get(CLOB + "/book", {"token_id": token_id}) or {}
        except urllib.error.HTTPError:
            return {}
