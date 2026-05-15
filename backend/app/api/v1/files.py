from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.files import FileRepository
from app.services.storage_service import LocalStorageService

router = APIRouter()


@router.get("/{file_id}/download")
def download_file(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    file_row = FileRepository(db).get(file_id)
    if file_row is None:
        raise HTTPException(status_code=404, detail="File not found")
    if not file_row.path:
        raise HTTPException(status_code=404, detail="File is not retained on server")
    path = LocalStorageService().get_path(file_row.path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Stored file not found")
    return FileResponse(path, filename=file_row.original_name, media_type=file_row.mime_type)
