"""Tests for DarkStore Ops Tracker.

Run: python -m pytest tests/ -v
"""

from datetime import datetime, timedelta

import pytest
from openpyxl import load_workbook

from darkstore import ops
from darkstore.app import create_app
from darkstore.models import (
    Bottleneck,
    InventoryItem,
    Order,
    Rider,
    Task,
    get_session,
)
from darkstore.seed import seed as seed_demo

NOW = datetime(2026, 11, 18, 20, 30)


@pytest.fixture()
def db():
    session = get_session(":memory:")
    yield session
    session.close()


def _order(ref="ORD-1", placed_ago=60, pick=None, pack=None,
           dispatch=None, deliver=None, cancelled=False):
    placed = NOW - timedelta(minutes=placed_ago)
    order = Order(ref=ref, customer="Test Customer", items_count=3,
                  total_value=450.0, placed_at=placed, cancelled=cancelled)
    cursor = placed
    for minutes, stage in ((pick, "picked"), (pack, "packed"),
                           (dispatch, "dispatched"), (deliver, "delivered")):
        if minutes is None:
            break
        cursor = cursor + timedelta(minutes=minutes)
        order.set_stage_timestamp(stage, cursor)
    return order


# --- SLA breach detection ---

def test_slow_pick_is_flagged_as_breach(db):
    order = _order(pick=14, pack=4, dispatch=3, deliver=18)
    db.add(order)
    db.commit()
    breaches = ops.order_breaches(order, NOW)
    pick_breach = [b for b in breaches if b["stage"] == "pick"]
    assert len(pick_breach) == 1
    assert pick_breach[0]["minutes"] == 14
    assert pick_breach[0]["target"] == 8
    assert pick_breach[0]["kind"] == "completed"


def test_order_within_sla_has_no_breaches(db):
    order = _order(pick=6, pack=4, dispatch=3, deliver=18)
    db.add(order)
    db.commit()
    assert ops.order_breaches(order, NOW) == []
    assert ops.is_on_time(order) is True


def test_order_waiting_too_long_mid_pipeline_is_flagged(db):
    # Placed 35 minutes ago, still not picked (pick SLA is 8 minutes).
    order = _order(placed_ago=35)
    db.add(order)
    db.commit()
    breaches = ops.order_breaches(order, NOW)
    assert len(breaches) == 1
    assert breaches[0]["stage"] == "pick"
    assert breaches[0]["kind"] == "waiting"
    assert breaches[0]["minutes"] == 35


def test_late_delivery_is_not_on_time(db):
    # Total 50 minutes, over the 45-minute promise.
    order = _order(pick=14, pack=6, dispatch=4, deliver=26)
    db.add(order)
    db.commit()
    assert ops.is_on_time(order) is False


def test_cancelled_order_never_breaches(db):
    order = _order(pick=30, pack=30, dispatch=30, deliver=30, cancelled=True)
    db.add(order)
    db.commit()
    assert ops.order_breaches(order, NOW) == []


# --- Pipeline stage transitions ---

def test_advance_moves_order_through_stages_in_order(db):
    order = _order()
    db.add(order)
    db.commit()
    assert order.status == "placed"
    assert ops.advance_order(db, order, NOW) == "picked"
    assert ops.advance_order(db, order, NOW) == "packed"
    assert ops.advance_order(db, order, NOW) == "dispatched"
    assert ops.advance_order(db, order, NOW) == "delivered"
    with pytest.raises(ValueError):
        ops.advance_order(db, order, NOW)


# --- Task overdue / completion logic ---

def test_overdue_task_logic(db):
    overdue = Task(title="Chase vendor", owner="Rahul", team="Inventory",
                   due_at=NOW - timedelta(hours=2), status="open",
                   created_at=NOW - timedelta(hours=5))
    done_late = Task(title="Old report", owner="Anita", team="Operations",
                     due_at=NOW - timedelta(hours=2), status="done",
                     completed_at=NOW - timedelta(hours=1),
                     created_at=NOW - timedelta(hours=5))
    future = Task(title="Evening roster", owner="Imran", team="Dispatch",
                  due_at=NOW + timedelta(hours=2), status="open",
                  created_at=NOW - timedelta(hours=5))
    db.add_all([overdue, done_late, future])
    db.commit()
    assert overdue.is_overdue(NOW) is True
    assert done_late.is_overdue(NOW) is False
    assert future.is_overdue(NOW) is False
    assert ops.overdue_tasks(db, NOW) == [overdue]


# --- Dashboard aggregates (seeded demo day) ---

def test_dashboard_aggregates_from_seeded_day(db):
    seed_demo(db, NOW)
    summary = ops.daily_summary(db, NOW)
    assert summary["total_orders"] == 24  # 24 live + 1 cancelled
    assert summary["delivered_orders"] == 21
    assert summary["open_orders"] == 3
    assert summary["on_time_pct"] == 95.2  # 20 of 21 delivered on time
    assert summary["overdue_tasks"] == 2
    assert summary["stockouts"] == 2
    assert summary["low_stock"] == 3
    assert summary["task_completion_pct"] == 44.4  # 4 of 9 done
    assert summary["avg_pick_min"] is not None
    assert 5.0 < summary["avg_pick_min"] < 8.0


def test_stock_alerts_split_stockouts_and_low_stock(db):
    db.add_all([
        InventoryItem(sku="A", name="Milk", category="Dairy", stock=0, reorder_level=10),
        InventoryItem(sku="B", name="Bread", category="Bakery", stock=4, reorder_level=10),
        InventoryItem(sku="C", name="Rice", category="Staples", stock=40, reorder_level=5),
    ])
    db.commit()
    stockouts, low = ops.stock_alerts(db)
    assert [i.sku for i in stockouts] == ["A"]
    assert [i.sku for i in low] == ["B"]


# --- Excel export ---

def test_excel_export_has_all_sheets_and_matching_rows(db, tmp_path):
    seed_demo(db, NOW)
    wb = ops.build_daily_report(db, NOW)
    path = tmp_path / "report.xlsx"
    wb.save(path)
    loaded = load_workbook(path)
    assert loaded.sheetnames == ["Summary", "Orders", "Inventory",
                                 "Riders", "Tasks", "Bottlenecks"]
    orders = loaded["Orders"]
    assert orders.max_row == 26  # header + 25 orders (incl. cancelled)
    assert orders.cell(row=2, column=1).value == "ORD-1001"
    summary = loaded["Summary"]
    labels = [row[0].value for row in summary.iter_rows(min_row=1, max_row=30)]
    assert "On-time delivery %" in labels
    tasks = loaded["Tasks"]
    assert tasks.max_row == 10  # header + 9 tasks
    bottlenecks = loaded["Bottlenecks"]
    assert bottlenecks.max_row == 4  # header + 3 entries
    assert "STOCK-OUT" in [c.value for row in loaded["Inventory"].iter_rows()
                           for c in row]


# --- Web app smoke tests ---

@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "test.db"
    session = get_session(str(db_path))
    seed_demo(session, NOW)
    session.close()
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def test_dashboard_page_loads_with_summary_numbers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"On-time delivery" in response.data
    assert b"95.2%" in response.data
    assert b"demo data" in response.data.lower()


def test_export_route_returns_xlsx(client):
    response = client.get("/export")
    assert response.status_code == 200
    assert "spreadsheetml" in response.content_type
    assert response.data[:2] == b"PK"  # zip container = .xlsx
    assert len(response.data) > 5000
