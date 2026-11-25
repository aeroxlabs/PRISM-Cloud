import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    create_engine, String, Integer, DateTime, Index, select, update
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./prism_cloud.db")

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}

engine = create_engine(DATABASE_URL, **engine_kwargs)


class Base(DeclarativeBase):
    pass


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(8), nullable=False)
    requests_used_this_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    billing_cycle_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


Index("ix_api_keys_active_tier", APIKey.is_active, APIKey.tier)

SessionFactory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def utcnow():
    return datetime.now(timezone.utc)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session_factory():
    return SessionFactory


def reset_monthly_counters_if_due(session, key: APIKey):
    now = utcnow()
    cycle_start = key.billing_cycle_start

    # SQLite may return naive datetimes even when timezone=True.
    if cycle_start.tzinfo is None:
        cycle_start = cycle_start.replace(tzinfo=timezone.utc)

    if now - cycle_start >= timedelta(days=30):
        key.requests_used_this_month = 0
        key.overage_count = 0
        key.billing_cycle_start = now
        session.flush()


def check_database() -> bool:
    """Run a lightweight query to verify database connectivity."""
    from sqlalchemy import text
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
