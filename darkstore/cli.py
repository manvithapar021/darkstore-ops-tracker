"""CLI for DarkStore Ops Tracker.

Usage:
    python -m darkstore.cli seed     # load demo data into the database
    python -m darkstore.cli demo     # print the daily ops summary
    python -m darkstore.cli export [path]  # write the daily report .xlsx
    python -m darkstore.cli serve    # start the web dashboard
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import ops, seed as seed_module
from .app import DEFAULT_DB_PATH, create_app
from .models import get_session


def _open_db(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return get_session(db_path)


def cmd_seed(db_path):
    db = _open_db(db_path)
    counts = seed_module.seed(db, datetime.now())
    db.close()
    print(f"Seeded demo data into {db_path}: {counts}")


def cmd_demo(db_path):
    db = _open_db(db_path)
    now = datetime.now()
    summary = ops.daily_summary(db, now)
    db.close()
    print("DarkStore Ops Tracker - daily summary (demo data)")
    print(f"  Orders today:        {summary['total_orders']} "
          f"({summary['delivered_orders']} delivered, "
          f"{summary['open_orders']} in pipeline)")
    print(f"  On-time delivery:    {summary['on_time_pct']}%")
    print(f"  Avg pick / pack / dispatch / deliver: "
          f"{summary['avg_pick_min']} / {summary['avg_pack_min']} / "
          f"{summary['avg_dispatch_min']} / {summary['avg_deliver_min']} min")
    print(f"  Commitments:         {summary['open_tasks']} open, "
          f"{summary['overdue_tasks']} overdue, "
          f"{summary['task_completion_pct']}% complete")
    print(f"  Stock-outs:          {summary['stockouts']} "
          f"({summary['low_stock']} low-stock items)")
    print(f"  Riders on delivery:  {summary['riders_on_delivery']}/"
          f"{summary['riders_total']}")


def cmd_export(db_path, out_path):
    db = _open_db(db_path)
    now = datetime.now()
    wb = ops.build_daily_report(db, now)
    db.close()
    wb.save(out_path)
    print(f"Daily report written to {out_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="DarkStore Ops Tracker CLI")
    parser.add_argument("command", choices=["seed", "demo", "export", "serve"])
    parser.add_argument("path", nargs="?", default=None,
                        help="output path for export")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args(argv)

    if args.command == "seed":
        cmd_seed(args.db)
    elif args.command == "demo":
        cmd_demo(args.db)
    elif args.command == "export":
        out = args.path or f"darkstore-daily-report-{datetime.now():%Y-%m-%d}.xlsx"
        cmd_export(args.db, out)
    elif args.command == "serve":
        create_app(args.db).run(port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
