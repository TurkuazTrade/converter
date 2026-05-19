from __future__ import annotations

from sqlalchemy import create_engine

from app.db.base import Base
from app.models import *  # noqa: F401,F403


def test_metadata_creates_tables() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    table_names = set(Base.metadata.tables)
    assert "users" in table_names
    assert "orders" in table_names
    assert "product_barcodes" in table_names
    assert "processing_events" in table_names
