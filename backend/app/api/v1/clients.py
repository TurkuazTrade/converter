from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.clients import ClientRepository
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.services.import_service import ImportService
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
    return ClientRepository(db).list(search=search, limit=limit, offset=offset)


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
        client_code=client_code,
        client_code_2=normalize_text(payload.client_code_2) or None,
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
    if client is None or client.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Client not found")

    if payload.client_code is not None:
        client.client_code = normalize_text(payload.client_code) or None
    if payload.client_code_2 is not None:
        client.client_code_2 = normalize_text(payload.client_code_2) or None
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
    result = await ImportService(db).import_clients(file, converter_type=converter_type)
    db.commit()
    return result
