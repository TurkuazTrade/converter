from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.converters.base import BaseConverter, ParsedClientHint, ParsedItem, ParsedOrder
from app.utils.excel_reader import SheetData, read_workbook
from app.utils.normalization import (
    is_short_numeric_item_code,
    normalize_barcode,
    normalize_item_code,
    normalize_key,
    normalize_text,
    parse_date,
    parse_decimal,
)


@dataclass(slots=True)
class HeaderMatch:
    sheet: SheetData
    header_row: int
    columns: dict[str, int]


class ConfigDrivenConverter(BaseConverter):
    """Config-driven parser for the current network order formats."""

    def __init__(self, config: dict, config_hash: str) -> None:
        self.config = config
        self.config_hash = config_hash
        self.converter_type = str(config["type"])
        self.converter_version = str(config["version"])
        self._sheets: list[SheetData] | None = None

    def detect(self, path: Path) -> bool:
        name = path.name.casefold()
        aliases = self.config.get("sheet", {}).get("name_aliases", [])
        return self.converter_type in name or any(str(alias).casefold() in name for alias in aliases)

    def validate(self, path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(path)
        self._find_header(path)

    def parse(self, path: Path) -> ParsedOrder:
        self.validate(path)
        match = self._find_header(path)
        first_data = self._first_data_row(match)
        document_no = self._document_no(match, first_data, path)
        document_date = self._document_date(match, first_data)
        warehouse_no = self._warehouse_no(match, first_data)
        client_hint = self._client_hint(match, first_data)
        items = self._parse_items(match)
        if not items:
            raise ValueError("No order rows with positive quantity were found.")
        items, duplicate_warnings = self._aggregate_duplicate_items(items)

        return ParsedOrder(
            document_no=document_no,
            document_date=document_date,
            warehouse_no=warehouse_no,
            sheet_name=match.sheet.name,
            header_row=match.header_row,
            client_hint=client_hint,
            items=items,
            warnings=duplicate_warnings,
            parser_metadata={
                "converter_type": self.converter_type,
                "converter_version": self.converter_version,
                "config_hash": self.config_hash,
            },
        )

    def normalize(self, parsed_order: ParsedOrder) -> ParsedOrder:
        return parsed_order

    def extract_client_hint(self, path: Path) -> ParsedClientHint:
        match = self._find_header(path)
        return self._client_hint(match, self._first_data_row(match))

    def extract_items(self, path: Path) -> list[ParsedItem]:
        return self._parse_items(self._find_header(path))

    def _load_sheets(self, path: Path) -> list[SheetData]:
        if self._sheets is None:
            self._sheets = read_workbook(path, data_only=True)
        return self._sheets

    def _find_header(self, path: Path) -> HeaderMatch:
        search_rows = int(self.config.get("header", {}).get("search_rows", 30))
        required = set(self.config.get("header", {}).get("required", []))
        candidates = self._candidate_sheets(path)
        for sheet in candidates:
            for row_index, row in sheet.visible_rows():
                if row_index > search_rows:
                    break
                columns = self._match_columns(row)
                if required.issubset(columns):
                    return HeaderMatch(sheet=sheet, header_row=row_index, columns=columns)
        required_text = ", ".join(sorted(required)) or "any configured column"
        raise ValueError(f"Required columns not found: {required_text}")

    def _candidate_sheets(self, path: Path) -> list[SheetData]:
        sheets = self._load_sheets(path)
        aliases = [
            normalize_key(alias)
            for alias in self.config.get("sheet", {}).get("name_aliases", [])
        ]
        if not aliases:
            return sheets
        preferred = [sheet for sheet in sheets if normalize_key(sheet.name) in aliases]
        return preferred or sheets

    def _match_columns(self, row: list[Any]) -> dict[str, int]:
        normalized_cells = [normalize_key(cell) for cell in row]
        result: dict[str, int] = {}
        for semantic_name, aliases in self.config.get("columns", {}).items():
            if isinstance(aliases, dict):
                fallback_index = aliases.get("fallback_index")
                if isinstance(fallback_index, int):
                    result[semantic_name] = fallback_index
                continue
            for alias in aliases:
                alias_key = normalize_key(alias)
                for index, cell_key in enumerate(normalized_cells):
                    if cell_key and cell_key == alias_key:
                        result[semantic_name] = index
                        break
                if semantic_name in result:
                    break
        return result

    @staticmethod
    def _cell(row: list[Any] | None, index: int | None) -> Any:
        if row is None or index is None or index >= len(row):
            return None
        return row[index]

    @staticmethod
    def _scan_text(sheet: SheetData, max_rows: int = 15) -> str:
        parts: list[str] = []
        for row_index, row in sheet.visible_rows():
            if row_index > max_rows:
                break
            for value in row:
                text = normalize_text(value)
                if text:
                    parts.append(text)
        return " ".join(parts)

    @staticmethod
    def _first_match(pattern: str, text: str, default: str = "") -> str:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.UNICODE)
        return normalize_text(match.group(1)) if match else default

    def _first_data_row(self, match: HeaderMatch) -> tuple[int, list[Any]] | None:
        for row_index, row in match.sheet.visible_rows():
            if row_index > match.header_row:
                return row_index, row
        return None

    def _document_no(
        self,
        match: HeaderMatch,
        first_data: tuple[int, list[Any]] | None,
        path: Path,
    ) -> str:
        row = first_data[1] if first_data else None
        from_column = normalize_text(self._cell(row, match.columns.get("document_no")))
        if from_column:
            return from_column
        text = self._scan_text(match.sheet)
        return self._first_match(r"№\s*:?\s*([A-ZА-Я0-9\-_/]+)", text, path.stem) or path.stem

    def _document_date(
        self,
        match: HeaderMatch,
        first_data: tuple[int, list[Any]] | None,
    ) -> date:
        row = first_data[1] if first_data else None
        from_column = self._cell(row, match.columns.get("document_date"))
        if from_column not in (None, ""):
            return parse_date(from_column, default=date.today())
        text = self._scan_text(match.sheet, max_rows=20)
        matches = re.findall(r"\d{2}[.\-]\d{2}[.\-]\d{4}(?:\s+\d{2}:\d{2}:\d{2})?", text)
        if matches:
            return parse_date(matches[-1 if self.converter_type == "alma" else 0], default=date.today())
        return date.today()

    def _warehouse_no(
        self,
        match: HeaderMatch,
        first_data: tuple[int, list[Any]] | None,
    ) -> str | None:
        row = first_data[1] if first_data else None
        return normalize_item_code(self._cell(row, match.columns.get("warehouse_no"))) or None

    def _client_hint(
        self,
        match: HeaderMatch,
        first_data: tuple[int, list[Any]] | None,
    ) -> ParsedClientHint:
        row = first_data[1] if first_data else None
        client_code = normalize_item_code(self._cell(row, match.columns.get("client_code")))
        client_name = normalize_text(self._cell(row, match.columns.get("client_name")))
        branch = normalize_text(self._cell(row, match.columns.get("client_branch")))
        if branch:
            client_name = f"{client_name}, {branch}" if client_name else branch
        metadata = self.config.get("metadata", {})

        if not client_name:
            for candidate in metadata.get("client_cell_candidates", []):
                value = self._cell_by_a1(match.sheet, candidate)
                if value:
                    client_name = normalize_text(value)
                    break

        text = self._scan_text(match.sheet, max_rows=20)
        if not client_name and metadata.get("client_text_prefix") == "Покупатель:":
            client_name = self._first_match(
                r"Покупатель:\s*(.+?)(?:\s+Адрес|\s+№|\s*$)",
                text,
                "",
            )
        if not client_name and metadata.get("client_text_prefix") == "Заказ на":
            client_name = self._first_match(
                r"Заказ на\s+(.+?)(?:\s+Адрес|\s+тел|\s*$)",
                text,
                "",
            )
        if not client_name and metadata.get("client_row_prefix") == "Склад":
            client_name = self._alma_client(match.sheet)
        if not client_name:
            client_name = self.converter_type

        return ParsedClientHint(
            raw_name=client_name,
            raw_address=self._first_match(r"Адрес(?: доставки)?:\s*(.+?)(?:\s+тел|\s+График|\s*$)", text, ""),
            client_code=client_code,
            payload={"source": "config_driven"},
        )

    @staticmethod
    def _cell_by_a1(sheet: SheetData, address: str) -> Any:
        match = re.fullmatch(r"([A-Za-z]+)(\d+)", address.strip())
        if not match:
            return None
        letters, row_text = match.groups()
        row_index = int(row_text) - 1
        col_index = 0
        for char in letters.upper():
            col_index = col_index * 26 + (ord(char) - ord("A") + 1)
        col_index -= 1
        if row_index < 0 or row_index >= len(sheet.rows):
            return None
        row = sheet.rows[row_index]
        if col_index < 0 or col_index >= len(row):
            return None
        return row[col_index]

    @staticmethod
    def _alma_client(sheet: SheetData) -> str:
        for row_index, row in sheet.visible_rows():
            if row_index < 8 or row_index > 20:
                continue
            text = " ".join(normalize_text(value) for value in row if normalize_text(value))
            if text.casefold().startswith("склад"):
                return text
        return "Алма"

    def _parse_items(self, match: HeaderMatch) -> list[ParsedItem]:
        items: list[ParsedItem] = []
        filters = self.config.get("filters", {})
        skip_zero = bool(filters.get("skip_zero_quantity", True))
        skip_short_numeric_item_codes = bool(filters.get("skip_short_numeric_item_codes", False))
        for row_index, row in match.sheet.visible_rows():
            if row_index <= match.header_row:
                continue
            item_code = normalize_item_code(self._cell(row, match.columns.get("item_code")))
            barcode = normalize_barcode(self._cell(row, match.columns.get("barcode")))
            item_name = normalize_text(self._cell(row, match.columns.get("item_name")))
            quantity = parse_decimal(self._cell(row, match.columns.get("quantity")))

            raw_quantity = self._cell(row, match.columns.get("quantity"))
            if not any((item_code, barcode, item_name, raw_quantity not in (None, ""))):
                continue
            if skip_short_numeric_item_codes and is_short_numeric_item_code(item_code):
                continue
            if quantity is None:
                if raw_quantity in (None, ""):
                    continue
                items.append(
                    ParsedItem(
                        row_number=row_index,
                        raw_barcode=barcode,
                        normalized_barcode=barcode,
                        raw_name=item_name or None,
                        normalized_name=normalize_key(item_name) or None,
                        raw_item_code=item_code,
                        quantity=None,
                        source_payload={"raw_quantity": raw_quantity, "error": "invalid_quantity"},
                    )
                )
                continue
            if skip_zero and quantity == Decimal("0"):
                continue

            items.append(
                ParsedItem(
                    row_number=row_index,
                    raw_barcode=barcode,
                    normalized_barcode=barcode,
                    raw_name=item_name or None,
                    normalized_name=normalize_key(item_name) or None,
                    raw_item_code=item_code,
                    quantity=quantity,
                    source_payload={"raw_quantity": str(raw_quantity) if raw_quantity is not None else None},
                )
            )
        return items

    @staticmethod
    def _aggregate_duplicate_items(items: list[ParsedItem]) -> tuple[list[ParsedItem], list[str]]:
        grouped: dict[str, ParsedItem] = {}
        result: list[ParsedItem] = []
        warnings: list[str] = []
        for item in items:
            key = item.normalized_barcode or item.raw_item_code or f"row:{item.row_number}"
            if key in grouped and item.quantity is not None:
                target = grouped[key]
                if target.quantity is None:
                    result.append(item)
                    continue
                target.quantity += item.quantity
                target.source_payload.setdefault("duplicate_rows", []).append(item.row_number)
                warnings.append(
                    f"Duplicate item {key}: row {item.row_number} aggregated into row {target.row_number}"
                )
                continue
            grouped[key] = item
            result.append(item)
        return result, warnings
