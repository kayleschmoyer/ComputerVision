from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppConfig:
    raw: dict[str, Any]

    @property
    def camera(self) -> dict[str, Any]:
        return self.raw["camera"]

    @property
    def model(self) -> dict[str, Any]:
        return self.raw["model"]

    @property
    def zones(self) -> dict[str, Any]:
        return self.raw["zones"]

    @property
    def rules(self) -> dict[str, Any]:
        return self.raw["rules"]

    @property
    def events(self) -> dict[str, Any]:
        return self.raw["events"]

    @property
    def api(self) -> dict[str, Any]:
        return self.raw["api"]


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)
    return AppConfig(raw=raw_config)
