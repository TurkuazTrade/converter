from __future__ import annotations

from pathlib import Path

from tests.helpers.export_template_analysis import analyze_template


def test_template_zakaz_structure_is_detected() -> None:
    template = Path("../data/templates/template_zakaz.xlsx").resolve()
    analysis = analyze_template(template)

    assert analysis["sheet_names"] == ["1"]
    assert analysis["active_sheet"] == "1"
    assert analysis["service_cells"] == {
        "client_code": "B1",
        "document_date": "B2",
        "warehouse_no": "B3",
        "fiche_no": "B4",
    }
    assert analysis["data_start_row"] == 6
    assert analysis["columns"] == {
        "item_code": "A",
        "item_name": "B",
        "unit": "C",
        "quantity": "D",
        "unit_price": "E",
    }
    assert analysis["active_columns"] == ["A", "B", "C", "D"]
    assert analysis["data_style_columns"] == ["A", "B", "C", "D"]
    assert analysis["merged_ranges"] == []
    assert analysis["hidden_columns"] == ["F"]
    assert analysis["formulas"] == []
