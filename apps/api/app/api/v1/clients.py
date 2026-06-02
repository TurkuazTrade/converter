from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.clients import ClientRepository
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.services.import_service import ImportService
from app.services.reference_workbook_service import ReferenceWorkbookService
from app.utils.normalization import normalize_key, normalize_text

router = APIRouter()


@router.get("", response_model=list[ClientRead])
def list_clients(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str = "",
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ClientRead]:
    return ClientRepository(db, branch_id=current_user.branch_id).list(search=search, limit=limit, offset=offset)


@router.post("", response_model=ClientRead)
def create_client(
    payload: ClientCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ClientRead:
    client_code = normalize_text(payload.client_code)
    name = normalize_text(payload.name)
    if not client_code or not name:
        raise HTTPException(status_code=400, detail="Client code and name are required")
    client = Client(
        branch_id=current_user.branch_id,
        client_code=client_code,
        name=name,
        name_2=normalize_text(payload.name_2) or None,
        normalized_name=normalize_key(name),
        address=normalize_text(payload.address) or None,
        normalized_address=normalize_key(payload.address),
        network_name=normalize_text(payload.network_name) or None,
        is_active=True,
    )
    db.add(client)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Client code already exists") from exc
    db.refresh(client)
    return client


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ClientRead:
    client = db.get(Client, client_id)
    if client is None or client.deleted_at is not None or not _belongs_to_branch(client, current_user.branch_id):
        raise HTTPException(status_code=404, detail="Client not found")

    if payload.client_code is not None:
        client.client_code = normalize_text(payload.client_code) or None
    if payload.name is not None:
        name = normalize_text(payload.name)
        if not name:
            raise HTTPException(status_code=400, detail="Client name is required")
        client.name = name
        client.normalized_name = normalize_key(name)
    if payload.name_2 is not None:
        client.name_2 = normalize_text(payload.name_2) or None
    if payload.address is not None:
        client.address = normalize_text(payload.address) or None
        client.normalized_address = normalize_key(payload.address)
    if payload.network_name is not None:
        client.network_name = normalize_text(payload.network_name) or None
    if payload.is_active is not None:
        client.is_active = payload.is_active

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Client code already exists") from exc
    db.refresh(client)
    return client


@router.post("/import")
async def import_clients(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    converter_type: str | None = None,
) -> dict:
    result = await ImportService(db, branch_id=current_user.branch_id).import_clients(file, converter_type=converter_type)
    db.commit()
    return result


@router.get("/import-template")
def client_import_template(
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    service = ReferenceWorkbookService()
    filename = "clients_template.xlsx"
    return Response(
        content=service.build_clients_workbook(),
        media_type=service.mime_type,
        headers={"Content-Disposition": _attachment_header(filename)},
    )


@router.get("/export")
def export_clients(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    clients = db.scalars(
        select(Client)
        .where(Client.deleted_at.is_(None), *_branch_filters(Client, current_user.branch_id))
        .order_by(Client.name, Client.client_code)
    )
    service = ReferenceWorkbookService()
    filename = "clients_filled.xlsx"
    return Response(
        content=service.build_clients_workbook(clients),
        media_type=service.mime_type,
        headers={"Content-Disposition": _attachment_header(filename)},
    )


def _attachment_header(filename: str) -> str:
    quoted = quote(filename)
    return f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quoted}'


def _branch_filters(model, branch_id: int | None) -> tuple:
    if branch_id is None:
        return ()
    return (model.branch_id == branch_id,)


def _belongs_to_branch(entity, branch_id: int | None) -> bool:
    return branch_id is None or getattr(entity, "branch_id", None) == branch_id
