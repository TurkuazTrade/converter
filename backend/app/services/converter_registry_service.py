from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.converters.config_driven import ConfigDrivenConverter
from app.core.enums import ConverterType


class ConverterRegistryService:
    def __init__(self, configs_dir: Path | None = None) -> None:
        self.configs_dir = configs_dir or Path(__file__).resolve().parents[1] / "converters" / "configs"

    def list_configs(self) -> list[dict]:
        return [self.load_config(path.stem) for path in sorted(self.configs_dir.glob("*.json"))]

    def load_config(self, converter_type: str) -> dict:
        path = self.configs_dir / f"{converter_type}.json"
        with path.open("r", encoding="utf-8") as file:
            config = json.load(file)
        base_name = config.get("extends")
        if base_name:
            base = self.load_config(str(base_name))
            config = self._merge_config(base, config)
            config.pop("extends", None)
        return config

    def config_hash(self, converter_type: str) -> str:
        config = self.load_config(converter_type)
        payload = json.dumps(config, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def get_converter(self, converter_type: str) -> ConfigDrivenConverter:
        config = self.load_config(converter_type)
        return ConfigDrivenConverter(config=config, config_hash=self.config_hash(converter_type))

    def detect_converter(self, filename: str, preview_text: str = "") -> ConverterType | None:
        key = f"{filename} {preview_text}".casefold()
        rules = {
            "питон": ConverterType.PITON,
            "piton": ConverterType.PITON,
            "народ": ConverterType.NARODNYI,
            "narod": ConverterType.NARODNYI,
            "глобус": ConverterType.GLOBUS,
            "globus": ConverterType.GLOBUS,
            "globys": ConverterType.GLOBUS,
            "spar": ConverterType.SPAR,
            "спар": ConverterType.SPAR,
            "достор": ConverterType.DOSTOR,
            "dostor": ConverterType.DOSTOR,
            "азия": ConverterType.ASIA_RETAIL,
            "asia": ConverterType.ASIA_RETAIL,
            "dark": ConverterType.DARKSTORE,
            "даркстор": ConverterType.DARKSTORE,
            "алма": ConverterType.ALMA,
            "alma": ConverterType.ALMA,
        }
        for marker, converter_type in rules.items():
            if marker in key:
                return converter_type
        return None

    @staticmethod
    def _merge_config(base: dict, override: dict) -> dict:
        merged = dict(base)
        for key, value in override.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        return merged
