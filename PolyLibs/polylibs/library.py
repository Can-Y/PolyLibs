"""Library scanning and tree building."""

from dataclasses import dataclass, field
from pathlib import Path

from .manifest import Vendor, Series, Model, load_manifest
from .parser import _split_device_package


@dataclass
class LibraryTree:
    vendors: dict[str, Vendor] = field(default_factory=dict)
    series: dict[str, Series] = field(default_factory=dict)
    models: dict[str, list[Model]] = field(default_factory=dict)

    def series_for_vendor(self, vendor_id: str) -> list[Series]:
        return [s for s in self.series.values() if s.vendor_id == vendor_id]

    def models_for_series(self, series_id: str) -> list[Model]:
        return self.models.get(series_id, [])


class LibraryScanner:
    def __init__(self, root: Path):
        self.root = root
        self.library_root = root / "library"

    def scan(self) -> LibraryTree:
        tree = LibraryTree()
        if not self.library_root.exists():
            return tree

        for manifest_path in sorted(self.library_root.rglob("manifest.yaml")):
            vendor, series, explicit_models = load_manifest(manifest_path, root=self.root)
            tree.vendors[vendor.id] = vendor
            tree.series[series.id] = series

            models: list[Model] = []
            seen: set[str] = set()
            for model in explicit_models:
                model.series_id = series.id
                models.append(model)
                seen.add(model.full_name.lower())

            for data_dir in series.data_dirs:
                if not data_dir.exists():
                    continue
                for csv_file in data_dir.glob("**/*.csv"):
                    stem = csv_file.stem.lower()
                    if stem.endswith("pkg"):
                        stem = stem[:-3]
                    device, package = _split_device_package(stem)
                    full_name = f"{device}{package}"
                    if full_name.lower() in seen:
                        continue
                    models.append(
                        Model(
                            device=device,
                            package=package,
                            full_name=full_name,
                            pinout=csv_file,
                            series_id=series.id,
                        )
                    )
                    seen.add(full_name.lower())

            tree.models[series.id] = sorted(models, key=lambda m: m.full_name)

        return tree
