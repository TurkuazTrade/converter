from __future__ import annotations

from pathlib import Path

import pytest

from app.services.converter_registry_service import ConverterRegistryService

SAMPLES_DIR = Path("/Users/niiazovmaksat/Downloads/Bishkek converter 2026 — копия/почтадан келген заказдар")

SAMPLES = {
    "piton": "Питон.xlsx",
    "narodnyi": "Народный заказ почта.xls",
    "globus": "Глобус заказ почта.xls",
    "spar": "SPAR заказ почта.xls",
    "dostor": "Достор - заказ почта.xlsx",
    "asia_retail": "Азия Ритейл заказ почта.xls",
    "darkstore": "Даркстор заказ почта.xlsx",
    "alma": "Алма заказ почта.xls",
}


@pytest.mark.parametrize(("converter_type", "filename"), SAMPLES.items())
def test_real_order_sample_parses(converter_type: str, filename: str) -> None:
    path = SAMPLES_DIR / filename
    if not path.exists():
        pytest.skip(f"Real sample not available: {filename}")

    parsed = ConverterRegistryService().get_converter(converter_type).parse(path)

    assert parsed.items
    assert parsed.document_no
    assert parsed.document_date
    assert parsed.client_hint.raw_name
    assert parsed.parser_metadata["converter_type"] == converter_type
    assert any(item.normalized_barcode or item.raw_item_code for item in parsed.items)
    assert all(item.quantity is None or item.quantity > 0 for item in parsed.items)
    assert all(item.row_number for item in parsed.items)
