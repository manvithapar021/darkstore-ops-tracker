"""DarkStore Ops Tracker: data models for a quick-commerce dark store.

A dark store is a small warehouse that fulfils grocery orders in minutes.
The models cover the four things a project-management / operations intern
tracks every day: the order pipeline, inventory, riders, and team
commitments, plus a log of process improvements.

All timestamps are naive local datetimes. Demo data is clearly labelled
as demo data wherever it appears.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

# SLA targets (minutes) for each pipeline stage. The store promises
# delivery within 45 minutes of the order being placed.
SLA_TARGETS = {
    "pick": 8,       # placed -> picked
    "pack": 5,       # picked -> packed
    "dispatch": 5,   # packed -> dispatched
    "deliver": 25,   # dispatched -> delivered
}
PROMISE_MINUTES = 45

PIPELINE_STAGES = ["placed", "picked", "packed", "dispatched", "delivered"]


class Order(Base):
    """One customer order moving through the pipeline."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    ref = Column(String(20), unique=True, nullable=False)  # e.g. ORD-1001
    customer = Column(String(80), nullable=False)
    items_count = Column(Integer, nullable=False, default=1)
    total_value = Column(Float, nullable=False, default=0.0)
    placed_at = Column(DateTime, nullable=False)
    picked_at = Column(DateTime, nullable=True)
    packed_at = Column(DateTime, nullable=True)
    dispatched_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    cancelled = Column(Boolean, nullable=False, default=False)
    rider_id = Column(Integer, ForeignKey("riders.id"), nullable=True)

    rider = relationship("Rider", back_populates="orders")

    @property
    def status(self):
        """Current pipeline stage, derived from the timestamps."""
        if self.cancelled:
            return "cancelled"
        if self.delivered_at is not None:
            return "delivered"
        if self.dispatched_at is not None:
            return "dispatched"
        if self.packed_at is not None:
            return "packed"
        if self.picked_at is not None:
            return "picked"
        return "placed"

    def stage_timestamp(self, stage):
        return {
            "placed": self.placed_at,
            "picked": self.picked_at,
            "packed": self.packed_at,
            "dispatched": self.dispatched_at,
            "delivered": self.delivered_at,
        }[stage]

    def set_stage_timestamp(self, stage, when):
        setattr(self, f"{stage}_at", when)


class InventoryItem(Base):
    """One stocked product (SKU) in the dark store."""

    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True)
    sku = Column(String(20), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    category = Column(String(60), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    reorder_level = Column(Integer, nullable=False, default=5)
    unit = Column(String(20), nullable=False, default="units")

    @property
    def is_stockout(self):
        return self.stock <= 0

    @property
    def is_low_stock(self):
        return 0 < self.stock <= self.reorder_level


class Rider(Base):
    """A delivery rider on shift."""

    __tablename__ = "riders"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    phone = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="available")
    # available | on-delivery | offline

    orders = relationship("Order", back_populates="rider")


class Task(Base):
    """A team commitment: something owned by someone, due by a date.

    This is the "100% completion" tracker: every commitment has an owner
    and a due time, and anything past due and still open is flagged for
    follow-up.
    """

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    owner = Column(String(80), nullable=False)
    team = Column(String(60), nullable=False, default="Operations")
    due_at = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="open")
    # open | in-progress | done
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)

    def is_overdue(self, now):
        return self.status != "done" and self.due_at < now


class Bottleneck(Base):
    """A recorded inefficiency, the action taken, and the measured result.

    The process-optimisation log: every entry states the problem, what was
    changed, and what the numbers did afterwards. Open entries have no
    measured result yet.
    """

    __tablename__ = "bottlenecks"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    area = Column(String(60), nullable=False)  # picking | packing | dispatch | inventory | rider
    description = Column(Text, nullable=False)
    action_taken = Column(Text, nullable=True)
    before_metric = Column(String(120), nullable=True)
    after_metric = Column(String(120), nullable=True)
    status = Column(String(20), nullable=False, default="open")  # open | resolved
    created_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)


def get_engine(db_path):
    return create_engine(f"sqlite:///{db_path}")


def get_session(db_path):
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
