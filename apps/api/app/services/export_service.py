from __future__ import annotations

import re
from collections import defaultdict
from copy import copy
from dataclasses import dataclass, replace
from datetime import date
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import openpyxl
from openpyxl.styles import Font
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CONVERTER_FILENAME_PREFIXES
from app.core.enums import OrderItemStatus, OrderStatus, ProcessingEventType
from app.models.order import Order, OrderItem, ProcessingEvent
from app.models.product import ProductTypeExportRule
from app.services.export_template import analyze_export_template
from app.utils.normalization import is_short_numeric_item_code, sanitize_filename_part


@dataclass(slots=True)
class ExportLine:
    item_code: str
    item_name: str | None
    quantity: float
    product_type: str | None = None
    unit: int | float = 1
    unit_price: float | None = None


@dataclass(slots=True)
class ExportProblemLine:
    row_number: int | None
    raw_item_code: str | None
    raw_barcode: str | None
    raw_name: str | None
    product_type: str | None
    quantity: float | None
    reason: str


@dataclass(slots=True)
class ResolvedOrderExport:
    converter_type: str
    client_code: str
    document_date: date
    fiche_no: str
    lines: list[ExportLine]
    problems: list[ExportProblemLine] | None = None
    product_type_filter: str | None = None
    sequence_number: int = 0


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

    def export_order(
        self,
        db: Session,
        order_id: int,
        user_id: int | None = None,
        *,
        product_type: str | None = None,
    ) -> GeneratedExport:
        order = db.get(Order, order_id)
        if order is None:
            raise ValueError("Order not found.")
        payload = self._payload_from_order(
            order,
            sequence_number=self._next_export_sequence_number(db),
            excluded_product_types=self._excluded_product_types(db),
            product_type_filter=product_type,
        )
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
            template_sheet = workbook[layout.sheet_name]
            lines_by_type: dict[str, list[ExportLine]] = defaultdict(list)
            for line in order.lines:
                lines_by_type[self._display_product_type(line.product_type)].append(line)

            grouped_lines = sorted(lines_by_type.items(), key=lambda item: item[0].casefold())
            worksheets = []
            keep_template_title = (
                len(grouped_lines) == 1
                and grouped_lines[0][0] == self._display_product_type(None)
                and not order.product_type_filter
            )
            for index, (product_type, lines) in enumerate(grouped_lines):
                worksheet = template_sheet if index == 0 else workbook.copy_worksheet(template_sheet)
                if not (index == 0 and keep_template_title):
                    existing_titles = [title for title in workbook.sheetnames if title != worksheet.title]
                    worksheet.title = self._unique_sheet_title(existing_titles, product_type)
                worksheets.append((worksheet, lines))

            for index, (worksheet, lines) in enumerate(worksheets):
                sheet_order = (
                    replace(order, fiche_no=self._fiche_no_for_sequence(order.sequence_number + index))
                    if len(worksheets) > 1
                    else order
                )
                self._write_export_sheet(worksheet, layout, sheet_order, lines)

            if order.problems:
                self._write_problem_sheet(workbook, order.problems)

            buffer = BytesIO()
            workbook.save(buffer)
            content = buffer.getvalue()
        finally:
            workbook.close()
        self.validate_export_bytes(content)
        return content

    def build_filename(self, order: ResolvedOrderExport) -> str:
        converter = self._filename_safe_text(
            self._filename_converter_prefix(order.converter_type),
            "Converter",
        )
        sequence = max(order.sequence_number, 0)
        suffix = ""
        if order.product_type_filter:
            suffix = f" {self._filename_safe_text(order.product_type_filter, 'type')}"
        export_date = order.document_date.isoformat()
        return f"{converter} zakaz {export_date} {sequence:04d}{suffix}.xlsx"

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

    def _payload_from_order(
        self,
        order: Order,
        *,
        sequence_number: int | None = None,
        excluded_product_types: set[str] | None = None,
        product_type_filter: str | None = None,
    ) -> ResolvedOrderExport:
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
        document_date = date.today()

        if order.client is None or not order.client.client_code:
            raise ValueError("Order is not ready to export: client is not resolved.")
        client_code = order.client.client_code

        lines: list[ExportLine] = []
        problems: list[ExportProblemLine] = []
        excluded_product_types = excluded_product_types or set()
        product_type_filter = product_type_filter.strip() if product_type_filter else None
        product_type_filter_key = product_type_filter.casefold() if product_type_filter else None
        for item in sorted(order.items, key=lambda row: row.row_number or 0):
            item_product_type = item.product.product_type if item.product else None
            item_product_type_key = (item_product_type or "").casefold()
            if product_type_filter_key and item_product_type_key != product_type_filter_key:
                continue
            if item.status == OrderItemStatus.SKIPPED.value:
                problems.append(self._problem_line(item, "Строка пропущена"))
                continue
            if item.status == OrderItemStatus.INVALID_QUANTITY.value:
                problems.append(self._problem_line(item, "Ошибка количества"))
                continue
            if item.status != OrderItemStatus.RESOLVED.value or item.product is None:
                problems.append(self._problem_line(item, "Товар не сопоставлен"))
                continue
            if item.product.exclude_from_export:
                problems.append(self._problem_line(item, "Товар исключен из Excel"))
                continue
            if not product_type_filter_key and item_product_type_key and item_product_type_key in excluded_product_types:
                problems.append(self._problem_line(item, "Тип исключен из общего Excel"))
                continue
            item_code = item.product.item_code
            if not item_code:
                problems.append(self._problem_line(item, "Нет номера товара для выгрузки"))
                continue
            if is_short_numeric_item_code(item_code, min_digits=3, max_digits=4):
                problems.append(self._problem_line(item, "Короткий номер товара 3-4 знака"))
                continue
            lines.append(
                ExportLine(
                    item_code=item_code,
                    item_name=self._item_name_for_export(item, item_code),
                    quantity=float(item.quantity),
                    product_type=item.product.product_type,
                )
            )

        if not lines:
            raise ValueError("Order has no exportable rows. Resolve or keep at least one product before export.")

        sequence = max(sequence_number if sequence_number is not None else order.id * 20, 0)
        return ResolvedOrderExport(
            converter_type=order.converter_type or "unknown",
            client_code=client_code,
            document_date=document_date,
            fiche_no=self._fiche_no_for_sequence(sequence),
            lines=lines,
            problems=problems,
            product_type_filter=product_type_filter,
            sequence_number=sequence,
        )

    @staticmethod
    def _next_export_sequence_number(db: Session) -> int:
        export_count = db.scalar(
            select(func.count(ProcessingEvent.id)).where(
                ProcessingEvent.event_type == ProcessingEventType.EXPORTED.value,
            )
        )
        return int(export_count or 0) * 20

    @staticmethod
    def _fiche_no_for_sequence(sequence: int) -> str:
        return f"KA{max(sequence, 0):010d}"

    @staticmethod
    def _excluded_product_types(db: Session) -> set[str]:
        return {
            rule.product_type.casefold()
            for rule in db.scalars(
                select(ProductTypeExportRule).where(ProductTypeExportRule.exclude_from_export.is_(True))
            )
            if rule.product_type
        }

    @staticmethod
    def _sorted_lines(lines: list[ExportLine]) -> list[ExportLine]:
        return sorted(lines, key=lambda line: ExportService._item_code_sort_key(line.item_code))

    @staticmethod
    def _item_code_sort_key(item_code: str) -> tuple[int, int | str, str]:
        code = item_code.strip()
        if code.isdigit():
            return (0, int(code), code)
        return (1, code.casefold(), code)

    @staticmethod
    def _write_export_sheet(worksheet, layout, order: ResolvedOrderExport, lines: list[ExportLine]) -> None:
        worksheet[layout.service_cells["client_code"]] = order.client_code
        worksheet[layout.service_cells["document_date"]] = order.document_date
        if worksheet[layout.service_cells["document_date"]].number_format == "General":
            worksheet[layout.service_cells["document_date"]].number_format = "dd/mm/yyyy"
        worksheet[layout.service_cells["warehouse_no"]] = 1
        worksheet[layout.service_cells["fiche_no"]] = order.fiche_no

        start_row = layout.data_start_row
        row_end = max(worksheet.max_row, start_row + len(lines) - 1)
        template_styles = {
            col: copy(worksheet.cell(start_row, col)._style)
            for col in layout.data_style_columns
        }
        template_row_height = worksheet.row_dimensions[start_row].height
        clearable_columns = set(layout.clearable_columns)
        if layout.unit_price_col is not None and any(line.unit_price is not None for line in lines):
            clearable_columns.add(layout.unit_price_col)

        for row in range(start_row, row_end + 1):
            for col in clearable_columns:
                worksheet.cell(row, col).value = None

        for offset, line in enumerate(ExportService._sorted_lines(lines)):
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

    @staticmethod
    def _write_problem_sheet(workbook, problems: list[ExportProblemLine]) -> None:
        worksheet = workbook.create_sheet("Проблемные")
        headers = [
            "Строка",
            "Код сети",
            "Штрихкод",
            "Наименование",
            "Тип",
            "Количество",
            "Причина",
        ]
        worksheet.append(headers)
        for problem in problems:
            worksheet.append(
                [
                    problem.row_number,
                    problem.raw_item_code,
                    problem.raw_barcode,
                    problem.raw_name,
                    problem.product_type,
                    problem.quantity,
                    problem.reason,
                ]
            )
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
        widths = [10, 22, 18, 48, 18, 14, 32]
        for index, width in enumerate(widths, start=1):
            worksheet.column_dimensions[openpyxl.utils.get_column_letter(index)].width = width
        worksheet.freeze_panes = "A2"

    @staticmethod
    def _problem_line(item: OrderItem, reason: str) -> ExportProblemLine:
        return ExportProblemLine(
            row_number=item.row_number,
            raw_item_code=item.raw_item_code,
            raw_barcode=item.raw_barcode,
            raw_name=item.raw_name,
            product_type=item.product.product_type if item.product else None,
            quantity=float(item.quantity) if item.quantity is not None else None,
            reason=reason,
        )

    @staticmethod
    def _display_product_type(value: str | None) -> str:
        text = (value or "").strip()
        return text or "Без типа"

    @staticmethod
    def _unique_sheet_title(existing_titles: list[str], title: str) -> str:
        cleaned = re.sub(r"[\[\]:*?/\\]", "_", title).strip() or "Sheet"
        cleaned = cleaned[:31]
        existing = {item.casefold() for item in existing_titles}
        if cleaned.casefold() not in existing:
            return cleaned
        counter = 2
        while True:
            suffix = f" {counter}"
            candidate = f"{cleaned[:31 - len(suffix)]}{suffix}"
            if candidate.casefold() not in existing:
                return candidate
            counter += 1

    @staticmethod
    def _filename_safe_text(value: str, fallback: str) -> str:
        text = sanitize_filename_part(value, fallback).replace("_", " ")
        return re.sub(r"\s+", " ", text).strip() or fallback

    @staticmethod
    def _item_name_for_export(item: OrderItem, fallback_code: str) -> str:
        product_name = (item.product.name or "").strip() if item.product is not None else ""
        if product_name:
            return product_name
        raw_name = (item.raw_name or "").strip()
        return raw_name or fallback_code
