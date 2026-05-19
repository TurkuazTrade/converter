from __future__ import annotations

import openpyxl
import pytest
from sqlalchemy.orm import Session

from app.core.enums import FileRole, OrderStatus
from app.models.order import Order
from app.services.order_processing_service import OrderProcessingService
from app.services.storage_service import StoredObject


class FakeStorage:
    def __init__(self, stored: StoredObject) -> None:
        self.stored = stored
        self.deleted: list[str] = []

    async def save_source(self, upload_file, user_id: int | None = None) -> StoredObject:
        return self.stored

    def delete(self, storage_path: str) -> None:
        self.deleted.append(storage_path)


@pytest.mark.asyncio
async def test_selected_converter_reprocesses_failed_duplicate(tmp_path, db_session: Session) -> None:
    path = tmp_path / "fr-12.xlsx"
    _write_asia_retail_order(path)
    stored = StoredObject(
        original_name="fr-12.xlsx",
        stored_name="fr-12.xlsx",
        path=str(path),
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        size=path.stat().st_size,
        sha256="same-file",
        file_role=FileRole.SOURCE,
    )
    failed = Order(
        converter_type="narodnyi",
        status=OrderStatus.FAILED.value,
        source_hash="same-file",
        error_message="Required columns not found: barcode, item_name, quantity",
    )
    db_session.add(failed)
    db_session.flush()

    order, duplicate, existing_order_id, message = await OrderProcessingService(
        db_session,
        storage=FakeStorage(stored),
    ).upload_order(
        upload_file=object(),
        user_id=None,
        converter_type="asia_retail",
    )

    assert duplicate is False
    assert existing_order_id == failed.id
    assert order is not None
    assert order.id != failed.id
    assert order.converter_type == "asia_retail"
    assert order.status != OrderStatus.FAILED.value
    assert len(order.items) == 1
    assert "processed" in message


def _write_asia_retail_order(path) -> None:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Заявка"
    worksheet.append(
        [
            "Вид документа",
            "Дата",
            "Номер",
            "Код обмена контрагент",
            "Контрагент",
            "Подразделение",
            "Код товара",
            "Товар",
            "Штрихкод",
            "Количество",
            "Цена",
            "Сумма",
            "Номер товара",
            "Номер контрагент",
        ]
    )
    worksheet.append(
        [
            "Заявки",
            "15.05.2026",
            "ЦБ00309246",
            "",
            'ЗАО "Азия Ритейл"',
            "Гипермаркет 12",
            "",
            "МЫЛО ТУАЛЕТНОЕ DALAN",
            "8690529522897",
            12,
            58,
            696,
            "203150105380107012200024",
            "",
        ]
    )
    workbook.save(path)
    workbook.close()
