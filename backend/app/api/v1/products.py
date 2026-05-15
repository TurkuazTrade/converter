from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.products import ProductRepository
from app.schemas.product import ProductRead
from app.services.import_service import ImportService

router = APIRouter()


@router.get("", response_model=list[ProductRead])
def list_products(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str = "",
    limit: int = Query(default=100, le=500),
) -> list[ProductRead]:
    return ProductRepository(db).list(search=search, limit=limit)


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
