from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

INVALID_FILENAME_CHARS = r'<>:"/\|?*'


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ").strip()
    return re.sub(r"\s+", " ", text)


def normalize_key(value: Any) -> str:
    text = normalize_text(value).casefold().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-я]+", "", text)


def normalize_barcode(value: Any) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    text = re.sub(r"\s+", "", text)
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    if re.fullmatch(r"\d+(\.\d+)?[eE]\+?\d+", text):
        try:
            text = f"{Decimal(text):f}".split(".")[0]
        except InvalidOperation:
            pass
    return text or None


def normalize_item_code(value: Any) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return text.strip() or None


def normalize_product_type(value: Any) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    return text.casefold()


def is_short_numeric_item_code(value: Any, *, min_digits: int = 2, max_digits: int = 4) -> bool:
    item_code = normalize_item_code(value)
    if not item_code:
        return False
    return re.fullmatch(rf"\d{{{min_digits},{max_digits}}}", item_code) is not None


def parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    text = normalize_text(value).replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if match:
        text = match.group(0)
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_date(value: Any, default: date | None = None) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = normalize_text(value)
    if not text:
        return default or date.today()

    patterns = (
        "%Y-%m-%d %H:%M:%S",
        "%d.%m.%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d.%m.%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
    )
    for pattern in patterns:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue

    match = re.search(r"(\d{2}[.\-]\d{2}[.\-]\d{4})", text)
    if match:
        return parse_date(match.group(1), default=default)
    return default or date.today()


def sanitize_filename_part(value: Any, fallback: str = "unknown") -> str:
    text = normalize_text(value) or fallback
    translation = str.maketrans({char: "_" for char in INVALID_FILENAME_CHARS})
    text = text.translate(translation)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._ ")
    return text or fallback


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1
