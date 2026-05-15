from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.enums import OrderItemStatus, OrderStatus
from app.db.session import get_db
from app.models.user import User
from app.models.order import Order
from app.repositories.orders import OrderRepository
from app.schemas.order import OrderDetail, OrderRead, UploadOrderResponse
from app.services.export_service import ExportService
from app.services.matching_service import MatchingService
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
) -> list[OrderRead]:
    orders = OrderRepository(db).list(limit=limit)
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
                "quantity": float(item.quantity),
                "status": item.status,
                "error_message": item.error_message,
                "product_id": item.product_id,
                "product_name": item.product.name if item.product else None,
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
    MatchingService(db).save_product_mapping(order_item_id, product_id, current_user.id)
    ReprocessService(db).rematch_only(order_id, user_id=current_user.id)
    db.commit()
    return {"order_id": order_id, "order_item_id": order_item_id, "status": "resolved"}


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
) -> dict:
    try:
        result = _generate_export(db, order_id, current_user.id)
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
) -> Response:
    try:
        result = _generate_export(db, order_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return Response(
        content=result.content,
        media_type=result.mime_type,
        headers={"Content-Disposition": _attachment_header(result.filename)},
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


def _generate_export(db: Session, order_id: int, user_id: int):
    order = OrderRepository(db).get(order_id)
    if order is None:
        raise ValueError("Order not found.")
    recalculation = ReprocessService(db).rematch_only(order_id, user_id=user_id)
    if recalculation["status"] != OrderStatus.READY_TO_EXPORT.value:
        raise ValueError("Order is not ready to export after recalculation. Resolve client and products first.")
    return ExportService().export_order(db, order_id, user_id=user_id)


def _refresh_order_state(db: Session, order: Order) -> None:
    if order.status == OrderStatus.FAILED.value:
        return
    MatchingService(db).match_order(order.id)
    unresolved_count = sum(
        1
        for item in order.items
        if item.status in {OrderItemStatus.UNRESOLVED.value, OrderItemStatus.INVALID_QUANTITY.value}
        or item.product_id is None
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


def _attachment_header(filename: str) -> str:
    quoted = quote(filename)
    return f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quoted}'
