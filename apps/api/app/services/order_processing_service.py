from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import FileRole, OrderItemStatus, OrderStatus, ProcessingEventType
from app.models.file import File
from app.models.order import Order, OrderItem, ProcessingEvent
from app.repositories.orders import OrderRepository
from app.services.converter_registry_service import ConverterRegistryService
from app.services.matching_service import MatchingService
from app.services.storage_service import LocalStorageService, StoredObject
from app.utils.excel_reader import read_workbook
from app.utils.normalization import normalize_text


class OrderProcessingService:
    def __init__(
        self,
        db: Session,
        storage: LocalStorageService | None = None,
        registry: ConverterRegistryService | None = None,
    ) -> None:
        self.db = db
        self.storage = storage or LocalStorageService()
        self.registry = registry or ConverterRegistryService()

    async def upload_order(
        self,
        upload_file,
        user_id: int | None,
        converter_type: str | None = None,
        force: bool = False,
    ) -> tuple[Order | None, bool, int | None, str]:
        stored = await self.storage.save_source(upload_file, user_id=user_id)
        existing = OrderRepository(self.db).find_by_source_hash(stored.sha256)
        if existing and not force and self._should_reuse_duplicate(existing, converter_type):
            self._discard_source_if_needed(stored)
            self._event(
                existing.id,
                ProcessingEventType.DUPLICATE_DETECTED.value,
                "Duplicate upload detected.",
                {"filename": stored.original_name, "sha256": stored.sha256},
                user_id,
            )
            return None, True, existing.id, "This file was already uploaded."

        file_row = self._persist_file(stored, user_id)
        detected = converter_type or self._detect_converter(stored)
        order = Order(
            converter_type=detected,
            converter_version=None,
            converter_config_hash=None,
            uploaded_by_id=user_id,
            source_file_id=file_row.id,
            status=OrderStatus.PROCESSING.value,
            source_hash=stored.sha256,
            parsed_snapshot=None,
            duplicate_of_order_id=existing.id if existing else None,
        )
        self.db.add(order)
        self.db.flush()
        self._event(
            order.id,
            ProcessingEventType.UPLOADED.value,
            "Source file uploaded.",
            {"filename": stored.original_name, "sha256": stored.sha256},
            user_id,
        )

        try:
            converter = self.registry.get_converter(detected)
            parsed = converter.parse(Path(stored.path))
            order.converter_type = parsed.parser_metadata.get("converter_type", detected)
            order.converter_version = parsed.parser_metadata.get("converter_version")
            order.converter_config_hash = parsed.parser_metadata.get("config_hash")
            order.order_number = parsed.document_no
            order.parsed_snapshot = parsed.snapshot()
            order.items.clear()
            self.db.flush()
            for parsed_item in parsed.items:
                order.items.append(
                    OrderItem(
                        raw_barcode=parsed_item.raw_barcode,
                        normalized_barcode=parsed_item.normalized_barcode,
                        raw_name=parsed_item.raw_name,
                        normalized_name=parsed_item.normalized_name,
                        raw_item_code=parsed_item.raw_item_code,
                        item_code=parsed_item.raw_item_code or parsed_item.normalized_barcode,
                        source_quantity=parsed_item.quantity or Decimal("0"),
                        conversion_multiplier=Decimal("1"),
                        quantity=parsed_item.quantity or Decimal("0"),
                        row_number=parsed_item.row_number,
                        status=(
                            OrderItemStatus.INVALID_QUANTITY.value
                            if parsed_item.quantity is None or parsed_item.quantity <= 0
                            else OrderItemStatus.UNRESOLVED.value
                        ),
                        error_message=(
                            "Invalid quantity."
                            if parsed_item.quantity is None or parsed_item.quantity <= 0
                            else None
                        ),
                        source_payload=parsed_item.source_payload,
                    )
                )
            self.db.flush()
            self._event(
                order.id,
                ProcessingEventType.PARSED.value,
                f"Parsed {len(parsed.items)} order rows.",
                {"warnings": parsed.warnings, "sheet": parsed.sheet_name},
                user_id,
            )
            MatchingService(self.db).match_order(order.id)
            unresolved_count = sum(
                1
                for item in order.items
                if item.status
                in {OrderItemStatus.UNRESOLVED.value, OrderItemStatus.INVALID_QUANTITY.value}
            )
            client_unresolved = order.client_id is None
            order.status = (
                OrderStatus.NEEDS_REVIEW.value
                if unresolved_count or client_unresolved
                else OrderStatus.READY_TO_EXPORT.value
            )
            order.error_message = (
                self._review_message(unresolved_count, client_unresolved)
                if order.status == OrderStatus.NEEDS_REVIEW.value
                else None
            )
            self._event(
                order.id,
                ProcessingEventType.MATCHED.value,
                "Matching completed.",
                {"unresolved_count": unresolved_count, "client_unresolved": client_unresolved},
                user_id,
            )
            self._discard_source_if_needed(stored, file_row)
            return order, False, existing.id if existing else None, "Order processed."
        except Exception as exc:
            order.status = OrderStatus.FAILED.value
            order.error_message = str(exc)
            self._event(
                order.id,
                ProcessingEventType.FAILED.value,
                "Order processing failed.",
                {"error": str(exc)},
                user_id,
            )
            self._discard_source_if_needed(stored, file_row)
            return order, False, existing.id if existing else None, f"Order processing failed: {exc}"

    def reprocess_order(self, order_id: int, user_id: int | None = None) -> Order:
        order = OrderRepository(self.db).get(order_id)
        if order is None:
            raise ValueError("Order not found.")
        if order.source_file is None:
            raise ValueError("Order has no source file.")
        if not order.source_file.path or not Path(order.source_file.path).exists():
            raise ValueError("Source file is not retained. Use rematch_only from parsed snapshot.")
        detected = order.converter_type or self._detect_converter_from_name(order.source_file.original_name)
        converter = self.registry.get_converter(detected)
        parsed = converter.parse(Path(order.source_file.path))
        order.status = OrderStatus.PROCESSING.value
        order.error_message = None
        order.converter_type = parsed.parser_metadata.get("converter_type", detected)
        order.converter_version = parsed.parser_metadata.get("converter_version")
        order.converter_config_hash = parsed.parser_metadata.get("config_hash")
        order.order_number = parsed.document_no
        order.parsed_snapshot = parsed.snapshot()
        order.items.clear()
        self.db.flush()
        for parsed_item in parsed.items:
            order.items.append(
                OrderItem(
                    raw_barcode=parsed_item.raw_barcode,
                    normalized_barcode=parsed_item.normalized_barcode,
                    raw_name=parsed_item.raw_name,
                    normalized_name=parsed_item.normalized_name,
                    raw_item_code=parsed_item.raw_item_code,
                    item_code=parsed_item.raw_item_code or parsed_item.normalized_barcode,
                    source_quantity=parsed_item.quantity or Decimal("0"),
                    conversion_multiplier=Decimal("1"),
                    quantity=parsed_item.quantity or Decimal("0"),
                    row_number=parsed_item.row_number,
                    source_payload=parsed_item.source_payload,
                )
            )
        self.db.flush()
        MatchingService(self.db).match_order(order.id)
        unresolved_count = sum(
            1
            for item in order.items
            if item.status in {OrderItemStatus.UNRESOLVED.value, OrderItemStatus.INVALID_QUANTITY.value}
        )
        client_unresolved = order.client_id is None
        order.status = (
            OrderStatus.NEEDS_REVIEW.value
            if unresolved_count or client_unresolved
            else OrderStatus.READY_TO_EXPORT.value
        )
        order.error_message = (
            self._review_message(unresolved_count, client_unresolved)
            if order.status == OrderStatus.NEEDS_REVIEW.value
            else None
        )
        self._event(
            order.id,
            ProcessingEventType.REPROCESSED.value,
            "Order reprocessed from source file.",
            {"unresolved_count": unresolved_count, "client_unresolved": client_unresolved},
            user_id,
        )
        return order

    def _detect_converter(self, stored: StoredObject) -> str:
        detected = self.registry.detect_converter(stored.original_name)
        if detected is not None and detected.value != "alma":
            return detected.value
        preview_text = self._preview_text(Path(stored.path))
        detected = self.registry.detect_converter(stored.original_name, preview_text=preview_text)
        if detected is not None:
            return detected.value
        return self._detect_converter_from_content(Path(stored.path)) or self._detect_converter_from_name(
            stored.original_name
        )

    def _detect_converter_from_name(self, filename: str) -> str:
        detected = self.registry.detect_converter(filename)
        return detected.value if detected else "narodnyi"

    def _detect_converter_from_content(self, path: Path) -> str | None:
        valid: list[str] = []
        for config in self.registry.list_configs():
            converter_type = str(config["type"])
            try:
                self.registry.get_converter(converter_type).validate(path)
            except Exception:
                continue
            valid.append(converter_type)
        return valid[0] if len(valid) == 1 else None

    @staticmethod
    def _preview_text(path: Path, max_rows: int = 12) -> str:
        try:
            sheets = read_workbook(path, data_only=True)
        except Exception:
            return ""
        parts: list[str] = []
        for sheet in sheets:
            parts.append(sheet.name)
            for row_index, row in sheet.visible_rows():
                if row_index > max_rows:
                    break
                for value in row:
                    text = normalize_text(value)
                    if text:
                        parts.append(text)
        return " ".join(parts)

    @staticmethod
    def _should_reuse_duplicate(existing: Order, requested_converter_type: str | None) -> bool:
        if existing.status == OrderStatus.FAILED.value:
            return False
        if requested_converter_type and existing.converter_type != requested_converter_type:
            return False
        return True

    def _persist_file(self, stored: StoredObject, user_id: int | None) -> File:
        file_row = File(
            original_name=stored.original_name,
            stored_name=stored.stored_name,
            storage_backend=stored.storage_backend.value,
            path=stored.path,
            mime_type=stored.mime_type,
            size=stored.size,
            sha256=stored.sha256,
            file_role=stored.file_role.value if isinstance(stored.file_role, FileRole) else str(stored.file_role),
            uploaded_by_id=user_id,
        )
        self.db.add(file_row)
        self.db.flush()
        return file_row

    def _discard_source_if_needed(self, stored: StoredObject, file_row: File | None = None) -> None:
        if settings.retain_source_files:
            return
        self.storage.delete(stored.path)
        if file_row is not None:
            file_row.path = ""
            file_row.stored_name = ""

    def _event(
        self,
        order_id: int,
        event_type: str,
        message: str,
        payload: dict | None,
        user_id: int | None,
    ) -> None:
        self.db.add(
            ProcessingEvent(
                order_id=order_id,
                event_type=event_type,
                message=message,
                payload=payload,
                created_by_id=user_id,
            )
        )

    @staticmethod
    def _review_message(unresolved_count: int, client_unresolved: bool) -> str:
        parts: list[str] = []
        if client_unresolved:
            parts.append("Client is not resolved.")
        if unresolved_count:
            parts.append(f"{unresolved_count} order item(s) are unresolved or invalid.")
        return " ".join(parts)
