from __future__ import annotations

from functools import cached_property
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Turkuaz CRM"
    environment: str = "development"
    database_url: str = "sqlite:///../data/app.db"
    secret_key: str = "dev-change-me-32-byte-secret-key-for-turkuaz-crm"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    auto_create_admin: bool = True
    default_admin_email: str = "admin@example.com"
    default_admin_password: str = "admin123"
    default_admin_full_name: str = "Admin"
    default_test_user_login: str = "user"
    default_test_user_email: str = "user@example.com"
    default_test_user_password: str = "password"
    default_test_user_full_name: str = "Test User"
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    storage_root: Path = Path("../data/storage")
    template_path: Path = Path("../data/templates/template_zakaz.xlsx")
    retain_source_files: bool = False

    @cached_property
    def source_storage_dir(self) -> Path:
        return self.storage_root / "source"

    @cached_property
    def export_storage_dir(self) -> Path:
        return self.storage_root / "export"

    @cached_property
    def quarantine_storage_dir(self) -> Path:
        return self.storage_root / "quarantine"

    def ensure_directories(self) -> None:
        self.source_storage_dir.mkdir(parents=True, exist_ok=True)
        self.export_storage_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_storage_dir.mkdir(parents=True, exist_ok=True)
        self.template_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
