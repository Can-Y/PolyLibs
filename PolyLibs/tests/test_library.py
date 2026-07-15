"""Tests for polylibs.library."""

from pathlib import Path

from polylibs.library import LibraryScanner


def test_scan_library(tmp_path: Path):
    lib = tmp_path / "library" / "gowin" / "gw2a"
    lib.mkdir(parents=True)
    (lib / "manifest.yaml").write_text(
        """
vendor:
  id: gowin
  name: Gowin
series:
  id: gw2a
  name: GW2A
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
""",
        encoding="utf-8",
    )
    tree = LibraryScanner(tmp_path).scan()
    assert "gowin" in tree.vendors
    assert "gw2a" in tree.series
    assert len(tree.models["gw2a"]) == 1
    assert tree.models["gw2a"][0].full_name == "dev1pkg1"


def test_scan_library_fallback_when_no_library(tmp_path: Path):
    tree = LibraryScanner(tmp_path).scan()
    assert tree.vendors == {}
    assert tree.series == {}
    assert tree.models == {}


def test_scan_library_new_vendor_csv_discovery(tmp_path: Path):
    """A new vendor with data_dirs is discovered and its CSVs are parsed."""
    from polylibs.parser import parse_csv_with_mapping
    from polylibs.manifest import load_manifest

    root = tmp_path
    lib = root / "library" / "lattice" / "ecp5"
    lib.mkdir(parents=True)
    data_dir = root / "pinout_file" / "lattice" / "ecp5" / "cabga256"
    data_dir.mkdir(parents=True)

    (lib / "manifest.yaml").write_text(
        """
vendor:
  id: lattice
  name: Lattice Semiconductor
  display_name: Lattice

series:
  id: ecp5
  name: ECP5
  family: GENERIC
  data_dirs:
    - pinout_file/lattice/ecp5/cabga256
  column_map:
    pin: Pin
    pin_name: Pin Name
    bank: Bank
    io_type: Type

models: []
""",
        encoding="utf-8",
    )

    (data_dir / "ecp5u25cabga324.csv").write_text(
        "Pin,Pin Name,Bank,Type\n"
        "A1,VCCIO_0,0,POWER\n"
        "A2,IO,1,IO\n"
        "B1,GND,NA,GROUND\n",
        encoding="utf-8",
    )

    tree = LibraryScanner(root).scan()
    assert "lattice" in tree.vendors
    assert tree.vendors["lattice"].display_name == "Lattice"
    assert "ecp5" in tree.series
    assert tree.series["ecp5"].family.name == "GENERIC"

    models = tree.models["ecp5"]
    assert len(models) == 1
    assert models[0].full_name == "ecp5u25cabga324"
    assert models[0].device == "ecp5u25"
    assert models[0].package == "cabga324"
    assert models[0].pinout == data_dir / "ecp5u25cabga324.csv"

    vendor, series, _ = load_manifest(lib / "manifest.yaml", root=root)
    pinout = parse_csv_with_mapping(models[0].pinout, series)
    assert pinout.full_name == "ecp5u25cabga324"
    assert pinout.total_pins == 3
    assert pinout.pins[0].ball_id == "A1"
    assert pinout.pins[0].pin_name == "VCCIO_0"
    assert pinout.pins[0].bank == "0"
    assert pinout.pins[0].io_type == "POWER"
