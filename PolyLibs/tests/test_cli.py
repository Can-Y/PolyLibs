"""Tests for polylibs.cli."""

from pathlib import Path

from polylibs.cli import main as cli_main


def _make_library(root: Path) -> None:
    lib = root / "library" / "testvendor" / "testseries"
    lib.mkdir(parents=True)
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
    pin_name: Name
    bank: Bank
    io_type: Type

models: []
""",
        encoding="utf-8",
    )


def test_scan_cli(tmp_path: Path):
    _make_library(tmp_path)
    result = cli_main(["library", "scan", "--root", str(tmp_path)])
    assert result == 0


def test_validate_cli(tmp_path: Path):
    _make_library(tmp_path)
    result = cli_main(["library", "validate", "--root", str(tmp_path)])
    assert result == 0


def test_validate_cli_bad_manifest(tmp_path: Path):
    lib = tmp_path / "library" / "bad" / "badseries"
    lib.mkdir(parents=True)
    (lib / "manifest.yaml").write_text(
        "vendor:\n  id: bad id\nseries:\n  id: s\n  name: S\n  family: GENERIC\n  data_dirs: [\".\"]\n  column_map:\n    pin: P\nmodels: []\n",
        encoding="utf-8",
    )
    result = cli_main(["library", "validate", "--root", str(tmp_path)])
    assert result == 1


def test_add_package_cli(tmp_path: Path):
    result = cli_main(
        [
            "add-package",
            "--root",
            str(tmp_path),
            '{"testpkg": {"pitch_mm": 1.0, "body_size_x": 10, "body_size_y": 10, "pad_diameter_mm": 0.5, "mask_opening_mm": 0.55, "paste_diameter_mm": 0.45}}',
        ]
    )
    assert result == 0
    assert (tmp_path / "data" / "pkg_db.json").exists()
