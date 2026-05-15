from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"


class FileRole(StrEnum):
    SOURCE = "source"
    EXPORT = "export"
    QUARANTINE = "quarantine"


class StorageBackend(StrEnum):
    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"


class ConverterType(StrEnum):
    PITON = "piton"
    NARODNYI = "narodnyi"
    GLOBUS = "globus"
    SPAR = "spar"
    DOSTOR = "dostor"
    ASIA_RETAIL = "asia_retail"
    DARKSTORE = "darkstore"
    ALMA = "alma"


class OrderStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    READY_TO_EXPORT = "ready_to_export"
    EXPORTED = "exported"
    FAILED = "failed"


class OrderItemStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    INVALID_QUANTITY = "invalid_quantity"
    DUPLICATE = "duplicate"
    SKIPPED = "skipped"


class ProcessingEventType(StrEnum):
    UPLOADED = "uploaded"
    DUPLICATE_DETECTED = "duplicate_detected"
    PARSED = "parsed"
    MATCHED = "matched"
    MAPPING_SAVED = "mapping_saved"
    REPROCESSED = "reprocessed"
    EXPORTED = "exported"
    FAILED = "failed"
