"""Tests for polylibs.parser."""

from pathlib import Path
import pytest
from polylibs.parser import ball_id_to_indices, find_device_csv, parse_csv
from polylibs.models import Family
from polylibs.parser import _split_device_package, parse_csv_with_mapping
from polylibs.manifest import Series


@pytest.mark.parametrize(
    "full_name, expected_device, expected_pkg",
    [
        ("xc7a100tfgg484", "xc7a100t", "fgg484"),
        ("xc7s50csga324", "xc7s50", "csga324"),
        ("xcku035fbva900", "xcku035", "fbva900"),
        ("xcau10pffvb676", "xcau10p", "ffvb676"),
        ("xczu7evffvc1156", "xczu7ev", "ffvc1156"),
        ("xczu1egsbva484", "xczu1eg", "sbva484"),
    ],
)
def test_split_device_package(full_name, expected_device, expected_pkg):
    device, package = _split_device_package(full_name)
    assert device == expected_device
    assert package == expected_pkg


def test_ball_id_to_indices():
    assert ball_id_to_indices("A1") == (0, 0)
    assert ball_id_to_indices("B2") == (1, 1)
    # Columns are numeric; row labels skip I, O, Q, S, X, Z: A..Y = 0..19,
    # AA = 20, AB = 21.
    assert ball_id_to_indices("AA10") == (9, 20)
    assert ball_id_to_indices("AB1") == (0, 21)


def test_find_device_csv_exact(data_dirs: list[Path]):
    path = find_device_csv("xc7a100tfgg484", data_dirs)
    assert path.exists()
    assert path.stem.lower().startswith("xc7a100tfgg484")


def test_find_device_csv_prefix(data_dirs: list[Path]):
    path = find_device_csv("xc7a100t", data_dirs)
    assert "xc7a100t" in path.stem.lower()


def test_find_device_csv_missing(data_dirs: list[Path]):
    with pytest.raises(FileNotFoundError):
        find_device_csv("notarealdevice123", data_dirs)


def test_parse_csv_7series(data_dirs: list[Path]):
    path = find_device_csv("xc7a100tfgg484", data_dirs)
    device = parse_csv(path)
    assert device.full_name.lower() == "xc7a100tfgg484"
    assert device.family == Family.SERIES_7
    assert device.total_pins > 0
    assert device.pins[0].ball_id != ""


def test_parse_csv_ball_indices(data_dirs: list[Path]):
    path = find_device_csv("xc7a100tfgg484", data_dirs)
    device = parse_csv(path)
    a1 = next(p for p in device.pins if p.ball_id == "A1")
    assert a1.col_index == 0
    assert a1.row_index == 0


def test_parse_csv_with_mapping(tmp_path: Path):
    csv = tmp_path / "pinout.csv"
    csv.write_text("Location,Name,Bank,Type\nA1,VCC,0,POWER\nB1,IO_1,1,LVCMOS33\n")
    series = Series(
        id="s",
        name="S",
        vendor_id="v",
        family=Family.GENERIC,
        data_dirs=[],
        column_map={
            "pin": "Location",
            "pin_name": "Name",
            "bank": "Bank",
            "io_type": "Type",
        },
    )
    device = parse_csv_with_mapping(csv, series)
    assert device.total_pins == 2
    assert device.pins[0].ball_id == "A1"
    assert device.pins[0].pin_name == "VCC"
    assert device.pins[1].io_type == "LVCMOS33"
