"""DarkStore Ops Tracker web app.

Routes:
- GET  /              — daily ops summary dashboard
- GET  /orders       — order pipeline with SLA breach flags
- GET  /inventory    — stock levels with stock-out / low-stock alerts
- GET  /riders       — rider dispatch board
- GET  /tasks        — team task & commitment tracker
- GET  /bottlenecks  — process-optimisation log
- GET  /export       — download the daily report as .xlsx
- GET  /api/summary  — dashboard numbers as JSON
- POST /orders/<id>/advance — move an order to its next stage
- POST /tasks/<id>/done     — mark a commitment complete
"""

from datetime import datetime
from io import BytesIO
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

from . import ops, seed as seed_module
from .models import Bottleneck, InventoryItem, Order, Rider, Task, get_session

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "instance" / "darkstore.db"


def create_app(db_path=None):
    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
    app.config["DB_PATH"] = str(db_path or DEFAULT_DB_PATH)

    def session():
        return get_session(app.config["DB_PATH"])

    @app.context_processor
    def inject_now():
        return {"now": datetime.now()}

    @app.route("/")
    def dashboard():
        db = session()
        try:
            summary = ops.daily_summary(db, datetime.now())
            overdue = ops.overdue_tasks(db, datetime.now())
            stockouts, low_stock = ops.stock_alerts(db)
            open_bottlenecks = db.query(Bottleneck).filter_by(status="open").all()
            return render_template(
                "dashboard.html", summary=summary, overdue=overdue,
                stockouts=stockouts, low_stock=low_stock,
                open_bottlenecks=open_bottlenecks,
            )
        finally:
            db.close()

    @app.route("/orders")
    def orders():
        db = session()
        try:
            now = datetime.now()
            rows = [
                {"order": o, "breaches": ops.order_breaches(o, now),
                 "on_time": ops.is_on_time(o)}
                for o in db.query(Order).order_by(Order.placed_at.desc()).all()
            ]
            return render_template("orders.html", rows=rows, now=now)
        finally:
            db.close()

    @app.route("/orders/<int:order_id>/advance", methods=["POST"])
    def advance(order_id):
        db = session()
        try:
            order = db.query(Order).get(order_id)
            if order is None:
                return "Order not found", 404
            try:
                ops.advance_order(db, order, datetime.now())
            except ValueError as exc:
                return str(exc), 400
            return redirect(url_for("orders"))
        finally:
            db.close()

    @app.route("/inventory")
    def inventory():
        db = session()
        try:
            items = db.query(InventoryItem).order_by(InventoryItem.stock).all()
            return render_template("inventory.html", items=items)
        finally:
            db.close()

    @app.route("/riders")
    def riders():
        db = session()
        try:
            return render_template("riders.html", board=ops.rider_board(db))
        finally:
            db.close()

    @app.route("/tasks")
    def tasks():
        db = session()
        try:
            now = datetime.now()
            all_tasks = db.query(Task).order_by(Task.due_at).all()
            return render_template(
                "tasks.html", tasks=all_tasks, now=now,
                overdue=ops.overdue_tasks(db, now),
            )
        finally:
            db.close()

    @app.route("/tasks/<int:task_id>/done", methods=["POST"])
    def mark_task_done(task_id):
        db = session()
        try:
            task = db.query(Task).get(task_id)
            if task is None:
                return "Task not found", 404
            task.status = "done"
            task.completed_at = datetime.now()
            db.add(task)
            db.commit()
            return redirect(url_for("tasks"))
        finally:
            db.close()

    @app.route("/bottlenecks")
    def bottlenecks():
        db = session()
        try:
            entries = db.query(Bottleneck).order_by(Bottleneck.created_at.desc()).all()
            return render_template("bottlenecks.html", entries=entries)
        finally:
            db.close()

    @app.route("/export")
    def export():
        db = session()
        try:
            now = datetime.now()
            wb = ops.build_daily_report(db, now)
            buf = BytesIO()
            wb.save(buf)
            buf.seek(0)
            filename = f"darkstore-daily-report-{now.strftime('%Y-%m-%d')}.xlsx"
            return send_file(
                buf,
                as_attachment=True,
                download_name=filename,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        finally:
            db.close()

    @app.route("/api/summary")
    def api_summary():
        db = session()
        try:
            return jsonify(ops.daily_summary(db, datetime.now()))
        finally:
            db.close()

    return app


def main():
    import argparse

    parser = argparse.ArgumentParser(description="DarkStore Ops Tracker")
    parser.add_argument("--seed", action="store_true",
                        help="seed the database with demo data and exit")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--db", default=None, help="SQLite database path")
    args = parser.parse_args()

    db_path = args.db or str(DEFAULT_DB_PATH)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    if args.seed:
        db = get_session(db_path)
        counts = seed_module.seed(db, datetime.now())
        db.close()
        print(f"Seeded demo data: {counts}")
        return
    app = create_app(db_path)
    print("DarkStore Ops Tracker at http://127.0.0.1:5000")
    app.run(port=args.port)


if __name__ == "__main__":
    main()
