from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.enums import OrderItemStatus, OrderStatus
from app.db.base import utc_now
from app.db.session import get_db
from app.models.user import User
from app.models.order import Order
from app.repositories.orders import OrderRepository
from app.schemas.order import OrderDetail, OrderRead, UploadOrderResponse
from app.services.export_service import ExportService
from app.services.matching_service import MatchingService
from app.services.reference_workbook_service import ReferenceWorkbookService
from app.services.reprocess_service import ReprocessService
from app.services.storage_service import LocalStorageService

router = APIRouter()


@router.post("/upload", response_model=UploadOrderResponse)
async def upload_order(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    converter_type: str | None = None,
    force: bool = False,
) -> UploadOrderResponse:
    from app.services.order_processing_service import OrderProcessingService

    order, duplicate, existing_order_id, message = await OrderProcessingService(db).upload_order(
        upload_file=file,
        user_id=current_user.id,
        converter_type=converter_type,
        force=force,
    )
    db.commit()
    return UploadOrderResponse(
        order=order,
        duplicate=duplicate,
        existing_order_id=existing_order_id,
        message=message,
    )


@router.get("", response_model=list[OrderRead])
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[OrderRead]:
    orders = OrderRepository(db).list(limit=limit, offset=offset)
    for order in orders:
        _refresh_order_state(db, order)
    db.commit()
    return orders


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrderDetail:
    order = OrderRepository(db).get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    _refresh_order_state(db, order)
    db.commit()
    return order


@router.get("/{order_id}/preview")
def order_preview(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = OrderRepository(db).get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    _refresh_order_state(db, order)
    db.commit()
    excluded_product_types = ExportService._excluded_product_types(db)
    return {
        "order": OrderDetail.model_validate(order).model_dump(mode="json"),
        "client": (
            {
                "id": order.client.id,
                "client_code": order.client.client_code,
                "name": order.client.name,
                "address": order.client.address,
                "network_name": order.client.network_name,
            }
            if order.client
            else None
        ),
        "client_hint": (order.parsed_snapshot or {}).get("client_hint"),
        "warnings": (order.parsed_snapshot or {}).get("warnings", []),
        "items": [
            {
                "id": item.id,
                "row_number": item.row_number,
                "raw_barcode": item.raw_barcode,
                "raw_item_code": item.raw_item_code,
                "item_code": item.item_code,
                "raw_name": item.raw_name,
                "source_quantity": float(item.source_quantity) if item.source_quantity is not None else None,
                "conversion_multiplier": float(item.conversion_multiplier),
                "quantity": float(item.quantity),
                "status": item.status,
                "error_message": item.error_message,
                "product_id": item.product_id,
                "product_name": item.product.name if item.product else None,
                "product_type": item.product.product_type if item.product else None,
                "product_exclude_from_export": _product_excluded_from_export(item.product, excluded_product_types),
            }
            for item in sorted(order.items, key=lambda row: row.row_number or 0)
        ],
    }


@router.get("/{order_id}/debug")
def order_debug(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = OrderRepository(db).get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    _refresh_order_state(db, order)
    db.commit()
    sorted_items = sorted(order.items, key=lambda row: row.row_number or 0)
    excluded_product_types = ExportService._excluded_product_types(db)
    status_counts: dict[str, int] = {}
    for item in sorted_items:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
    return {
        "order": {
            "id": order.id,
            "status": order.status,
            "error_message": order.error_message,
            "converter_type": order.converter_type,
            "converter_version": order.converter_version,
            "converter_config_hash": order.converter_config_hash,
            "order_number": order.order_number,
            "source_file_id": order.source_file_id,
            "export_file_id": order.export_file_id,
            "export_downloaded_at": order.export_downloaded_at,
            "export_downloads": order.export_downloads,
        },
        "client": (
            {
                "id": order.client.id,
                "client_code": order.client.client_code,
                "name": order.client.name,
                "address": order.client.address,
                "network_name": order.client.network_name,
            }
            if order.client
            else None
        ),
        "items_summary": {
            "total": len(sorted_items),
            "by_status": status_counts,
            "resolved": status_counts.get("resolved", 0),
            "unresolved": status_counts.get("unresolved", 0),
            "invalid_quantity": status_counts.get("invalid_quantity", 0),
        },
        "items": [
            {
                "id": item.id,
                "row_number": item.row_number,
                "raw_barcode": item.raw_barcode,
                "raw_item_code": item.raw_item_code,
                "raw_name": item.raw_name,
                "product_id": item.product_id,
                "product_item_code": item.product.item_code if item.product else None,
                "product_name": item.product.name if item.product else None,
                "product_type": item.product.product_type if item.product else None,
                "product_exclude_from_export": _product_excluded_from_export(item.product, excluded_product_types),
                "source_quantity": float(item.source_quantity) if item.source_quantity is not None else None,
                "conversion_multiplier": float(item.conversion_multiplier),
                "quantity": float(item.quantity),
                "status": item.status,
                "error_message": item.error_message,
            }
            for item in sorted_items[:10]
        ],
    }


@router.get("/{order_id}/unresolved")
def unresolved_items(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = OrderRepository(db).get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    _refresh_order_state(db, order)
    db.commit()
    items = [
        {
            "id": item.id,
            "row_number": item.row_number,
            "raw_barcode": item.raw_barcode,
            "raw_item_code": item.raw_item_code,
            "raw_name": item.raw_name,
            "source_quantity": float(item.source_quantity) if item.source_quantity is not None else None,
            "conversion_multiplier": float(item.conversion_multiplier),
            "quantity": float(item.quantity),
            "status": item.status,
            "error_message": item.error_message,
        }
        for item in sorted(order.items, key=lambda row: row.row_number or 0)
        if item.status in {"unresolved", "invalid_quantity"}
    ]
    return {"order_id": order_id, "items": items, "count": len(items)}


@router.post("/{order_id}/resolve-product")
def resolve_product(
    order_id: int,
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order_item_id = int(payload["order_item_id"])
    product_id = int(payload["product_id"])
    MatchingService(db).save_product_mapping(
        order_item_id,
        product_id,
        current_user.id,
        conversion_multiplier=_payload_decimal(payload.get("conversion_multiplier")),
    )
    ReprocessService(db).rematch_only(order_id, user_id=current_user.id)
    db.commit()
    return {"order_id": order_id, "order_item_id": order_item_id, "status": "resolved"}


@router.post("/{order_id}/skip-product")
def skip_product(
    order_id: int,
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order_item_id = int(payload["order_item_id"])
    MatchingService(db).skip_item(order_item_id)
    ReprocessService(db).rematch_only(order_id, user_id=current_user.id)
    db.commit()
    return {"order_id": order_id, "order_item_id": order_item_id, "status": "skipped"}


@router.post("/{order_id}/update-multiplier")
def update_multiplier(
    order_id: int,
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order_item_id = int(payload["order_item_id"])
    MatchingService(db).update_item_multiplier(
        order_item_id,
        conversion_multiplier=_payload_decimal(payload.get("conversion_multiplier")),
    )
    ReprocessService(db).rematch_only(order_id, user_id=current_user.id)
    db.commit()
    return {"order_id": order_id, "order_item_id": order_item_id, "status": "updated"}


@router.post("/{order_id}/resolve-client")
def resolve_client(
    order_id: int,
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    client_id = int(payload["client_id"])
    MatchingService(db).save_client_mapping(order_id, client_id, current_user.id)
    ReprocessService(db).rematch_only(order_id, user_id=current_user.id)
    db.commit()
    return {"order_id": order_id, "client_id": client_id, "status": "resolved"}


@router.post("/{order_id}/reprocess")
def reprocess_order(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    mode: str = "rematch_only",
) -> dict:
    service = ReprocessService(db)
    try:
        result = (
            service.full_reparse(order_id, user_id=current_user.id)
            if mode == "full_reparse"
            else service.rematch_only(order_id, user_id=current_user.id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.post("/{order_id}/export")
def export_order(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    product_type: str | None = None,
) -> dict:
    try:
        result = _generate_export(db, order_id, current_user.id, product_type=product_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {
        "order_id": order_id,
        "file_id": None,
        "filename": result.filename,
        "download_url": f"/api/v1/orders/{order_id}/download-export",
        "status": "exported",
    }


@router.get("/{order_id}/download-export")
def download_export(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    product_type: str | None = None,
) -> Response:
    try:
        result = _generate_export(db, order_id, current_user.id, product_type=product_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    order = OrderRepository(db).get(order_id)
    previous_download = _export_download_info(order, product_type) if order is not None else None
    if order is not None:
        _mark_export_downloaded(order, product_type, current_user)
    db.commit()
    headers = {"Content-Disposition": _attachment_header(result.filename)}
    if previous_download:
        previous_user_name = previous_download.get("user_name")
        previous_downloaded_at = previous_download.get("downloaded_at")
        if previous_user_name:
            headers["X-Export-Previously-Downloaded-By"] = quote(str(previous_user_name))
        if previous_downloaded_at:
            headers["X-Export-Previously-Downloaded-At"] = quote(str(previous_downloaded_at))
    return Response(
        content=result.content,
        media_type=result.mime_type,
        headers=headers,
    )


@router.get("/templates/import")
def order_import_template(
    current_user: Annotated[User, Depends(get_current_user)],
    converter_type: str | None = None,
) -> Response:
    service = ReferenceWorkbookService()
    selected_converter = converter_type or "asia_retail"
    try:
        content = service.build_order_template(selected_converter)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Converter template not found") from exc
    filename = f"order_template_{selected_converter}.xlsx"
    return Response(
        content=content,
        media_type=service.mime_type,
        headers={"Content-Disposition": _attachment_header(filename)},
    )


@router.get("/{order_id}/download-source")
def download_source(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    order = OrderRepository(db).get(order_id)
    if order is None or order.source_file is None:
        raise HTTPException(status_code=404, detail="Source file not found")
    if not order.source_file.path:
        raise HTTPException(status_code=404, detail="Source file is not retained on server")
    path = LocalStorageService().get_path(order.source_file.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Stored source file not found")
    return FileResponse(
        path,
        filename=order.source_file.original_name,
        media_type=order.source_file.mime_type,
    )


def _generate_export(db: Session, order_id: int, user_id: int, *, product_type: str | None = None):
    order = OrderRepository(db).get(order_id)
    if order is None:
        raise ValueError("Order not found.")
    ReprocessService(db).rematch_only(order_id, user_id=user_id)
    return ExportService().export_order(db, order_id, user_id=user_id, product_type=product_type)


def _mark_export_downloaded(order: Order, product_type: str | None, user: User) -> None:
    downloaded_at = utc_now()
    download_key = product_type.strip() if product_type and product_type.strip() else "__full__"
    order.export_downloaded_at = downloaded_at
    order.export_downloads = {
        **(order.export_downloads or {}),
        download_key: {
            "downloaded_at": downloaded_at.isoformat(),
            "user_id": user.id,
            "user_name": user.full_name,
        },
    }


def _export_download_info(order: Order, product_type: str | None) -> dict | None:
    download_key = product_type.strip() if product_type and product_type.strip() else "__full__"
    value = (order.export_downloads or {}).get(download_key)
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return {"downloaded_at": value}
    return None


def _refresh_order_state(db: Session, order: Order) -> None:
    if order.status == OrderStatus.FAILED.value:
        return
    MatchingService(db).match_order(order.id)
    unresolved_count = sum(
        1
        for item in order.items
        if item.status in {OrderItemStatus.UNRESOLVED.value, OrderItemStatus.INVALID_QUANTITY.value}
        or (item.status == OrderItemStatus.RESOLVED.value and item.product_id is None)
    )
    client_unresolved = order.client_id is None
    order.status = (
        OrderStatus.NEEDS_REVIEW.value
        if unresolved_count or client_unresolved
        else OrderStatus.READY_TO_EXPORT.value
    )
    order.error_message = _review_message(unresolved_count, client_unresolved)
    order.export_file_id = None


def _review_message(unresolved_count: int, client_unresolved: bool) -> str | None:
    if not unresolved_count and not client_unresolved:
        return None
    parts: list[str] = []
    if client_unresolved:
        parts.append("Client is not resolved.")
    if unresolved_count:
        parts.append(f"{unresolved_count} order item(s) are unresolved or invalid.")
    return " ".join(parts)


def _product_excluded_from_export(product: object, excluded_product_types: set[str]) -> bool:
    if product is None:
        return False
    if getattr(product, "exclude_from_export", False):
        return True
    product_type = (getattr(product, "product_type", None) or "").casefold()
    return bool(product_type and product_type in excluded_product_types)


def _attachment_header(filename: str) -> str:
    quoted = quote(filename)
    return f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quoted}'


def _payload_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
