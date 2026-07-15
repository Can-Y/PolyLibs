# New Vendor Test Design

**Date:** 2026-07-15  
**Project:** PolyLibs (E:/1_work/15_pinout)  
**Goal:** Add a minimal, real new vendor/series to the project layout and an automated test that proves the discovery/manifest pipeline picks it up.

## Background

`handoff.md` lists the next step as *Add a new vendor/series*: create `pinout_file/<vendor>/<series>/` raw data and `library/<vendor>/<series>/manifest.yaml`, then validate that the scanner discovers it. The existing test suite already contains temporary dummy-vendor examples (`test_library.py::test_scan_library_new_vendor_csv_discovery`, `test_integration.py::test_generate_from_library`), but no permanent vendor exists in the real `library/` / `pinout_file/` tree.

## Design

Add a small, clearly-named example vendor so the GUI/CLI scanner can discover it, plus a pytest test that scans the actual project root and asserts the vendor/series/model are present.

### Files to create

1. `library/example/example_series/manifest.yaml`
2. `pinout_file/example/example_series/ex1csg324.csv`
3. `PolyLibs/tests/test_new_vendor.py`

### Manifest (`library/example/example_series/manifest.yaml`)

```yaml
vendor:
  id: example
  name: ExampleVendor
  display_name: Example Vendor

series:
  id: example_series
  name: ExampleSeries
  family: GENERIC
  data_dirs:
    - pinout_file/example/example_series
  column_map:
    pin: Pin
    pin_name: Pin Name
    bank: Bank
    io_type: Type

models: []
```

### Pinout CSV (`pinout_file/example/example_series/ex1csg324.csv`)

```csv
Pin,Pin Name,Bank,Type
A1,VCC,0,POWER
B1,GND,0,GROUND
A2,IO_0,1,IO
```

The filename `ex1csg324.csv` splits into device `ex1` and package `csg324` using the existing `_split_device_package` heuristic.

### Test (`PolyLibs/tests/test_new_vendor.py`)

```python
"""Test that the example new vendor is discovered in the real project layout."""

from pathlib import Path

from polylibs.library import LibraryScanner


def test_example_vendor_discovered(project_root: Path):
    root = project_root.parent
    tree = LibraryScanner(root).scan()

    assert "example" in tree.vendors
    assert tree.vendors["example"].name == "ExampleVendor"

    assert "example_series" in tree.series
    assert tree.series["example_series"].family.name == "GENERIC"

    models = tree.models["example_series"]
    assert len(models) == 1
    assert models[0].full_name == "ex1csg324"
    assert models[0].device == "ex1"
    assert models[0].package == "csg324"
```

## Verification

1. CLI scan: `cd PolyLibs && python -m polylibs library scan --root ..`
2. CLI validate: `cd PolyLibs && python -m polylibs library validate --root ..`
3. pytest: `cd PolyLibs && python -m pytest tests/test_new_vendor.py -q`
4. Full suite: `cd PolyLibs && python -m pytest -q` (must remain 70 passing).

## Out of scope

- Package dimensions / footprint generation for the dummy model.
- Adding the vendor to `data/pkg_db.json` or the vendor-specific extraction scripts.
- Updating the open-source backup (`PolyLibs-opensource/`) unless explicitly requested.

## Trade-offs

- Keeping the vendor named `example` makes its test purpose obvious and avoids confusion with real vendors.
- Adding real files (not just a temp-dir test) exercises the same paths the GUI and CLI use, matching `handoff.md` step 1.
- The test is independent of temporary fixtures, so it also guards against accidental deletion of the manifest or CSV.
