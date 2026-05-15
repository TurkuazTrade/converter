from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.product import Product, ProductBarcode
from app.models.user import User
from app.repositories.products import ProductRepository
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services.import_service import ImportService
from app.services.matching_service import MatchingService
from app.utils.normalization import normalize_barcode, normalize_item_code, normalize_text

router = APIRouter()


@router.get("", response_model=list[ProductRead])
def list_products(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str = "",
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ProductRead]:
    return ProductRepository(db).list(search=search, limit=limit, offset=offset)


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
        conversion_multiplier=_payload_multiplier(payload.conversion_multiplier),
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
    if payload.conversion_multiplier is not None:
        product.conversion_multiplier = _payload_multiplier(payload.conversion_multiplier)
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
