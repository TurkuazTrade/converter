from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.export_template import describe_export_template


def analyze_template(path: Path) -> dict[str, Any]:
    return describe_export_template(path)
