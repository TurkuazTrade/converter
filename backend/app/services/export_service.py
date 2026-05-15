from __future__ import annotations

import re
from copy import copy
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import openpyxl
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CONVERTER_FILENAME_PREFIXES
from app.core.enums import OrderItemStatus, OrderStatus, ProcessingEventType
from app.models.order import Order, ProcessingEvent
from app.services.export_template import analyze_export_template
from app.utils.normalization import sanitize_filename_part


@dataclass(slots=True)
class ExportLine:
    item_code: str
    item_name: str | None
    quantity: float
    unit: int | float = 1
    unit_price: float | None = None


@dataclass(slots=True)
class ResolvedOrderExport:
    converter_type: str
    client_code: str
    document_date: date
    fiche_no: str
    lines: list[ExportLine]


@dataclass(slots=True)
class GeneratedExport:
    filename: str
    content: bytes
    mime_type: str
    size: int
    sha256: str


class ExportService:
    """Template-preserving export service."""

    def __init__(
        self,
        template_path: Path | None = None,
    ) -> None:
        self.template_path = template_path or settings.template_path

    def export_order(self, db: Session, order_id: int, user_id: int | None = None) -> GeneratedExport:
        order = db.get(Order, order_id)
        if order is None:
            raise ValueError("Order not found.")
        payload = self._payload_from_order(order)
        content = self.build_export_bytes(payload)
        filename = self.build_filename(payload)
        result = GeneratedExport(
            filename=filename,
            content=content,
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size=len(content),
            sha256=sha256(content).hexdigest(),
        )
        order.status = OrderStatus.EXPORTED.value
        order.export_file_id = None
        order.error_message = None
        db.add(
            ProcessingEvent(
                order_id=order.id,
                event_type=ProcessingEventType.EXPORTED.value,
                message="Export workbook generated on demand.",
                payload={"filename": result.filename, "size": result.size, "sha256": result.sha256},
                created_by_id=user_id,
            )
        )
        return result

    def build_export_bytes(self, order: ResolvedOrderExport) -> bytes:
        workbook = openpyxl.load_workbook(self.template_path)
        try:
            layout = analyze_export_template(workbook)
            worksheet = workbook[layout.sheet_name]

            worksheet[layout.service_cells["client_code"]] = order.client_code
            worksheet[layout.service_cells["document_date"]] = order.document_date
            if worksheet[layout.service_cells["document_date"]].number_format == "General":
                worksheet[layout.service_cells["document_date"]].number_format = "dd/mm/yyyy"
            worksheet[layout.service_cells["warehouse_no"]] = 1
            worksheet[layout.service_cells["fiche_no"]] = order.fiche_no

            start_row = layout.data_start_row
            row_end = max(worksheet.max_row, start_row + len(order.lines) - 1)
            template_styles = {
                col: copy(worksheet.cell(start_row, col)._style)
                for col in layout.data_style_columns
            }
            template_row_height = worksheet.row_dimensions[start_row].height
            clearable_columns = set(layout.clearable_columns)
            if layout.unit_price_col is not None and any(line.unit_price is not None for line in order.lines):
                clearable_columns.add(layout.unit_price_col)

            for row in range(start_row, row_end + 1):
                for col in clearable_columns:
                    worksheet.cell(row, col).value = None

            for offset, line in enumerate(order.lines):
                row = start_row + offset
                if template_row_height is not None:
                    worksheet.row_dimensions[row].height = template_row_height
                for col, style in template_styles.items():
                    worksheet.cell(row, col)._style = copy(style)
                worksheet.cell(row, layout.item_code_col).value = line.item_code
                if layout.item_name_col is not None:
                    worksheet.cell(row, layout.item_name_col).value = line.item_name or line.item_code
                if layout.unit_col is not None:
                    worksheet.cell(row, layout.unit_col).value = line.unit
                worksheet.cell(row, layout.quantity_col).value = line.quantity
                if layout.unit_price_col is not None and line.unit_price is not None:
                    worksheet.cell(row, layout.unit_price_col).value = line.unit_price

            buffer = BytesIO()
            workbook.save(buffer)
            content = buffer.getvalue()
        finally:
            workbook.close()
        self.validate_export_bytes(content)
        return content

    def build_filename(self, order: ResolvedOrderExport) -> str:
        converter = sanitize_filename_part(self._filename_converter_prefix(order.converter_type), "Converter")
        return f"{converter} zakaz 01.xlsx"

    @staticmethod
    def _filename_converter_prefix(converter_type: str) -> str:
        key = converter_type.strip().casefold()
        if key in CONVERTER_FILENAME_PREFIXES:
            return CONVERTER_FILENAME_PREFIXES[key]
        parts = [part for part in re.split(r"[^0-9A-Za-zА-Яа-я]+", converter_type.strip()) if part]
        if not parts:
            return "Converter"
        return "".join(part[:1].upper() + part[1:] for part in parts)

    @staticmethod
    def validate_export_bytes(content: bytes) -> None:
        workbook = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
        workbook.close()

    def _payload_from_order(self, order: Order) -> ResolvedOrderExport:
        allowed_statuses = {
            OrderStatus.NEEDS_REVIEW.value,
            OrderStatus.READY_TO_EXPORT.value,
            OrderStatus.EXPORTED.value,
        }
        if order.status not in allowed_statuses:
            raise ValueError(
                f"Order is not ready to export: status must be {OrderStatus.READY_TO_EXPORT.value} "
                f"or {OrderStatus.NEEDS_REVIEW.value}, "
                f"got {order.status}."
            )
        snapshot = order.parsed_snapshot or {}
        document_date = date.today()
        if snapshot.get("document_date"):
            document_date = date.fromisoformat(snapshot["document_date"])

        if order.client is None or not order.client.client_code:
            raise ValueError("Order is not ready to export: client is not resolved.")
        client_code = order.client.client_code

        lines: list[ExportLine] = []
        for item in sorted(order.items, key=lambda row: row.row_number or 0):
            if item.status == OrderItemStatus.SKIPPED.value:
                continue
            if item.status == OrderItemStatus.INVALID_QUANTITY.value:
                continue
            if item.status != OrderItemStatus.RESOLVED.value or item.product is None:
                continue
            item_code = item.product.item_code
            if not item_code:
                continue
            lines.append(
                ExportLine(
                    item_code=item_code,
                    item_name=self._item_name_from_source(item),
                    quantity=float(item.quantity),
                )
            )

        if not lines:
            raise ValueError("Order has no exportable rows. Resolve or keep at least one product before export.")

        return ResolvedOrderExport(
            converter_type=order.converter_type or "unknown",
            client_code=client_code,
            document_date=document_date,
            fiche_no=order.order_number or f"{order.id:010d}",
            lines=lines,
        )

    @staticmethod
    def _item_name_from_source(item) -> str | None:
        raw_name = (item.raw_name or "").strip()
        if raw_name:
            return raw_name
        if item.product is not None and item.product.name:
            return item.product.name
        return item.product.item_code if item.product is not None else item.item_code
