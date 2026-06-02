from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.import_service import ImportService

router = APIRouter()


@router.post("/import")
async def import_references(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    converter_type: str | None = None,
    import_products: bool = True,
    import_clients: bool = True,
) -> dict:
    if not import_products and not import_clients:
        raise HTTPException(status_code=400, detail="Select at least one reference type to import")
    result = await ImportService(db, branch_id=current_user.branch_id).import_reference_workbook(
        file,
        converter_type=converter_type,
        import_products=import_products,
        import_clients=import_clients,
    )
    db.commit()
    return result
