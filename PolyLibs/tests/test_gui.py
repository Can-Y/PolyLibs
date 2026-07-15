"""Tests for polylibs.gui."""

from pathlib import Path

import pytest

from polylibs.gui import build_output, GeneratorRegistry, Application
from polylibs.library import LibraryScanner


def test_generator_registry():
    registry = GeneratorRegistry()
    names = [g.name for g in registry.all_generators()]
    assert "PADS" in names
    assert "Cadence" in names
    assert "Altium" in names
    assert "KiCad" in names


def test_build_output_creates_files(tmp_path: Path, data_dirs: list[Path]):
    outdir = tmp_path / "out"
    summary = build_output(
        device_name="xc7a100tfgg484",
        data_dirs=data_dirs,
        output_dir=outdir,
        selected={"PADS": True, "Cadence": False, "Altium": False},
        generate_symbol=True,
        generate_footprint=True,
    )
    assert (outdir / "xc7a100tfgg484" / "pads").exists()
    assert "total_pins" in summary


def test_build_output_overwrite_false_raises(tmp_path: Path, data_dirs: list[Path]):
    outdir = tmp_path / "out"
    build_output(
        device_name="xc7a100tfgg484",
        data_dirs=data_dirs,
        output_dir=outdir,
        selected={"PADS": True, "Cadence": False, "Altium": False},
        generate_symbol=True,
        generate_footprint=True,
    )
    with pytest.raises(FileExistsError):
        build_output(
            device_name="xc7a100tfgg484",
            data_dirs=data_dirs,
            output_dir=outdir,
            selected={"PADS": True, "Cadence": False, "Altium": False},
            generate_symbol=True,
            generate_footprint=True,
            overwrite=False,
        )


def test_build_device_tree_for_gui(tmp_path: Path):
    lib = tmp_path / "library" / "v" / "s"
    lib.mkdir(parents=True)
    (lib / "manifest.yaml").write_text(
        """
vendor:
  id: v
  name: Vendor
series:
  id: s
  name: Series
  family: GENERIC
  data_dirs: ["."]
  column_map:
    pin: Pin
    pin_name: Name
    bank: Bank
    io_type: Type
models:
  - device: dev1
    package: pkg1
    full_name: dev1pkg1
    pinout: dev1/pinout.csv
  - device: dev1
    package: pkg2
    full_name: dev1pkg2
    pinout: dev1pkg2/pinout.csv
""",
        encoding="utf-8",
    )
    tree = LibraryScanner(tmp_path).scan()
    devices = Application._build_device_tree(tree)
    assert "v" in devices
    assert "s" in devices["v"]
    assert devices["v"]["s"]["dev1"] == ["pkg1", "pkg2"]
