from __future__ import annotations


class AppError(Exception):
    """Base application error."""


class StorageError(AppError):
    """Storage layer failed."""


class ConverterError(AppError):
    """Converter failed."""


class MatchingError(AppError):
    """Matching failed."""


class ExportError(AppError):
    """Export failed."""
