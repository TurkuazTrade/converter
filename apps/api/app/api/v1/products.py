from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.product import Product, ProductBarcode, ProductTypeExportRule
from app.models.user import User
from app.repositories.products import ProductRepository
from app.schemas.product import (
    ProductCreate,
    ProductRead,
    ProductTypeExportRuleRead,
    ProductTypeExportRuleUpdate,
    ProductUpdate,
)
from app.services.import_service import ImportService
from app.services.matching_service import MatchingService
from app.utils.normalization import normalize_barcode, normalize_item_code, normalize_product_type, normalize_text

router = APIRouter()


@router.get("", response_model=list[ProductRead])
def list_products(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str = "",
    exclude_from_export: bool | None = None,
    is_active: bool | None = None,
    product_type: str = "",
    brand: str = "",
    trade_mark: str = "",
    sort_by: str = "name",
    sort_dir: str = "asc",
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ProductRead]:
    return ProductRepository(db).list(
        search=search,
        limit=limit,
        offset=offset,
        exclude_from_export=exclude_from_export,
        is_active=is_active,
        product_type=product_type,
        brand=brand,
        trade_mark=trade_mark,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/types", response_model=list[ProductTypeExportRuleRead])
def list_product_types(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ProductTypeExportRuleRead]:
    product_types = {
        normalized
        for value in db.scalars(
            select(Product.product_type)
            .where(Product.deleted_at.is_(None), Product.product_type.is_not(None), Product.product_type != "")
            .distinct()
        )
        if (normalized := normalize_product_type(value))
    }
    rules: dict[str, bool] = {}
    for rule in db.scalars(select(ProductTypeExportRule)):
        normalized = normalize_product_type(rule.product_type)
        if normalized:
            rules[normalized] = rules.get(normalized, False) or rule.exclude_from_export
    product_types.update(rules)
    return [
        ProductTypeExportRuleRead(product_type=product_type, exclude_from_export=rules.get(product_type, False))
        for product_type in sorted(product_types, key=lambda value: value.casefold())
    ]


@router.get("/filter-options")
def product_filter_options(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    def distinct_values(column) -> list[str]:
        values: dict[str, str] = {}
        for value in db.scalars(
            select(column)
            .where(Product.deleted_at.is_(None), column.is_not(None), column != "")
            .distinct()
            .order_by(column)
        ):
            normalized = normalize_product_type(value) if column is Product.product_type else normalize_text(value)
            if normalized:
                values.setdefault(normalized.casefold(), normalized)
        return sorted(values.values(), key=lambda value: value.casefold())

    return {
        "product_types": distinct_values(Product.product_type),
        "brands": distinct_values(Product.brand),
        "trade_marks": distinct_values(Product.trade_mark),
    }


@router.patch("/types/export-exclusion", response_model=ProductTypeExportRuleRead)
def update_product_type_export_exclusion(
    payload: ProductTypeExportRuleUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductTypeExportRuleRead:
    product_type = normalize_text(payload.product_type)
    product_type = normalize_product_type(product_type) or ""
    if not product_type:
        raise HTTPException(status_code=400, detail="Product type is required")
    rule = db.scalar(
        select(ProductTypeExportRule).where(
            func.lower(ProductTypeExportRule.product_type) == product_type.casefold()
        )
    )
    if rule is None:
        rule = ProductTypeExportRule(product_type=product_type, exclude_from_export=payload.exclude_from_export)
        db.add(rule)
    else:
        rule.exclude_from_export = payload.exclude_from_export
    db.commit()
    db.refresh(rule)
    return ProductTypeExportRuleRead(
        product_type=rule.product_type,
        exclude_from_export=rule.exclude_from_export,
    )


@router.post("", response_model=ProductRead)
def create_product(
    payload: ProductCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductRead:
    name = normalize_text(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Product name is required")
    product = Product(
        item_code=normalize_item_code(payload.item_code),
        name=name,
        price_code=normalize_item_code(payload.price_code),
        exchange_code=normalize_item_code(payload.exchange_code),
        article=normalize_item_code(payload.article),
        stock=normalize_text(payload.stock) or None,
        trade_mark=normalize_text(payload.trade_mark) or None,
        brand=normalize_text(payload.brand) or None,
        product_type=normalize_product_type(payload.product_type),
        conversion_multiplier=_payload_multiplier(payload.conversion_multiplier),
        exclude_from_export=payload.exclude_from_export,
        is_active=payload.is_active,
    )
    barcode = normalize_barcode(payload.barcode)
    if barcode:
        product.barcodes.append(ProductBarcode(barcode=barcode, is_primary=True, is_active=True))
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Product code or barcode already exists") from exc
    db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductRead:
    product = db.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Product not found")

    if payload.item_code is not None:
        product.item_code = normalize_item_code(payload.item_code)
    if payload.name is not None:
        name = normalize_text(payload.name)
        if not name:
            raise HTTPException(status_code=400, detail="Product name is required")
        product.name = name
    if payload.price_code is not None:
        product.price_code = normalize_item_code(payload.price_code)
    if payload.exchange_code is not None:
        product.exchange_code = normalize_item_code(payload.exchange_code)
    if payload.article is not None:
        product.article = normalize_item_code(payload.article)
    if payload.stock is not None:
        product.stock = normalize_text(payload.stock) or None
    if payload.trade_mark is not None:
        product.trade_mark = normalize_text(payload.trade_mark) or None
    if payload.brand is not None:
        product.brand = normalize_text(payload.brand) or None
    if payload.product_type is not None:
        product.product_type = normalize_product_type(payload.product_type)
    if payload.conversion_multiplier is not None:
        product.conversion_multiplier = _payload_multiplier(payload.conversion_multiplier)
    if payload.exclude_from_export is not None:
        product.exclude_from_export = payload.exclude_from_export
    if payload.is_active is not None:
        product.is_active = payload.is_active
    if payload.barcode is not None:
        _replace_primary_barcode(product, normalize_barcode(payload.barcode))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Product code or barcode already exists") from exc
    db.refresh(product)
    return product


@router.post("/import")
async def import_products(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    converter_type: str | None = None,
) -> dict:
    result = await ImportService(db).import_products(file, converter_type=converter_type)
    db.commit()
    return result


@router.post("/backfill-names")
def backfill_product_names(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    result = MatchingService(db).backfill_product_names_from_orders()
    db.commit()
    return result


def _replace_primary_barcode(product: Product, barcode: str | None) -> None:
    active_barcodes = [item for item in product.barcodes if item.deleted_at is None]
    if not barcode:
        for item in active_barcodes:
            item.is_active = False
            item.is_primary = False
        return
    primary = next((item for item in active_barcodes if item.is_primary), None)
    if primary is None and active_barcodes:
        primary = active_barcodes[0]
    if primary is None:
        product.barcodes.append(ProductBarcode(barcode=barcode, is_primary=True, is_active=True))
        return
    primary.barcode = barcode
    primary.is_primary = True
    primary.is_active = True
    for item in active_barcodes:
        if item is not primary:
            item.is_primary = False


def _payload_multiplier(value: float | None) -> Decimal:
    if value in (None, ""):
        return Decimal("1")
    try:
        multiplier = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="Conversion multiplier must be a number") from None
    if multiplier <= 0:
        raise HTTPException(status_code=400, detail="Conversion multiplier must be greater than zero")
    return multiplier
