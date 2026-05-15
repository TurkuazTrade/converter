from __future__ import annotations

from app.converters.config_driven import ConfigDrivenConverter
from app.services.converter_registry_service import ConverterRegistryService


class ConverterRegistry:
    def __init__(self, service: ConverterRegistryService | None = None) -> None:
        self.service = service or ConverterRegistryService()

    def get(self, converter_type: str) -> ConfigDrivenConverter:
        config = self.service.load_config(converter_type)
        return ConfigDrivenConverter(config=config, config_hash=self.service.config_hash(converter_type))

    def all(self) -> list[ConfigDrivenConverter]:
        return [self.get(config["type"]) for config in self.service.list_configs()]
