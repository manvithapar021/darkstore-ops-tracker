"""Demo seed data for DarkStore Ops Tracker.

One full day of realistic operations for a fictional dark store
("DS-01, demo store"). Everything here is invented demo data: fake
customer names, fake rider phone numbers, and order timings generated
relative to the moment the seed runs. No real store, customer or order
is represented.
"""

from datetime import datetime, timedelta

from .models import Bottleneck, InventoryItem, Order, Rider, Task

# (minutes before "now" the order was placed, pick, pack, dispatch,
#  deliver) — None means the stage has not happened yet. A few orders
# are deliberately slow so the SLA flags have something to catch.
_ORDER_PLAN = [
    # placed_ago, pick, pack, dispatch, deliver, items, value, rider
    (545, 6, 4, 3, 18, 5, 642, 1),
    (530, 7, 5, 4, 22, 3, 389, 2),
    (512, 14, 6, 4, 26, 8, 918, 1),   # pick breach: 14 > 8 min
    (495, 5, 4, 3, 19, 2, 215, 3),
    (478, 8, 5, 6, 24, 6, 734, 2),
    (460, 6, 4, 4, 31, 4, 487, 4),    # deliver breach: 31 > 25 min
    (441, 7, 9, 4, 20, 7, 812, 1),    # pack breach: 9 > 5 min
    (425, 5, 3, 3, 17, 3, 298, 3),
    (408, 6, 4, 5, 21, 5, 556, 2),
    (390, 9, 5, 4, 23, 4, 461, 4),    # pick breach: 9 > 8 min
    (372, 6, 4, 3, 19, 2, 176, 1),
    (355, 7, 4, 4, 28, 9, 1044, 2),   # deliver breach: 28 > 25 min
    (338, 5, 5, 3, 18, 3, 322, 3),
    (320, 6, 4, 4, 20, 6, 689, 4),
    (302, 8, 4, 5, 22, 4, 503, 1),
    (285, 6, 3, 3, 16, 2, 189, 2),
    (268, 7, 5, 4, 21, 5, 598, 3),
    (250, 5, 4, 3, 19, 3, 341, 4),
    (232, 6, 4, 4, 24, 7, 776, 1),
    (215, 7, 4, 3, 18, 2, 204, 2),
    (196, 6, 5, 4, 22, 4, 457, 3),
    (120, 6, 4, None, None, 5, 612, 4),  # in pipeline: packed, awaiting dispatch
    (95, 5, None, None, None, 3, 287, None),  # in pipeline: picked, awaiting pack
    (35, None, None, None, None, 4, 448, None),  # just placed; pick SLA (8 min) already breached
]

_CUSTOMERS = [
    "Aarav Mehta", "Priya Nair", "Rohan Iyer", "Sana Sheikh", "Kabir Das",
    "Ananya Rao", "Vikram Joshi", "Meera Pillai", "Arjun Malhotra",
    "Divya Menon", "Nikhil Agarwal", "Kavya Reddy", "Aditya Sharma",
    "Riya Kapoor", "Sanjay Verma", "Neha Gupta", "Farhan Ali",
    "Ishita Bose", "Karan Singh", "Tara Krishnan", "Dev Patel",
    "Lakshmi Venkat", "Yash Thakur", "Zoya Khan",
]

_RIDERS = [
    ("Rahul Kumar", "+91 98100 00001", "available"),
    ("Imran Sheikh", "+91 98100 00002", "available"),
    ("Suresh Yadav", "+91 98100 00003", "on-delivery"),
    ("Anita Devi", "+91 98100 00004", "available"),
]

_INVENTORY = [
    # sku, name, category, stock, reorder_level
    ("SKU-101", "Amul Full Cream Milk 1L", "Dairy", 42, 10),
    ("SKU-102", "Brown Bread 400g", "Bakery", 18, 8),
    ("SKU-103", "Banana Robusta 1kg", "Fruits", 25, 10),
    ("SKU-104", "Onion 1kg", "Vegetables", 0, 10),      # stock-out
    ("SKU-105", "Tomato 1kg", "Vegetables", 6, 10),     # low stock
    ("SKU-106", "Basmati Rice 1kg", "Staples", 33, 8),
    ("SKU-107", "Sunflower Oil 1L", "Staples", 14, 6),
    ("SKU-108", "Eggs (Pack of 12)", "Dairy", 0, 12),   # stock-out
    ("SKU-109", "Butter 100g", "Dairy", 9, 10),         # low stock
    ("SKU-110", "Aashirvaad Atta 5kg", "Staples", 21, 5),
    ("SKU-111", "Maggi Noodles 12-pack", "Instant Food", 27, 8),
    ("SKU-112", "Coca-Cola 750ml", "Beverages", 31, 10),
    ("SKU-113", "Parle-G Biscuits 200g", "Snacks", 4, 10),  # low stock
    ("SKU-114", "Tata Salt 1kg", "Staples", 48, 10),
    ("SKU-115", "Curd 400g", "Dairy", 16, 8),
    ("SKU-116", "Potato 1kg", "Vegetables", 29, 10),
    ("SKU-117", "Toothpaste 150g", "Personal Care", 12, 5),
    ("SKU-118", "Dishwash Bar 200g", "Home Care", 19, 5),
]

# (title, owner, team, due offset in minutes from now, status)
_TASKS = [
    ("Restock onion and eggs from morning vendor delivery", "Rahul Kumar", "Inventory", -180, "done"),
    ("Call 3 customers whose orders were delayed past 45 min", "Anita Devi", "Support", -120, "done"),
    ("Reprint shelf labels for aisle 2 after price update", "Suresh Yadav", "Store Ops", -60, "done"),
    ("Confirm evening rider roster (6 PM - 11 PM shift)", "Imran Sheikh", "Dispatch", -30, "done"),
    ("Follow up with vendor on tomato short supply", "Rahul Kumar", "Inventory", -240, "open"),   # overdue
    ("Update pick-path chart after new rack layout", "Anita Devi", "Store Ops", -90, "open"),     # overdue
    ("Prepare daily ops report for area manager", "Imran Sheikh", "Operations", 90, "in-progress"),
    ("Audit cold-storage temperature log for the week", "Suresh Yadav", "Store Ops", 240, "open"),
    ("Chase packaging supplier on delayed polybag delivery", "Rahul Kumar", "Inventory", 300, "open"),
]

_BOTTLENECKS = [
    {
        "title": "Picking slows down when two riders wait at the same rack",
        "area": "picking",
        "description": "Pickers and riders queue at the dairy rack during the 8-10 AM rush; pick times rose above the 8-minute SLA on 3 orders.",
        "action_taken": "Split dairy into two pick zones and staggered rider arrivals by 5 minutes.",
        "before_metric": "Avg pick time 11.5 min (8-10 AM)",
        "after_metric": "Avg pick time 6.8 min (8-10 AM)",
        "status": "resolved",
        "created_hours_ago": 30,
        "resolved_hours_ago": 6,
    },
    {
        "title": "Packing station runs out of medium bags by 7 PM",
        "area": "packing",
        "description": "Medium polybags stock out most evenings, forcing repacks into large bags and slowing pack times.",
        "action_taken": "Raised the evening par level and added a 6 PM bag-count check to the shift checklist.",
        "before_metric": None,
        "after_metric": None,
        "status": "open",
        "created_hours_ago": 12,
        "resolved_hours_ago": None,
    },
    {
        "title": "Delivery delays on orders to the far side of the sector",
        "area": "dispatch",
        "description": "Orders beyond 3 km take 28-31 minutes to deliver, breaching the 25-minute dispatch-to-delivery SLA.",
        "action_taken": None,
        "before_metric": "Avg delivery time 29 min beyond 3 km",
        "after_metric": None,
        "status": "open",
        "created_hours_ago": 8,
        "resolved_hours_ago": None,
    },
]


def seed(session, now=None):
    """Wipe and re-seed the database with one demo day of operations."""
    now = now or datetime.now()
    for table in (Order, Task, Bottleneck, InventoryItem, Rider):
        session.query(table).delete()

    riders = {}
    for name, phone, status in _RIDERS:
        rider = Rider(name=name, phone=phone, status=status)
        session.add(rider)
        session.flush()
        riders[len(riders) + 1] = rider

    for idx, plan in enumerate(_ORDER_PLAN):
        placed_ago, pick, pack, dispatch, deliver, items, value, rider_no = plan
        placed_at = now - timedelta(minutes=placed_ago)
        order = Order(
            ref=f"ORD-{1001 + idx}",
            customer=_CUSTOMERS[idx % len(_CUSTOMERS)],
            items_count=items,
            total_value=float(value),
            placed_at=placed_at,
            rider_id=riders[rider_no].id if rider_no else None,
        )
        cursor = placed_at
        for minutes, stage in ((pick, "picked"), (pack, "packed"),
                               (dispatch, "dispatched"), (deliver, "delivered")):
            if minutes is None:
                break
            cursor = cursor + timedelta(minutes=minutes)
            order.set_stage_timestamp(stage, cursor)
        session.add(order)

    # One cancelled order, for completeness.
    session.add(Order(
        ref="ORD-1025", customer="Nikhil Agarwal", items_count=2,
        total_value=156.0, placed_at=now - timedelta(minutes=150),
        cancelled=True,
    ))

    for sku, name, category, stock, reorder in _INVENTORY:
        session.add(InventoryItem(
            sku=sku, name=name, category=category, stock=stock,
            reorder_level=reorder,
        ))

    for title, owner, team, due_offset, status in _TASKS:
        due_at = now + timedelta(minutes=due_offset)
        session.add(Task(
            title=title, owner=owner, team=team, due_at=due_at,
            status=status,
            completed_at=(due_at - timedelta(minutes=20)
                          if status == "done" else None),
            created_at=now - timedelta(hours=10),
        ))

    for b in _BOTTLENECKS:
        session.add(Bottleneck(
            title=b["title"], area=b["area"], description=b["description"],
            action_taken=b["action_taken"], before_metric=b["before_metric"],
            after_metric=b["after_metric"], status=b["status"],
            created_at=now - timedelta(hours=b["created_hours_ago"]),
            resolved_at=(now - timedelta(hours=b["resolved_hours_ago"])
                         if b["resolved_hours_ago"] is not None else None),
        ))

    session.commit()
    return {
        "orders": len(_ORDER_PLAN) + 1,
        "riders": len(_RIDERS),
        "inventory_items": len(_INVENTORY),
        "tasks": len(_TASKS),
        "bottlenecks": len(_BOTTLENECKS),
    }
