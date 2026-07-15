"""Tests for polylibs.manifest."""

from pathlib import Path

import pytest

from polylibs.manifest import load_manifest, validate_manifest


def test_load_manifest_minimal(tmp_path: Path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
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
    vendor, series, models = load_manifest(manifest)
    assert vendor.id == "testvendor"
    assert vendor.name == "TestVendor"
    assert series.id == "testseries"
    assert series.family.name == "GENERIC"
    assert len(models) == 1
    assert models[0].device == "dev1"
    assert models[0].package == "pkg1"
    assert models[0].full_name == "dev1pkg1"


def test_load_manifest_missing_required_columns(tmp_path: Path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
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

models: []
""",
        encoding="utf-8",
    )
    vendor, series, models = load_manifest(manifest)
    with pytest.raises(ValueError, match="missing required keys"):
        validate_manifest(vendor, series, models)


def test_validate_manifest_bad_vendor_id(tmp_path: Path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """
vendor:
  id: "Bad ID"
  name: TestVendor

series:
  id: testseries
  name: TestSeries
  family: GENERIC
  data_dirs: ["."]
  column_map:
    pin: Location
    pin_name: Name
    bank: Bank
    io_type: Type

models: []
""",
        encoding="utf-8",
    )
    vendor, series, models = load_manifest(manifest)
    with pytest.raises(ValueError, match="invalid vendor id"):
        validate_manifest(vendor, series, models)
