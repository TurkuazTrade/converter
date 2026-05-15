from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import openpyxl
import pytest
from sqlalchemy.orm import Session

from app.core.enums import OrderItemStatus, OrderStatus
from app.models.client import Client
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.services.export_service import ExportLine, ExportService, ResolvedOrderExport


TEMPLATE_PATH = Path("../data/templates/template_zakaz.xlsx").resolve()


def test_export_matches_template_contract() -> None:
    service = ExportService(template_path=TEMPLATE_PATH)
    content = service.build_export_bytes(
        ResolvedOrderExport(
            converter_type="piton",
            client_code="100245",
            document_date=date(2026, 5, 14),
            fiche_no="0000000001",
            lines=[
                ExportLine(item_code="201300090081421071130040", item_name="Test product 1", quantity=4),
                ExportLine(item_code="ABC-2", item_name="Test product 2", quantity=12.5),
            ],
        )
    )

    template = openpyxl.load_workbook(TEMPLATE_PATH, data_only=False)
    workbook = openpyxl.load_workbook(BytesIO(content), data_only=False)
    template_sheet = template.active
    sheet = workbook.active

    assert workbook.sheetnames == template.sheetnames
    assert sheet.title == template_sheet.title
    assert [str(item) for item in sheet.merged_cells.ranges] == [
        str(item) for item in template_sheet.merged_cells.ranges
    ]
    assert [key for key, dim in sheet.column_dimensions.items() if dim.hidden] == ["F"]
    assert sheet.column_dimensions["A"].width == template_sheet.column_dimensions["A"].width
    assert sheet.column_dimensions["B"].width == template_sheet.column_dimensions["B"].width
    assert sheet["A1"].value == "CLIENT CODE"
    assert sheet["B1"].value == "100245"
    assert sheet["A2"].value == "DATE"
    assert sheet["B2"].number_format == template_sheet["B2"].number_format
    assert sheet["A3"].value == "WH NO"
    assert sheet["B3"].value == 1
    assert sheet["A4"].value == "FICHE NO"
    assert sheet["B4"].value == "0000000001"
    assert sheet["C5"].value == "Unit"
    assert sheet["E5"].value == "Unit Price (Tenge)"
    assert sheet["A6"].value == "201300090081421071130040"
    assert sheet["B6"].value == "Test product 1"
    assert sheet["C6"].value == 1
    assert sheet["D6"].value == 4
    assert sheet["A7"].value == "ABC-2"
    assert sheet["B7"].value == "Test product 2"
    assert sheet["C7"].value == 1
    assert sheet["D7"].value == 12.5
    assert sheet["E6"].value is None
    assert sheet["A6"].border.left.style == template_sheet["A6"].border.left.style
    assert sheet["D6"].fill.fill_type == template_sheet["D6"].fill.fill_type
    workbook.close()
    template.close()


def test_export_filename_is_operator_friendly() -> None:
    filename = ExportService().build_filename(
        ResolvedOrderExport(
            converter_type="asia_retail",
            client_code="120-31-4-04-2486",
            document_date=date(2026, 5, 14),
            fiche_no="0000000001",
            lines=[],
        )
    )

    assert re.fullmatch(r"AsiaRetail_zakaz_120-31-4-04-2486_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.xlsx", filename)


def test_export_order_uses_resolved_product_and_client(db_session: Session) -> None:
    order = _resolved_order(db_session, product_item_code="ERP-100", raw_barcode="9999999999999")
    db_session.flush()

    result = ExportService(template_path=TEMPLATE_PATH).export_order(
        db_session,
        order.id,
    )

    workbook = openpyxl.load_workbook(BytesIO(result.content), data_only=True)
    sheet = workbook.active
    assert sheet["B1"].value == "100245"
    assert sheet["A6"].value == "ERP-100"
    assert sheet["A6"].value != "9999999999999"
    assert sheet["B6"].value == "Resolved Product"
    assert sheet["D6"].value == 4
    assert order.status == OrderStatus.EXPORTED.value
    assert order.export_file_id is None
    assert result.filename.startswith("Piton_zakaz_100245_")
    workbook.close()


def test_export_blocks_needs_review_order(db_session: Session) -> None:
    order = _resolved_order(db_session, status=OrderStatus.NEEDS_REVIEW.value)
    db_session.flush()

    with pytest.raises(ValueError, match="status must be ready_to_export"):
        ExportService(template_path=TEMPLATE_PATH).export_order(db_session, order.id)


def test_export_blocks_unresolved_items(db_session: Session) -> None:
    order = _resolved_order(db_session)
    item = order.items[0]
    item.status = OrderItemStatus.UNRESOLVED.value
    item.product_id = None
    db_session.flush()

    with pytest.raises(ValueError, match="unresolved product"):
        ExportService(template_path=TEMPLATE_PATH).export_order(db_session, order.id)


def test_exported_order_can_be_regenerated(db_session: Session) -> None:
    order = _resolved_order(db_session, status=OrderStatus.EXPORTED.value)
    db_session.flush()

    result = ExportService(template_path=TEMPLATE_PATH).export_order(
        db_session,
        order.id,
    )

    workbook = openpyxl.load_workbook(BytesIO(result.content), data_only=True)
    assert workbook.active["B6"].value == "Resolved Product"
    workbook.close()


def test_export_blocks_order_without_client(db_session: Session) -> None:
    order = _resolved_order(db_session)
    order.client_id = None
    db_session.flush()

    with pytest.raises(ValueError, match="client is not resolved"):
        ExportService(template_path=TEMPLATE_PATH).export_order(db_session, order.id)


def test_export_blocks_product_without_item_code(db_session: Session) -> None:
    order = _resolved_order(db_session, product_item_code=None)
    db_session.flush()

    with pytest.raises(ValueError, match="unresolved product"):
        ExportService(template_path=TEMPLATE_PATH).export_order(db_session, order.id)


def _resolved_order(
    db_session: Session,
    *,
    status: str = OrderStatus.READY_TO_EXPORT.value,
    product_item_code: str | None = "ERP-100",
    raw_barcode: str = "4600000000000",
) -> Order:
    client = Client(
        client_code="100245",
        name="Resolved Client",
        normalized_name="resolvedclient",
        is_active=True,
    )
    product = Product(
        item_code=product_item_code,
        name="Resolved Product",
        is_active=True,
    )
    db_session.add_all([client, product])
    db_session.flush()

    order = Order(
        order_number="0000000001",
        converter_type="piton",
        converter_version="1.0.0",
        client_id=client.id,
        status=status,
        parsed_snapshot={"document_date": "2026-05-14"},
    )
    order.items.append(
        OrderItem(
            product_id=product.id,
            raw_barcode=raw_barcode,
            normalized_barcode=raw_barcode,
            raw_name="Raw Product",
            raw_item_code="RAW-100",
            item_code="RAW-100",
            quantity=Decimal("4"),
            row_number=6,
            status=OrderItemStatus.RESOLVED.value,
        )
    )
    db_session.add(order)
    return order
