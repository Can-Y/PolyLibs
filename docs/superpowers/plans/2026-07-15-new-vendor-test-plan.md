# New Vendor Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task in the current session.

**Goal:** Add a minimal `example/example_series` vendor to the real project layout and a pytest test that proves `LibraryScanner` discovers it.

**Architecture:** Rely entirely on the existing manifest/scanning pipeline. No library code changes are needed; we only add a new manifest, a tiny CSV, and a focused test file.

**Tech Stack:** Python 3.11+, pytest, PyYAML.

## Global Constraints

- Project root: `E:/1_work/15_pinout`.
- All new vendor data lives under `library/example/example_series/` and `pinout_file/example/example_series/`.
- Non-Xilinx vendor must use `family: GENERIC`.
- `column_map` must include required keys: `pin`, `pin_name`, `bank`, `io_type`.
- Existing tests and discovery logic must not be modified.
- Full PolyLibs pytest suite must remain at 70 passing tests.

---

### Task 1: Create the example vendor manifest

**Files:**
- Create: `library/example/example_series/manifest.yaml`

**Interfaces:**
- Consumes: Existing `polylibs.manifest.load_manifest` expects `vendor`, `series`, `column_map`, optional `models`.
- Produces: A valid manifest discovered by `LibraryScanner`.

- [ ] **Step 1: Write the manifest**

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

- [ ] **Step 2: Validate the manifest parses**

Run: `cd PolyLibs && python -m polylibs library validate --root ..`
Expected: No errors for `library/example/example_series/manifest.yaml`.

---

### Task 2: Add the dummy pinout CSV

**Files:**
- Create: `pinout_file/example/example_series/ex1csg324.csv`

**Interfaces:**
- Consumes: The manifest `data_dirs` path and `column_map`.
- Produces: A CSV that `LibraryScanner` auto-discovers as model `ex1csg324`.

- [ ] **Step 1: Write the CSV**

```csv
Pin,Pin Name,Bank,Type
A1,VCC,0,POWER
B1,GND,0,GROUND
A2,IO_0,1,IO
```

- [ ] **Step 2: Verify the scanner finds the model**

Run: `cd PolyLibs && python -m polylibs library scan --root ..`
Expected: Output lists vendor `example`, series `example_series`, and model `ex1csg324`.

---

### Task 3: Add a permanent discovery test

**Files:**
- Create: `PolyLibs/tests/test_new_vendor.py`

**Interfaces:**
- Consumes: The existing `project_root` fixture and `LibraryScanner`.
- Produces: A passing test that guards the new vendor files.

- [ ] **Step 1: Write the test**

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

- [ ] **Step 2: Run the new test**

Run: `cd PolyLibs && python -m pytest tests/test_new_vendor.py -v`
Expected: `test_example_vendor_discovered` passes.

---

### Task 4: Regression-check the full suite

**Files:**
- None.

- [ ] **Step 1: Run the full PolyLibs test suite**

Run: `cd PolyLibs && python -m pytest -q`
Expected: 70 passed (or previous count + 1 if this is a fresh baseline), no failures.

---

## Self-Review

- **Spec coverage:** Each design section maps to a task: manifest (Task 1), CSV (Task 2), test (Task 3), verification (Task 4).
- **Placeholder scan:** No TBDs; all file content and commands are concrete.
- **Type consistency:** Uses existing `project_root` fixture type `Path` and `LibraryScanner.scan()` return type `LibraryTree`.
