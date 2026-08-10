"""polycopy CLI."""
from __future__ import annotations

import argparse

from . import backtest as bt
from . import simulate
from .api import PolymarketAPI
from .config import Config
from .discover import discover, print_wallets, scan_wallet
from .store import Store
from .watch import watch


def main(argv=None):
    p = argparse.ArgumentParser(prog="polycopy",
                                description="Polymarket perfect-trader copy alert MVP")
    p.add_argument("--db", help="sqlite path (default polycopy.db / $POLYCOPY_DB)")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="seed from leaderboards, scan + classify wallets")
    d.add_argument("--limit", type=int, help="max wallets to scan")
    d.add_argument("--addr", action="append", default=[], help="extra wallet address(es) to include")
    d.add_argument("--recent", type=int, default=0, metavar="PAGES",
                   help="also seed from N pages of recent large geo/politics fills")
    d.add_argument("--no-leaderboard", action="store_true")

    s = sub.add_parser("scan", help="scan specific wallet(s)")
    s.add_argument("addresses", nargs="+")

    w = sub.add_parser("wallets", help="list stored wallets")
    w.add_argument("--all", action="store_true", help="include non-qualified")

    wa = sub.add_parser("watch", help="poll qualified wallets, alert + simulate copies")
    wa.add_argument("--once", action="store_true")
    wa.add_argument("--dry-run", action="store_true", help="print alerts instead of sending")
    wa.add_argument("--poll", type=int, help="seconds between polls")

    sub.add_parser("backtest", help="replay stored history as copy-trades ($10/$100/perfect100)")

    r = sub.add_parser("report", help="P&L report for live + backtest simulations")
    r.add_argument("--refresh", action="store_true", help="refresh marks/resolutions first")

    md = sub.add_parser("mf-discover", help="Manifold: seed from recent big bets, scan + classify")
    md.add_argument("--pages", type=int, default=3, help="pages of 1000 recent bets to seed from")
    md.add_argument("--min-mana", type=float, default=100.0)
    md.add_argument("--limit", type=int)

    ms = sub.add_parser("mf-scan", help="Manifold: scan specific user(s) by username or id")
    ms.add_argument("users", nargs="+")

    mw = sub.add_parser("mf-watch", help="Manifold: poll qualified users, alert + sim (+ optional play-money execute)")
    mw.add_argument("--once", action="store_true")
    mw.add_argument("--dry-run", action="store_true")
    mw.add_argument("--poll", type=int)
    mw.add_argument("--execute", action="store_true",
                    help="place real play-money bets (needs MANIFOLD_API_KEY env)")

    sub.add_parser("mf-wallets", help="Manifold: list stored users")
    sub.add_parser("mf-report", help="Manifold: live sim + backtest P&L")

    args = p.parse_args(argv)
    cfg = Config.load()
    is_mf = args.cmd.startswith("mf-")
    if args.db:
        cfg.db_path = args.db
    elif is_mf:
        cfg.db_path = "manifold.db"
    store = Store(cfg.db_path)
    api = PolymarketAPI(cfg.rate_limit_sec, cfg.http_timeout)

    if is_mf:
        import os

        from . import manifold as mf
        mapi = mf.ManifoldAPI(api_key=os.environ.get("MANIFOLD_API_KEY", ""))
        if args.cmd == "mf-discover":
            mf.discover(store, mapi, cfg, pages=args.pages, min_mana=args.min_mana, limit=args.limit)
            print()
            print_wallets(store, qualified_only=True)
        elif args.cmd == "mf-scan":
            for u in args.users:
                uid = u if len(u) > 20 else mf.ManifoldAPI().user_by_name(u).get("id", u)
                mf.scan_user(store, mapi, cfg, uid, verbose=True)
        elif args.cmd == "mf-wallets":
            print_wallets(store, qualified_only=False)
        elif args.cmd == "mf-watch":
            if args.poll:
                cfg.poll_sec = args.poll
            mf.watch(store, mapi, cfg, once=args.once, dry_run=args.dry_run, execute=args.execute)
        elif args.cmd == "mf-report":
            mf.refresh_marks(store, mapi)
            print("== live (watch-mode) fills ==")
            print(simulate.report(store, "live"))
            print("\n== backtest fills ==")
            print(bt.run(store, cfg))
        return

    if args.cmd == "discover":
        discover(store, api, cfg, extra_addresses=args.addr, limit=args.limit,
                 recent_pages=args.recent, use_leaderboard=not args.no_leaderboard)
        print()
        print_wallets(store, qualified_only=True)
    elif args.cmd == "scan":
        for a in args.addresses:
            scan_wallet(store, api, cfg, a.lower(), verbose=True)
    elif args.cmd == "wallets":
        print_wallets(store, qualified_only=not args.all)
    elif args.cmd == "watch":
        if args.poll:
            cfg.poll_sec = args.poll
        watch(store, api, cfg, once=args.once, dry_run=args.dry_run)
    elif args.cmd == "backtest":
        print("Backtest (entries at trader price "
              f"+{cfg.backtest_adverse_bps}bps adverse, exits on trader sell/resolution):\n")
        print(bt.run(store, cfg))
    elif args.cmd == "report":
        if args.refresh:
            from .discover import sync_markets
            sync_markets(store, api, store.unresolved_condition_ids())
            simulate.refresh_marks(store, api, cfg)
        print("== live (watch-mode) fills ==")
        print(simulate.report(store, "live"))
        print("\n== backtest fills ==")
        print(simulate.report(store, "backtest"))


if __name__ == "__main__":
    main()
