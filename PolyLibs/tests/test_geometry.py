"""Tests for polylibs.geometry."""

import json
from pathlib import Path
from polylibs.models import PinRecord, Family, PackageSpec
from polylibs.geometry import get_package_spec, compute_ball_coordinates, get_grid_bounds, PackageRegistry


def test_pkg_db_exists(project_root: Path):
    db_path = project_root / "data" / "pkg_db.json"
    assert db_path.exists()
    db = json.loads(db_path.read_text(encoding="utf-8"))
    assert "fgg484" in db
    assert db["fgg484"]["pitch_mm"] == 1.0


def test_get_package_spec_known():
    spec = get_package_spec("fgg484")
    assert spec.pitch_mm == 1.0
    assert spec.body_size_x == 23.0


def test_get_package_spec_unknown_ball_count():
    spec = get_package_spec("xyz999", ball_count=484)
    assert spec.pitch_mm == 1.0
    assert spec.body_size_x > 0


def test_get_package_spec_prefix_fuzzy_lookup():
    # A suffix-only match would incorrectly return a fine-pitch package; the
    # prefix-aware lookup should stay within the same family.
    spec = get_package_spec("tfgg484", ball_count=484)
    assert spec.pitch_mm == 1.0
    assert abs(spec.body_size_x - 23.0) < 3.0


def test_get_package_spec_prefix_heuristic():
    # sbva484 is not in the exact database; the prefix heuristic should give a
    # finer pitch than the generic ball-count heuristic.
    spec = get_package_spec("sbva484", ball_count=484)
    assert spec.pitch_mm == 0.8


def test_get_package_spec_override():
    spec = get_package_spec("fgg484", override_pitch=0.8)
    assert spec.pitch_mm == 0.8


def test_compute_ball_coordinates():
    pins = [
        PinRecord("A1", "IO", "NA", "NA", Family.SERIES_7, col_index=0, row_index=0),
        PinRecord("A2", "IO", "NA", "NA", Family.SERIES_7, col_index=0, row_index=1),
        PinRecord("B1", "IO", "NA", "NA", Family.SERIES_7, col_index=1, row_index=0),
    ]
    spec = PackageSpec(1.0, 10.0, 10.0, 0.4, 0.5, 0.35)
    coords = compute_ball_coordinates(pins, spec)
    assert coords["A1"] == (-0.5, 0.5)
    assert coords["A2"] == (-0.5, -0.5)
    assert coords["B1"] == (0.5, 0.5)


def test_get_grid_bounds():
    pins = [
        PinRecord("A1", "IO", "NA", "NA", Family.SERIES_7, col_index=0, row_index=0),
        PinRecord("C3", "IO", "NA", "NA", Family.SERIES_7, col_index=2, row_index=2),
    ]
    assert get_grid_bounds(pins) == (0, 2, 0, 2)


def test_package_registry_external_and_override(tmp_path: Path):
    db = tmp_path / "pkg_db.json"
    db.write_text(
        '{"fgg484": {"pitch_mm": 1.0, "body_size_x": 23, "body_size_y": 23, "pad_diameter_mm": 0.45, "mask_opening_mm": 0.5, "paste_diameter_mm": 0.4}}'
    )
    reg = PackageRegistry(tmp_path)
    spec = reg.get_spec("fgg484")
    assert spec.pitch_mm == 1.0

    reg.add_series_packages(
        {
            "fgg484": {
                "pitch_mm": 0.8,
                "body_size_x": 15,
                "body_size_y": 15,
                "pad_diameter_mm": 0.4,
                "mask_opening_mm": 0.45,
                "paste_diameter_mm": 0.35,
            }
        }
    )
    spec2 = reg.get_spec("fgg484")
    assert spec2.pitch_mm == 0.8
