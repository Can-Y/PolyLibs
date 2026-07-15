"""Manifest parsing for vendor/series/models."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import Family


@dataclass(frozen=True)
class Vendor:
    id: str
    name: str
    display_name: str = ""
    aliases: list[str] = field(default_factory=list)


@dataclass
class Series:
    id: str
    name: str
    vendor_id: str
    family: Family
    data_dirs: list[Path]
    column_map: dict[str, str]
    classification: Any = None
    packages: Any = None
    manifest_dir: Path = Path()


@dataclass
class Model:
    device: str
    package: str
    full_name: str
    pinout: Path
    package_spec: Path | None = None
    series_id: str = ""


_ID_RE = re.compile(r"^[a-z0-9_-]+$")


def _parse_family(value: str) -> Family:
    try:
        return Family[value.upper().replace("-", "_")]
    except KeyError as exc:
        raise ValueError(f"Unknown family: {value}") from exc


def load_manifest(path: Path, root: Path | None = None) -> tuple[Vendor, Series, list[Model]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest.yaml must contain a YAML mapping")

    raw_vendor = data.get("vendor", {})
    vendor = Vendor(
        id=str(raw_vendor.get("id", "")).strip(),
        name=str(raw_vendor.get("name", "")).strip(),
        display_name=str(raw_vendor.get("display_name", "")).strip(),
        aliases=list(raw_vendor.get("aliases", [])),
    )

    raw_series = data.get("series", {})
    manifest_dir = path.resolve().parent
    data_root = root.resolve() if root else manifest_dir
    raw_packages = raw_series.get("packages")
    if isinstance(raw_packages, str):
        raw_packages = manifest_dir / raw_packages
    raw_classification = raw_series.get("classification")
    if isinstance(raw_classification, str):
        raw_classification = manifest_dir / raw_classification
    series = Series(
        id=str(raw_series.get("id", "")).strip(),
        name=str(raw_series.get("name", "")).strip(),
        vendor_id=vendor.id,
        family=_parse_family(raw_series.get("family", "GENERIC")),
        data_dirs=[(data_root / d).resolve() for d in raw_series.get("data_dirs", [])],
        column_map=dict(raw_series.get("column_map", {})),
        classification=raw_classification,
        packages=raw_packages,
        manifest_dir=manifest_dir,
    )

    models: list[Model] = []
    for raw_model in data.get("models", []):
        device = str(raw_model.get("device", "")).strip()
        package = str(raw_model.get("package", "")).strip()
        full_name = str(raw_model.get("full_name", "") or f"{device}{package}").strip()
        pinout = raw_model.get("pinout", "")
        package_spec = raw_model.get("package_spec")
        models.append(
            Model(
                device=device,
                package=package,
                full_name=full_name,
                pinout=(manifest_dir / pinout).resolve(),
                package_spec=(manifest_dir / package_spec).resolve() if package_spec else None,
                series_id=series.id,
            )
        )

    return vendor, series, models


def validate_manifest(vendor: Vendor, series: Series, models: list[Model]) -> None:
    if not vendor.id or not _ID_RE.match(vendor.id):
        raise ValueError(f"invalid vendor id: {vendor.id!r}")
    if not vendor.name:
        raise ValueError("vendor.name is required")
    if not series.id or not _ID_RE.match(series.id):
        raise ValueError(f"invalid series id: {series.id!r}")
    if not series.name:
        raise ValueError("series.name is required")
    required_columns = {"pin", "pin_name", "bank", "io_type"}
    missing = required_columns - set(series.column_map.keys())
    if missing:
        raise ValueError(f"series.column_map missing required keys: {missing}")
    for model in models:
        if not model.device or not model.package:
            raise ValueError(f"model {model.full_name!r} missing device or package")
