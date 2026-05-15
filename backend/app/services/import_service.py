from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.mapping import ClientMapping, ProductMapping
from app.models.product import Product, ProductBarcode
from app.services.converter_registry_service import ConverterRegistryService
from app.utils.excel_reader import read_workbook
from app.utils.normalization import (
    normalize_barcode,
    normalize_item_code,
    normalize_key,
    normalize_text,
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
            products = self._import_products_from_path(path, detected_converter) if import_products else None
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
            return self._import_products_from_path(path, detected_converter)
        finally:
            path.unlink(missing_ok=True)

    async def import_clients(self, file: UploadFile, converter_type: str | None = None) -> dict:
        path = await self._save_temp_upload(file)
        try:
            detected_converter = converter_type or self._detect_converter_type(file.filename or path.name)
            return self._import_clients_from_path(path, detected_converter)
        finally:
            path.unlink(missing_ok=True)

    def _import_products_from_path(self, path: Path, detected_converter: str | None) -> dict:
        rows = self._rows_from_excel(path, preferred_sheets=("convert",), kind="products")
        inserted = updated = skipped = mappings_inserted = 0
        seen_mappings: set[tuple[str, str, str, int]] = set()
        seen_barcodes: set[tuple[int, str]] = set()
        for row in rows:
            barcode = normalize_barcode(row.get("barcode"))
            raw_item_code = normalize_item_code(row.get("raw_item_code"))
            item_code = self._first_item_code(row)
            explicit_name = normalize_text(row.get("name"))
            name = explicit_name or item_code or barcode or raw_item_code
            price_code = normalize_item_code(row.get("price_code"))
            if not item_code or not (barcode or raw_item_code or explicit_name):
                skipped += 1
                continue
            product = self._find_product(barcode=barcode, item_code=item_code)
            if product is None:
                product = Product(item_code=item_code, name=name, price_code=price_code, is_active=True)
                self.db.add(product)
                self.db.flush()
                inserted += 1
            else:
                product.item_code = product.item_code or item_code
                if explicit_name:
                    product.name = explicit_name
                product.price_code = price_code or product.price_code
                product.is_active = True
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

    def _import_clients_from_path(self, path: Path, detected_converter: str | None) -> dict:
        rows = self._rows_from_excel(path, preferred_sheets=("client", "clients", "клиенты"), kind="clients")
        inserted = updated = skipped = mappings_inserted = 0
        for row in rows:
            client_code = normalize_item_code(row.get("client_code"))
            client_code_2 = normalize_item_code(row.get("client_code_2"))
            name = normalize_text(row.get("name"))
            raw_client_name = normalize_text(row.get("raw_client_name"))
            address = normalize_text(row.get("address")) or None
            network_name = normalize_text(row.get("network_name")) or detected_converter or None
            if not name and not client_code:
                skipped += 1
                continue
            client = self._find_client(client_code=client_code, name=name)
            if client is None:
                client = Client(
                    client_code=client_code,
                    client_code_2=client_code_2,
                    name=name or client_code or "Unknown client",
                    normalized_name=normalize_key(name or client_code),
                    address=address,
                    normalized_address=normalize_key(address),
                    network_name=network_name,
                    is_active=True,
                )
                self.db.add(client)
                inserted += 1
            else:
                client.client_code = client.client_code or client_code
                client.client_code_2 = client_code_2 or client.client_code_2
                client.name = name or client.name
                client.normalized_name = normalize_key(client.name)
                client.address = address or client.address
                client.normalized_address = normalize_key(client.address)
                client.network_name = network_name or client.network_name
                client.is_active = True
                updated += 1
            if raw_client_name and detected_converter and self._save_client_mapping(
                converter_type=detected_converter,
                client=client,
                raw_client_name=raw_client_name,
                address=address,
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
            },
            "item_code_alt_1": {"turkuazalter1stockcode"},
            "item_code_alt_2": {"turkuazalter2stockcode"},
            "item_code_alt_3": {"turkuazalter3stockcode"},
            "raw_item_code": {"clientstockcode", "кодсети", "сетевойкод", "кодклиента"},
            "barcode": {"штрихкод", "штрихкодтовара", "barcode", "ean"},
            "name": {"наименование", "товар", "продукция", "name"},
            "price_code": {"ценовойкод", "pricecode"},
            "conversion_quantity": {"convquantity", "conversionquantity", "коэффициент"},
            "client_code": {"кодклиентапанорама", "кодклиента", "clientcode", "код"},
            "client_code_2": {"кодклиента2", "clientcode2"},
            "raw_client_name": {"названиеклиентапитон", "rawclientname", "networkclientname"},
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

        if kind == "products":
            if "item_code" in mapping and (
                "barcode" in mapping or "raw_item_code" in mapping or "name" in mapping
            ):
                return mapping
            return None
        if kind == "clients":
            if "client_code" in mapping and ("name" in mapping or "raw_client_name" in mapping):
                return mapping
            return None
        if "name" in mapping and (("barcode" in mapping) or ("client_code" in mapping) or ("item_code" in mapping)):
            return mapping
        return None

    @staticmethod
    def _first_item_code(row: dict[str, Any]) -> str | None:
        for field in ("item_code", "item_code_alt_1", "item_code_alt_2", "item_code_alt_3"):
            item_code = normalize_item_code(row.get(field))
            if item_code:
                return item_code
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
        exists = self.db.scalar(select(ProductMapping.id).where(*conditions))
        if exists is not None:
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

    def _save_client_mapping(
        self,
        *,
        converter_type: str,
        client: Client,
        raw_client_name: str,
        address: str | None,
    ) -> bool:
        normalized_client_name = normalize_key(raw_client_name)
        normalized_address = normalize_key(address)
        exists = self.db.scalar(
            select(ClientMapping.id).where(
                ClientMapping.converter_type == converter_type,
                ClientMapping.normalized_client_name == normalized_client_name,
                ClientMapping.client_id == client.id,
                ClientMapping.deleted_at.is_(None),
            )
        )
        if exists is not None:
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
        return True
