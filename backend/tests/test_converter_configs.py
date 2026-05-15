from __future__ import annotations

from app.services.converter_registry_service import ConverterRegistryService


def test_converter_configs_load() -> None:
    service = ConverterRegistryService()
    configs = service.list_configs()
    types = {config["type"] for config in configs}
    assert types == {
        "piton",
        "narodnyi",
        "globus",
        "spar",
        "dostor",
        "asia_retail",
        "darkstore",
        "alma",
    }
    for config in configs:
        assert config["version"]
        assert service.config_hash(config["type"])
