"""End-to-end integration tests."""

import json
from pathlib import Path

from polylibs.gui import build_output, build_output_from_library
from polylibs.geometry import PackageRegistry
from polylibs.library import LibraryScanner


def test_end_to_end_xc7a100tfgg484(tmp_path: Path, data_dirs: list[Path]):
    outdir = tmp_path / "out"
    summary = build_output(
        device_name="xc7a100tfgg484",
        data_dirs=data_dirs,
        output_dir=outdir,
        selected={"PADS": True, "Cadence": True, "Altium": True},
        generate_symbol=True,
        generate_footprint=True,
    )
    assert summary["total_pins"] > 0
    device_dir = outdir / "xc7a100tfgg484"
    assert device_dir.exists()
    assert (device_dir / "pads").exists()
    assert (device_dir / "cadence").exists()
    assert (device_dir / "altium").exists()
    assert (device_dir / "report.txt").exists()


def test_end_to_end_xcku035fbva900(tmp_path: Path, data_dirs: list[Path]):
    outdir = tmp_path / "out"
    summary = build_output(
        device_name="xcku035fbva900",
        data_dirs=data_dirs,
        output_dir=outdir,
        selected={"PADS": True, "Cadence": True, "Altium": True},
        generate_symbol=True,
        generate_footprint=True,
    )
    assert summary["total_pins"] > 0


def test_end_to_end_xcau10pffvb676(tmp_path: Path, data_dirs: list[Path]):
    outdir = tmp_path / "out"
    summary = build_output(
        device_name="xcau10pffvb676",
        data_dirs=data_dirs,
        output_dir=outdir,
        selected={"PADS": True, "Cadence": True, "Altium": True},
        generate_symbol=True,
        generate_footprint=True,
    )
    assert summary["total_pins"] > 0


def test_generate_from_library(tmp_path: Path):
    # Create an external data root with a package database.
    db = tmp_path / "data" / "pkg_db.json"
    db.parent.mkdir(parents=True)
    db.write_text(
        json.dumps(
            {
                "pg484": {
                    "pitch_mm": 1.0,
                    "body_size_x": 23.0,
                    "body_size_y": 23.0,
                    "pad_diameter_mm": 0.45,
                    "mask_opening_mm": 0.5,
                    "paste_diameter_mm": 0.4,
                }
            }
        ),
        encoding="utf-8",
    )

    lib = tmp_path / "library" / "testvendor" / "testseries"
    lib.mkdir(parents=True)
    model_dir = lib / "dev1pkg1"
    model_dir.mkdir()
    (model_dir / "pinout.csv").write_text(
        "Location,Pin Name,Bank,I/O Type\n"
        "A1,VCC,0,POWER\n"
        "B1,GND,0,GROUND\n"
        "A2,IO_0,1,LVCMOS33\n",
        encoding="utf-8",
    )
    (lib / "manifest.yaml").write_text(
        """
vendor:
  id: testvendor
  name: TestVendor
series:
  id: testseries
  name: TestSeries
  family: GENERIC
  data_dirs: ["."]
  column_map:
    pin: Location
    pin_name: Pin Name
    bank: Bank
    io_type: I/O Type
models:
  - device: dev1
    package: pkg1
    full_name: dev1pkg1
    pinout: dev1pkg1/pinout.csv
""",
        encoding="utf-8",
    )

    tree = LibraryScanner(tmp_path).scan()
    series = tree.series["testseries"]
    model = tree.models["testseries"][0]
    registry = PackageRegistry(tmp_path).load()

    outdir = tmp_path / "out"
    summary = build_output_from_library(
        model=model,
        series=series,
        output_dir=outdir,
        registry=registry,
        selected={"PADS": True},
        generate_symbol=True,
        generate_footprint=True,
    )
    assert summary["total_pins"] == 3
    device_dir = outdir / "dev1pkg1"
    assert device_dir.exists()
    assert (device_dir / "pads").exists()
    assert (device_dir / "report.txt").exists()
