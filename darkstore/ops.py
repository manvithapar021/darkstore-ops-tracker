"""Operations logic for DarkStore Ops Tracker.

Pure functions over the models in :mod:`darkstore.models` so the same
rules drive the web dashboard, the Excel export and the tests:

- SLA breach detection per pipeline stage (and for orders stuck mid-pipeline)
- pipeline stage transitions
- daily aggregates (computed with pandas)
- task overdue / completion tracking
- the daily Excel report (openpyxl)
"""

from datetime import timedelta

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font

from .models import (
    PIPELINE_STAGES,
    PROMISE_MINUTES,
    SLA_TARGETS,
    Bottleneck,
    InventoryItem,
    Order,
    Rider,
    Task,
)

# stage -> (timestamp field before it, timestamp field of it, SLA key)
_STAGE_WINDOWS = {
    "pick": ("placed_at", "picked_at"),
    "pack": ("picked_at", "packed_at"),
    "dispatch": ("packed_at", "dispatched_at"),
    "deliver": ("dispatched_at", "delivered_at"),
}

# status -> the SLA stage that comes next for an order sitting there
_NEXT_STAGE = {
    "placed": "pick",
    "picked": "pack",
    "packed": "dispatch",
    "dispatched": "deliver",
}


def minutes_between(start, end):
    """Whole minutes between two datetimes."""
    return (end - start).total_seconds() / 60.0


def stage_duration(order, stage):
    """Minutes an order spent in one stage, or None if not completed."""
    start_field, end_field = _STAGE_WINDOWS[stage]
    start = getattr(order, start_field)
    end = getattr(order, end_field)
    if start is None or end is None:
        return None
    return minutes_between(start, end)


def order_breaches(order, now):
    """SLA breaches for one order.

    Returns a list of dicts: {stage, minutes, target, kind} where kind is
    "completed" (the stage took too long) or "waiting" (the order has been
    sitting in the stage longer than the target allows). Cancelled orders
    never breach.
    """
    breaches = []
    if order.cancelled:
        return breaches
    for stage, target in SLA_TARGETS.items():
        duration = stage_duration(order, stage)
        if duration is not None and duration > target:
            breaches.append(
                {"stage": stage, "minutes": round(duration, 1),
                 "target": target, "kind": "completed"}
            )
    # Waiting breach: order is mid-pipeline and the next stage is overdue.
    nxt = _NEXT_STAGE.get(order.status)
    if nxt is not None:
        last_stamp = order.stage_timestamp(order.status)
        waiting = minutes_between(last_stamp, now)
        if waiting > SLA_TARGETS[nxt]:
            breaches.append(
                {"stage": nxt, "minutes": round(waiting, 1),
                 "target": SLA_TARGETS[nxt], "kind": "waiting"}
            )
    return breaches


def is_on_time(order):
    """True if a delivered order arrived within the 45-minute promise."""
    if order.delivered_at is None or order.cancelled:
        return False
    return minutes_between(order.placed_at, order.delivered_at) <= PROMISE_MINUTES


def advance_order(session, order, now):
    """Move an order to its next pipeline stage, stamping the time.

    Returns the new status. Raises ValueError for delivered/cancelled
    orders, which have nowhere left to go.
    """
    if order.status in ("delivered", "cancelled"):
        raise ValueError(f"Order {order.ref} is {order.status} and cannot advance")
    next_index = PIPELINE_STAGES.index(order.status) + 1
    next_stage = PIPELINE_STAGES[next_index]
    order.set_stage_timestamp(next_stage, now)
    session.add(order)
    session.commit()
    return order.status


def orders_dataframe(session):
    """All non-cancelled orders as a pandas DataFrame with stage minutes."""
    rows = []
    for o in session.query(Order).filter_by(cancelled=False).all():
        rows.append({
            "ref": o.ref,
            "status": o.status,
            "items": o.items_count,
            "value": o.total_value,
            "pick_min": stage_duration(o, "pick"),
            "pack_min": stage_duration(o, "pack"),
            "dispatch_min": stage_duration(o, "dispatch"),
            "deliver_min": stage_duration(o, "deliver"),
            "total_min": (
                minutes_between(o.placed_at, o.delivered_at)
                if o.delivered_at is not None else None
            ),
            "on_time": is_on_time(o) if o.delivered_at is not None else None,
        })
    return pd.DataFrame(rows)


def daily_summary(session, now):
    """The numbers on the dashboard, computed with pandas."""
    df = orders_dataframe(session)
    delivered = df[df["status"] == "delivered"] if not df.empty else df
    total = len(df)
    delivered_count = len(delivered)
    on_time_pct = (
        round(100.0 * delivered["on_time"].sum() / delivered_count, 1)
        if delivered_count else 0.0
    )
    open_orders = total - delivered_count

    def _avg(col):
        if df.empty or df[col].dropna().empty:
            return None
        return round(float(df[col].mean()), 1)

    tasks = session.query(Task).all()
    open_tasks = [t for t in tasks if t.status != "done"]
    overdue = [t for t in tasks if t.is_overdue(now)]
    completion_pct = (
        round(100.0 * (len(tasks) - len(open_tasks)) / len(tasks), 1)
        if tasks else 0.0
    )

    items = session.query(InventoryItem).all()
    stockouts = [i for i in items if i.is_stockout]
    low_stock = [i for i in items if i.is_low_stock]

    riders = session.query(Rider).all()
    on_delivery = [r for r in riders if r.status == "on-delivery"]

    return {
        "total_orders": total,
        "delivered_orders": delivered_count,
        "open_orders": open_orders,
        "on_time_pct": on_time_pct,
        "avg_pick_min": _avg("pick_min"),
        "avg_pack_min": _avg("pack_min"),
        "avg_dispatch_min": _avg("dispatch_min"),
        "avg_deliver_min": _avg("deliver_min"),
        "avg_total_min": _avg("total_min"),
        "total_tasks": len(tasks),
        "open_tasks": len(open_tasks),
        "overdue_tasks": len(overdue),
        "task_completion_pct": completion_pct,
        "stockouts": len(stockouts),
        "low_stock": len(low_stock),
        "riders_on_delivery": len(on_delivery),
        "riders_total": len(riders),
    }


def overdue_tasks(session, now):
    """Open tasks whose due time has passed, oldest first."""
    return sorted(
        (t for t in session.query(Task).all() if t.is_overdue(now)),
        key=lambda t: t.due_at,
    )


def stock_alerts(session):
    """(stock-out items, low-stock items) for the inventory page."""
    items = session.query(InventoryItem).all()
    return [i for i in items if i.is_stockout], [i for i in items if i.is_low_stock]


def rider_board(session):
    """Riders with their delivered-order count today, busiest first."""
    board = []
    for r in session.query(Rider).all():
        delivered = sum(
            1 for o in r.orders
            if o.status == "delivered" and not o.cancelled
        )
        board.append({"rider": r, "delivered": delivered})
    return sorted(board, key=lambda b: b["delivered"], reverse=True)


def build_daily_report(session, now):
    """Build the daily ops report as an openpyxl workbook.

    Sheets: Summary, Orders, Inventory, Riders, Tasks, Bottlenecks.
    This is the Excel proof: the same numbers the dashboard shows,
    exported as a .xlsx the ops team can open, filter and share.
    """
    summary = daily_summary(session, now)
    wb = Workbook()
    bold = Font(bold=True)

    ws = wb.active
    ws.title = "Summary"
    ws.append(["DarkStore Ops Tracker - Daily Operations Report (demo data)"])
    ws.append([f"Generated: {now.strftime('%d %b %Y, %H:%M')}"])
    ws.append([])
    for label, value in [
        ("Total orders", summary["total_orders"]),
        ("Delivered", summary["delivered_orders"]),
        ("Still in pipeline", summary["open_orders"]),
        ("On-time delivery %", summary["on_time_pct"]),
        ("Avg pick time (min)", summary["avg_pick_min"]),
        ("Avg pack time (min)", summary["avg_pack_min"]),
        ("Avg dispatch time (min)", summary["avg_dispatch_min"]),
        ("Avg delivery time (min)", summary["avg_deliver_min"]),
        ("Avg total time (min)", summary["avg_total_min"]),
        ("Open commitments", summary["open_tasks"]),
        ("Overdue commitments", summary["overdue_tasks"]),
        ("Commitment completion %", summary["task_completion_pct"]),
        ("Stock-outs", summary["stockouts"]),
        ("Low-stock items", summary["low_stock"]),
        ("Riders on delivery", summary["riders_on_delivery"]),
    ]:
        ws.append([label, value])
    for row in ws.iter_rows(min_row=1, max_row=3):
        for cell in row:
            cell.font = bold

    ws = wb.create_sheet("Orders")
    ws.append(["Ref", "Status", "Items", "Value (Rs)", "Pick (min)",
               "Pack (min)", "Dispatch (min)", "Deliver (min)",
               "Total (min)", "On time", "SLA breaches"])
    for cell in ws[1]:
        cell.font = bold
    for o in session.query(Order).order_by(Order.placed_at).all():
        ws.append([
            o.ref, o.status, o.items_count, o.total_value,
            stage_duration(o, "pick"), stage_duration(o, "pack"),
            stage_duration(o, "dispatch"), stage_duration(o, "deliver"),
            minutes_between(o.placed_at, o.delivered_at)
            if o.delivered_at is not None else None,
            "Yes" if is_on_time(o) else ("No" if o.delivered_at else "-"),
            "; ".join(
                f"{b['stage']} {b['minutes']}m > {b['target']}m ({b['kind']})"
                for b in order_breaches(o, now)
            ),
        ])

    ws = wb.create_sheet("Inventory")
    ws.append(["SKU", "Product", "Category", "Stock", "Reorder level", "Alert"])
    for cell in ws[1]:
        cell.font = bold
    for i in session.query(InventoryItem).order_by(InventoryItem.stock).all():
        alert = "STOCK-OUT" if i.is_stockout else ("LOW STOCK" if i.is_low_stock else "")
        ws.append([i.sku, i.name, i.category, i.stock, i.reorder_level, alert])

    ws = wb.create_sheet("Riders")
    ws.append(["Rider", "Phone", "Status", "Delivered today"])
    for cell in ws[1]:
        cell.font = bold
    for entry in rider_board(session):
        r = entry["rider"]
        ws.append([r.name, r.phone, r.status, entry["delivered"]])

    ws = wb.create_sheet("Tasks")
    ws.append(["Task", "Owner", "Team", "Due", "Status", "Overdue"])
    for cell in ws[1]:
        cell.font = bold
    for t in session.query(Task).order_by(Task.due_at).all():
        ws.append([
            t.title, t.owner, t.team,
            t.due_at.strftime("%d %b %Y %H:%M"), t.status,
            "Yes" if t.is_overdue(now) else "No",
        ])

    ws = wb.create_sheet("Bottlenecks")
    ws.append(["Title", "Area", "Problem", "Action taken",
               "Before", "After", "Status"])
    for cell in ws[1]:
        cell.font = bold
    for b in session.query(Bottleneck).order_by(Bottleneck.created_at).all():
        ws.append([
            b.title, b.area, b.description, b.action_taken or "",
            b.before_metric or "", b.after_metric or "", b.status,
        ])

    return wb
