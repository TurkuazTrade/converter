from __future__ import annotations

import base64
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.mapping import ClientMapping, ProductMapping
from app.models.product import Product, ProductBarcode
from app.services.converter_registry_service import ConverterRegistryService
from app.services.product_dictionary_service import ProductDictionaryService
from app.services.reference_workbook_service import ReferenceWorkbookService
from app.utils.excel_reader import read_workbook
from app.utils.normalization import (
    normalize_barcode,
    normalize_item_code,
    normalize_key,
    normalize_product_type,
    normalize_text,
    parse_decimal,
)


class ImportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.registry = ConverterRegistryService()

    async def import_reference_workbook(
        self,
        file: UploadFile,
        converter_type: str | None = None,
        *,
        import_products: bool = True,
        import_clients: bool = True,
    ) -> dict:
        path = await self._save_temp_upload(file)
        try:
            detected_converter = converter_type or self._detect_converter_type(file.filename or path.name)
            products = (
                self._import_products_from_path(path, detected_converter, source_filename=file.filename)
                if import_products
                else None
            )
            clients = self._import_clients_from_path(path, detected_converter) if import_clients else None
            return {
                "status": "ok",
                "converter_type": detected_converter,
                "products": products,
                "clients": clients,
            }
        finally:
            path.unlink(missing_ok=True)

    async def import_products(self, file: UploadFile, converter_type: str | None = None) -> dict:
        path = await self._save_temp_upload(file)
        try:
            detected_converter = converter_type or self._detect_converter_type(file.filename or path.name)
            return self._import_products_from_path(path, detected_converter, source_filename=file.filename)
        finally:
            path.unlink(missing_ok=True)

    async def import_clients(self, file: UploadFile, converter_type: str | None = None) -> dict:
        path = await self._save_temp_upload(file)
        try:
            detected_converter = converter_type or self._detect_converter_type(file.filename or path.name)
            return self._import_clients_from_path(path, detected_converter)
        finally:
            path.unlink(missing_ok=True)

    def _import_products_from_path(
        self,
        path: Path,
        detected_converter: str | None,
        *,
        source_filename: str | None = None,
    ) -> dict:
        rows = self._rows_from_excel(path, preferred_sheets=("convert",), kind="products")
        inserted = updated = skipped = mappings_inserted = 0
        skipped_rows: list[dict[str, Any]] = []
        dictionary_service = ProductDictionaryService(self.db)
        seen_mappings: set[tuple[str, str, str, int]] = set()
        seen_barcodes: set[tuple[int, str]] = set()
        for row in rows:
            barcode = normalize_barcode(row.get("barcode"))
            raw_item_code = normalize_item_code(row.get("raw_item_code"))
            item_code = self._first_item_code(row)
            explicit_name = self._human_product_name(
                row.get("name"),
                item_code=item_code,
                barcode=barcode,
                raw_item_code=raw_item_code,
            )
            name = explicit_name or ""
            price_code = normalize_item_code(row.get("price_code"))
            conversion_multiplier = self._conversion_multiplier(row.get("conversion_quantity"))
            catalog_fields = self._catalog_fields(row)
            if not (barcode or raw_item_code or explicit_name):
                skipped += 1
                skipped_rows.append(
                    self._skipped_product_row(
                        row,
                        reason=self._product_skip_reason(
                            item_code=item_code,
                            barcode=barcode,
                            raw_item_code=raw_item_code,
                            explicit_name=explicit_name,
                        ),
                    )
                )
                continue
            product = self._find_product(barcode=barcode, item_code=item_code)
            if product is None:
                product = Product(
                    item_code=item_code,
                    name=name,
                    price_code=price_code,
                    conversion_multiplier=conversion_multiplier,
                    **catalog_fields,
                    is_active=True,
                )
                self.db.add(product)
                dictionary_service.sync_product(product)
                self.db.flush()
                inserted += 1
            else:
                product.item_code = product.item_code or item_code
                if explicit_name:
                    product.name = explicit_name
                product.price_code = price_code or product.price_code
                product.conversion_multiplier = conversion_multiplier
                self._apply_catalog_fields(product, catalog_fields)
                product.is_active = True
                dictionary_service.sync_product(product)
                updated += 1
            barcode_key = (product.id, barcode) if barcode else None
            if barcode_key and barcode_key not in seen_barcodes and not self._barcode_exists(product.id, barcode):
                self.db.add(
                    ProductBarcode(
                        product_id=product.id,
                        barcode=barcode,
                        source="import",
                        is_primary=not product.barcodes,
                        is_active=True,
                    )
                )
                seen_barcodes.add(barcode_key)
            if detected_converter and self._save_product_mapping(
                converter_type=detected_converter,
                product=product,
                barcode=barcode,
                raw_item_code=raw_item_code,
                raw_name=explicit_name or None,
                conversion_multiplier=conversion_multiplier,
                seen=seen_mappings,
            ):
                mappings_inserted += 1
        return {
            "status": "ok",
            "converter_type": detected_converter,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "mappings_inserted": mappings_inserted,
            "skipped_file": self._skipped_products_file(skipped_rows, source_filename or path.name) if skipped_rows else None,
        }

    def _import_clients_from_path(self, path: Path, detected_converter: str | None) -> dict:
        rows = self._rows_from_excel(path, preferred_sheets=("client", "clients", "клиенты"), kind="clients")
        inserted = updated = skipped = mappings_inserted = 0
        seen_by_code: dict[str, Client] = {}
        seen_by_name: dict[str, Client] = {}
        seen_mappings: set[tuple[str, str, int]] = set()
        for row in rows:
            client_code = normalize_item_code(row.get("client_code"))
            name = normalize_text(row.get("name"))
            raw_client_name = normalize_text(row.get("raw_client_name"))
            name_2 = self._secondary_client_name(name, row.get("name_2"), raw_client_name)
            address = normalize_text(row.get("address")) or None
            network_name = normalize_text(row.get("network_name")) or detected_converter or None
            if not name and not client_code:
                skipped += 1
                continue
            normalized_name = normalize_key(name)
            client = (
                seen_by_code.get(client_code or "")
                or seen_by_name.get(normalized_name)
                or self._find_client(client_code=client_code, name=name)
            )
            if client is None:
                client = Client(
                    client_code=client_code,
                    name=name or client_code or "Unknown client",
                    name_2=name_2,
                    normalized_name=normalize_key(name or client_code),
                    address=address,
                    normalized_address=normalize_key(address),
                    network_name=network_name,
                    is_active=True,
                )
                self.db.add(client)
                self.db.flush()
                inserted += 1
            else:
                client.client_code = client.client_code or client_code
                client.name = name or client.name
                client.name_2 = name_2 or client.name_2
                client.normalized_name = normalize_key(client.name)
                client.address = address or client.address
                client.normalized_address = normalize_key(client.address)
                client.network_name = network_name or client.network_name
                client.is_active = True
                updated += 1
            if client.client_code:
                seen_by_code[client.client_code] = client
            if client.normalized_name:
                seen_by_name[client.normalized_name] = client
            if raw_client_name and detected_converter and self._save_client_mapping(
                converter_type=detected_converter,
                client=client,
                raw_client_name=raw_client_name,
                address=address,
                seen=seen_mappings,
            ):
                mappings_inserted += 1
        return {
            "status": "ok",
            "converter_type": detected_converter,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "mappings_inserted": mappings_inserted,
        }

    async def _save_temp_upload(self, file: UploadFile) -> Path:
        suffix = Path(file.filename or "upload.xlsx").suffix
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        path = Path(handle.name)
        try:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        finally:
            handle.close()
            await file.seek(0)
        return path

    def _rows_from_excel(
        self,
        path: Path,
        *,
        preferred_sheets: tuple[str, ...] = (),
        kind: str = "generic",
    ) -> list[dict[str, Any]]:
        sheets = read_workbook(path)
        if kind == "products":
            records: list[dict[str, Any]] = []
            for sheet in self._prioritized_sheets(sheets, preferred_sheets):
                if normalize_key(sheet.name) in {"client", "clients", "клиенты"}:
                    continue
                for row_index, row in sheet.visible_rows():
                    mapping = self._header_mapping(row, kind=kind)
                    if not mapping:
                        continue
                    sheet_type = normalize_text(sheet.name) or None
                    for data_row_index, data_row in sheet.visible_rows():
                        if data_row_index <= row_index:
                            continue
                        record = {
                            field: data_row[col] if col < len(data_row) else None
                            for field, col in mapping.items()
                        }
                        if sheet_type and normalize_key(sheet_type) != "convert":
                            record["product_type"] = sheet_type
                        if any(normalize_text(value) for value in record.values()):
                            record["__sheet"] = sheet.name
                            record["__row_number"] = data_row_index + 1
                            records.append(record)
                    break
            return records
        for sheet in self._prioritized_sheets(sheets, preferred_sheets):
            for row_index, row in sheet.visible_rows():
                mapping = self._header_mapping(row, kind=kind)
                if not mapping:
                    continue
                records = []
                for data_row_index, data_row in sheet.visible_rows():
                    if data_row_index <= row_index:
                        continue
                    record = {
                        field: data_row[col] if col < len(data_row) else None
                        for field, col in mapping.items()
                    }
                    if any(normalize_text(value) for value in record.values()):
                        records.append(record)
                return records
        return []

    @staticmethod
    def _prioritized_sheets(sheets: list[Any], preferred_names: tuple[str, ...]) -> list[Any]:
        if not preferred_names:
            return sheets
        preferred_keys = {normalize_key(name) for name in preferred_names}
        preferred = [sheet for sheet in sheets if normalize_key(sheet.name) in preferred_keys]
        others = [sheet for sheet in sheets if normalize_key(sheet.name) not in preferred_keys]
        return preferred + others

    @staticmethod
    def _header_mapping(row: list[Any], *, kind: str = "generic") -> dict[str, int] | None:
        aliases = {
            "item_code": {
                "а",
                "a",
                "код",
                "кодтовара",
                "itemcode",
                "sku",
                "skuno",
                "turkuazstockcode",
                "номертовара",
                "длинныйкод",
            },
            "item_code_alt_1": {"turkuazalter1stockcode"},
            "item_code_alt_2": {"turkuazalter2stockcode"},
            "item_code_alt_3": {"turkuazalter3stockcode"},
            "raw_item_code": {"clientstockcode", "кодсети", "сетевойкод", "кодклиента"},
            "barcode": {"штрихкод", "штрихкодтовара", "barcode", "ean"},
            "name": {"наименование", "наименованиетовара", "товар", "продукция", "name"},
            "price_code": {"ценовойкод", "pricecode"},
            "exchange_code": {"кодобмена", "exchangecode"},
            "article": {"артикул", "article", "vendorcode"},
            "stock": {"остаток", "stock", "quantityonhand"},
            "trade_mark": {"торговаямарка", "trademark"},
            "brand": {"бренд", "brand"},
            "product_type": {"тип", "type", "producttype", "категория"},
            "conversion_quantity": {"convquantity", "conversionquantity", "коэффициент"},
            "client_code": {"кодклиентапанорама", "кодклиента", "clientcode", "код"},
            "raw_client_name": {"названиеклиентапитон", "rawclientname", "networkclientname"},
            "name_2": {
                "название2",
                "название_2",
                "названиеклиента2",
                "названиеклиентапитон",
                "clientname2",
                "clientname_2",
                "name2",
                "name_2",
                "secondname",
                "secondaryname",
                "alternatename",
            },
            "address": {"адрес", "address", "адресклиента"},
            "network_name": {"сеть", "network", "networkname", "названиесети"},
        }
        aliases["name"] = aliases["name"] | {"названиеклиентапанорама", "названиеклиента", "clientname"}
        normalized = [normalize_key(cell) for cell in row]
        mapping: dict[str, int] = {}
        for field, field_aliases in aliases.items():
            for index, cell in enumerate(normalized):
                if cell in field_aliases:
                    mapping[field] = index
                    break
        if kind == "products" and "name" in mapping and "item_code" in mapping and "barcode" in mapping:
            if "trade_mark" not in mapping and len(row) > 4 and not normalize_text(row[4]):
                mapping["trade_mark"] = 4
            if "brand" not in mapping and len(row) > 5 and not normalize_text(row[5]):
                mapping["brand"] = 5

        if kind == "products":
            item_code_fields = {"item_code", "item_code_alt_1", "item_code_alt_2", "item_code_alt_3"}
            if item_code_fields.intersection(mapping) or "barcode" in mapping or "raw_item_code" in mapping or "name" in mapping:
                return mapping
            return None
        if kind == "clients":
            if "client_code" in mapping and (
                "name" in mapping or "name_2" in mapping or "raw_client_name" in mapping
            ):
                return mapping
            return None
        if "name" in mapping and (("barcode" in mapping) or ("client_code" in mapping) or ("item_code" in mapping)):
            return mapping
        return None

    @staticmethod
    def _catalog_fields(row: dict[str, Any]) -> dict[str, str | None]:
        return {
            "exchange_code": normalize_item_code(row.get("exchange_code")),
            "article": normalize_item_code(row.get("article")),
            "stock": normalize_text(row.get("stock")) or None,
            "trade_mark": normalize_text(row.get("trade_mark")) or None,
            "brand": normalize_text(row.get("brand")) or None,
            "product_type": normalize_product_type(row.get("product_type")),
        }

    @staticmethod
    def _apply_catalog_fields(product: Product, fields: dict[str, str | None]) -> None:
        for field, value in fields.items():
            if value:
                setattr(product, field, value)

    @staticmethod
    def _first_item_code(row: dict[str, Any]) -> str | None:
        for field in ("item_code", "item_code_alt_1", "item_code_alt_2", "item_code_alt_3"):
            item_code = normalize_item_code(row.get(field))
            if item_code:
                return item_code
        return None

    @staticmethod
    def _conversion_multiplier(value: Any) -> Decimal:
        multiplier = parse_decimal(value)
        if multiplier is None or multiplier <= 0:
            return Decimal("1")
        return multiplier

    @staticmethod
    def _product_skip_reason(
        *,
        item_code: str | None,
        barcode: str | None,
        raw_item_code: str | None,
        explicit_name: str,
    ) -> str:
        reasons: list[str] = []
        if not (barcode or raw_item_code or explicit_name):
            reasons.append("нет штрихкода, кода сети или названия")
        return "; ".join(reasons) or "строка не распознана"

    @staticmethod
    def _skipped_product_row(row: dict[str, Any], *, reason: str) -> dict[str, Any]:
        return {
            "reason": reason,
            "sheet": row.get("__sheet"),
            "row_number": row.get("__row_number"),
            "item_code": row.get("item_code"),
            "barcode": row.get("barcode"),
            "raw_item_code": row.get("raw_item_code"),
            "name": row.get("name"),
            "price_code": row.get("price_code"),
            "exchange_code": row.get("exchange_code"),
            "article": row.get("article"),
            "stock": row.get("stock"),
            "trade_mark": row.get("trade_mark"),
            "brand": row.get("brand"),
            "product_type": row.get("product_type"),
            "conversion_quantity": row.get("conversion_quantity"),
        }

    @staticmethod
    def _skipped_products_file(rows: list[dict[str, Any]], source_filename: str) -> dict[str, str]:
        content = ReferenceWorkbookService().build_skipped_products_workbook(rows)
        stem = Path(source_filename or "products").stem or "products"
        return {
            "filename": f"{stem}_skipped.xlsx",
            "mime_type": ReferenceWorkbookService.mime_type,
            "content_base64": base64.b64encode(content).decode("ascii"),
        }

    @staticmethod
    def _human_product_name(
        value: Any,
        *,
        item_code: str | None,
        barcode: str | None,
        raw_item_code: str | None,
    ) -> str:
        name = normalize_text(value)
        if not name:
            return ""
        name_key = normalize_key(name)
        technical_keys = {
            normalize_key(candidate)
            for candidate in (item_code, barcode, raw_item_code)
            if candidate
        }
        return "" if name_key in technical_keys else name

    @staticmethod
    def _secondary_client_name(primary_name: str, *values: Any) -> str | None:
        primary_key = normalize_key(primary_name)
        for value in values:
            name = normalize_text(value)
            if name and normalize_key(name) != primary_key:
                return name
        return None

    def _detect_converter_type(self, filename: str) -> str | None:
        detected = self.registry.detect_converter(filename)
        return detected.value if detected else None

    def _find_product(self, barcode: str | None, item_code: str | None) -> Product | None:
        if barcode:
            product = self.db.scalar(
                select(Product)
                .join(ProductBarcode, ProductBarcode.product_id == Product.id)
                .where(
                    ProductBarcode.barcode == barcode,
                    self._trusted_barcode_condition(),
                    ProductBarcode.deleted_at.is_(None),
                    ProductBarcode.is_active.is_(True),
                    Product.deleted_at.is_(None),
                    Product.is_active.is_(True),
                )
            )
            if product is not None:
                return product
        if item_code:
            return self.db.scalar(select(Product).where(Product.item_code == item_code, Product.deleted_at.is_(None)))
        return None

    def _barcode_exists(self, product_id: int, barcode: str) -> bool:
        return (
            self.db.scalar(
                select(ProductBarcode.id).where(
                    ProductBarcode.product_id == product_id,
                    ProductBarcode.barcode == barcode,
                    ProductBarcode.deleted_at.is_(None),
                )
            )
            is not None
        )

    def _save_product_mapping(
        self,
        *,
        converter_type: str,
        product: Product,
        barcode: str | None,
        raw_item_code: str | None,
        raw_name: str | None,
        conversion_multiplier: Decimal,
        seen: set[tuple[str, str, str, int]] | None = None,
    ) -> bool:
        normalized_barcode = normalize_barcode(barcode)
        normalized_item_code = normalize_key(raw_item_code)
        normalized_name = normalize_key(raw_name)
        if not normalized_barcode and not normalized_item_code and not normalized_name:
            return False

        mapping_keys: list[tuple[str, str, str, int]] = []
        if normalized_barcode:
            mapping_keys.append(("barcode", converter_type, normalized_barcode, product.id))
        if normalized_item_code:
            mapping_keys.append(("item_code", converter_type, normalized_item_code, product.id))
        if normalized_name:
            mapping_keys.append(("name", converter_type, normalized_name, product.id))
        if seen is not None and any(key in seen for key in mapping_keys):
            return False

        match_conditions = []
        if normalized_item_code:
            match_conditions.append(ProductMapping.normalized_item_code == normalized_item_code)
        if normalized_barcode:
            match_conditions.append(ProductMapping.normalized_barcode == normalized_barcode)
        if normalized_name:
            match_conditions.append(ProductMapping.normalized_name == normalized_name)
        conditions = [
            ProductMapping.converter_type == converter_type,
            ProductMapping.product_id == product.id,
            ProductMapping.deleted_at.is_(None),
            or_(*match_conditions),
        ]
        existing_mapping = self.db.scalar(select(ProductMapping).where(*conditions))
        if existing_mapping is not None:
            existing_mapping.conversion_multiplier = conversion_multiplier
            if seen is not None:
                seen.update(mapping_keys)
            return False

        self.db.add(
            ProductMapping(
                converter_type=converter_type,
                raw_barcode=barcode,
                normalized_barcode=normalized_barcode,
                raw_item_code=raw_item_code,
                normalized_item_code=normalized_item_code,
                raw_name=raw_name,
                normalized_name=normalized_name,
                conversion_multiplier=conversion_multiplier,
                product_id=product.id,
                is_active=True,
            )
        )
        if seen is not None:
            seen.update(mapping_keys)
        return True

    def _find_client(self, client_code: str | None, name: str | None) -> Client | None:
        if client_code:
            client = self.db.scalar(
                select(Client).where(Client.client_code == client_code, Client.deleted_at.is_(None))
            )
            if client is not None:
                return client
        if name:
            return self.db.scalar(
                select(Client).where(Client.normalized_name == normalize_key(name), Client.deleted_at.is_(None))
            )
        return None

    @staticmethod
    def _trusted_barcode_condition():
        return or_(ProductBarcode.source.is_(None), ProductBarcode.source != "smoke")

    def _save_client_mapping(
        self,
        *,
        converter_type: str,
        client: Client,
        raw_client_name: str,
        address: str | None,
        seen: set[tuple[str, str, int]] | None = None,
    ) -> bool:
        normalized_client_name = normalize_key(raw_client_name)
        normalized_address = normalize_key(address)
        mapping_key = (converter_type, normalized_client_name, client.id)
        if seen is not None and mapping_key in seen:
            return False
        exists = self.db.scalar(
            select(ClientMapping.id).where(
                ClientMapping.converter_type == converter_type,
                ClientMapping.normalized_client_name == normalized_client_name,
                ClientMapping.client_id == client.id,
                ClientMapping.deleted_at.is_(None),
            )
        )
        if exists is not None:
            if seen is not None:
                seen.add(mapping_key)
            return False
        self.db.add(
            ClientMapping(
                converter_type=converter_type,
                raw_client_name=raw_client_name,
                normalized_client_name=normalized_client_name,
                raw_address=address,
                normalized_address=normalized_address,
                client_id=client.id,
                is_active=True,
            )
        )
        if seen is not None:
            seen.add(mapping_key)
        return True
