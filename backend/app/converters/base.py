from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ParsedClientHint:
    raw_name: str | None = None
    raw_address: str | None = None
    client_code: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedItem:
    row_number: int
    raw_barcode: str | None
    normalized_barcode: str | None
    raw_name: str | None
    normalized_name: str | None
    raw_item_code: str | None
    quantity: Decimal | None
    source_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedOrder:
    document_no: str | None
    document_date: date | None
    sheet_name: str
    header_row: int | None
    client_hint: ParsedClientHint
    items: list[ParsedItem]
    warnings: list[str] = field(default_factory=list)
    parser_metadata: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        return {
            "document_no": self.document_no,
            "document_date": self.document_date.isoformat() if self.document_date else None,
            "sheet": self.sheet_name,
            "header_row": self.header_row,
            "client_hint": asdict(self.client_hint),
            "items": [
                {
                    **asdict(item),
                    "quantity": str(item.quantity) if item.quantity is not None else None,
                }
                for item in self.items
            ],
            "warnings": self.warnings,
            "parser_metadata": self.parser_metadata,
        }


class BaseConverter(ABC):
    converter_type: str
    converter_version: str

    @abstractmethod
    def detect(self, path: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def validate(self, path: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def parse(self, path: Path) -> ParsedOrder:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, parsed_order: ParsedOrder) -> ParsedOrder:
        raise NotImplementedError

    @abstractmethod
    def extract_client_hint(self, path: Path) -> ParsedClientHint:
        raise NotImplementedError

    @abstractmethod
    def extract_items(self, path: Path) -> list[ParsedItem]:
        raise NotImplementedError
