# Reduce Distribution Size Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task in the current session.

**Goal:** Add a build-time pinout filter so `dist/` can be built with only selected series, dramatically reducing package size.

**Architecture:** Parameterize `PolyLibs.spec` with an environment variable `POLYLIBS_PINOUT_INCLUDE`. Add a helper `build_minimal.py` to set the variable and run PyInstaller. Default behavior remains unchanged.

**Tech Stack:** Python 3.11+, PyInstaller, standard library (`shutil`, `pathlib`, `os`, `subprocess`, `argparse`).

## Global Constraints

- Default build must remain a full distribution (~108 MB) for backward compatibility.
- Filter syntax: comma-separated vendor/series paths, e.g. `xilinx/7series,xilinx/zynq7000`.
- Legacy flat directories are only copied when their mapped series is included.
- No runtime code changes; the GUI/CLI discovery logic stays the same.
- Built `dist/` must still pass `python -m polylibs library scan --root dist` for the selected series.

---

### Task 1: Add selective pinout copy to `PolyLibs.spec`

**Files:**
- Modify: `PolyLibs.spec`

**Interfaces:**
- Consumes: `POLYLIBS_PINOUT_INCLUDE` environment variable.
- Produces: Selective copy of `pinout_file/` into `dist/pinout_file/`.

- [ ] **Step 1: Parse the include filter**

Add near the top of the post-build block:

```python
import os

_PINOUT_INCLUDE = os.environ.get("POLYLIBS_PINOUT_INCLUDE")
if _PINOUT_INCLUDE:
    _included_series = {
        tuple(part.strip().strip("/").split("/"))
        for part in _PINOUT_INCLUDE.split(",")
        if part.strip()
    }
else:
    _included_series = None
```

- [ ] **Step 2: Replace wholesale pinout copy with selective copy**

Replace:

```python
_PINOUT_DIR = 'pinout_file'
if Path(_PINOUT_DIR).exists():
    shutil.copytree(_PINOUT_DIR, dist_dir / _PINOUT_DIR, dirs_exist_ok=True)
```

with:

```python
_PINOUT_DIR = Path('pinout_file')
_PINOUT_DST = dist_dir / _PINOUT_DIR
if _PINOUT_DIR.exists():
    _PINOUT_DST.mkdir(parents=True, exist_ok=True)
    for vendor_dir in sorted(_PINOUT_DIR.iterdir()):
        if not vendor_dir.is_dir():
            continue
        for series_dir in sorted(vendor_dir.iterdir()):
            if not series_dir.is_dir():
                continue
            key = (vendor_dir.name, series_dir.name)
            if _included_series is None or key in _included_series:
                shutil.copytree(
                    series_dir,
                    _PINOUT_DST / vendor_dir.name / series_dir.name,
                    dirs_exist_ok=True,
                )
```

- [ ] **Step 3: Filter legacy flat directories**

Replace the `_LEGACY_DATA_DIRS` loop with a filtered version:

```python
_LEGACY_DATA_DIRS = {
    'a7all': ('xilinx', '7series'),
    'k7all': ('xilinx', '7series'),
    's7all/s7all': ('xilinx', '7series'),
    'v7all': ('xilinx', '7series'),
    'usaall': ('xilinx', 'ultrascale'),
    'zupall': ('xilinx', 'zynq_us_plus'),
    'z7all/7zSeriesALL': ('xilinx', 'zynq7000'),
    'versal-all/versal-all': ('xilinx', 'versal'),
}
for src_name, key in _LEGACY_DATA_DIRS.items():
    if _included_series is not None and key not in _included_series:
        continue
    src_path = Path(src_name)
    if src_path.exists():
        shutil.copytree(src_path, dist_dir / src_path, dirs_exist_ok=True)
```

- [ ] **Step 4: Test backward compatibility**

Run: `cd PolyLibs && ./.venv/Scripts/python -m PyInstaller ../PolyLibs.spec --noconfirm`
Expected: `dist/` still contains all pinout series and `dist/PolyLibs.exe` launches.

---

### Task 2: Create `build_minimal.py`

**Files:**
- Create: `build_minimal.py`

**Interfaces:**
- Consumes: CLI series selection.
- Produces: A filtered `dist/` and optionally a zip in `dist_packages/`.

- [ ] **Step 1: Write the helper script**

```python
#!/usr/bin/env python3
"""Build a minimal PolyLibs distribution with only selected pinout series."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a minimal PolyLibs dist with selected pinout series."
    )
    parser.add_argument(
        "--series",
        action="append",
        help="Vendor/series to include, e.g. xilinx/7series (repeatable).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include all series (default full build).",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Package the resulting dist/ into dist_packages/PolyLibs_<label>.zip.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove dist/ before building.",
    )
    args = parser.parse_args()

    if not args.all and not args.series:
        parser.error("Specify --series at least once or use --all.")

    include_value = "all" if args.all else ",".join(args.series)
    env = os.environ.copy()
    if not args.all:
        env["POLYLIBS_PINOUT_INCLUDE"] = include_value

    project_root = Path(__file__).resolve().parent
    dist_dir = project_root / "dist"

    if args.clean and dist_dir.exists():
        shutil.rmtree(dist_dir)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "PolyLibs.spec",
        "--noconfirm",
    ]
    print(f"Building with POLYLIBS_PINOUT_INCLUDE={include_value!r}")
    subprocess.run(cmd, cwd=project_root, env=env, check=True)

    if args.zip:
        label = "all" if args.all else "_".join(
            s.replace("/", "_") for s in args.series
        )
        packages_dir = project_root / "dist_packages"
        packages_dir.mkdir(exist_ok=True)
        zip_path = packages_dir / f"PolyLibs_{label}"
        if zip_path.with_suffix(".zip").exists():
            zip_path.with_suffix(".zip").unlink()
        shutil.make_archive(str(zip_path), "zip", str(dist_dir))
        print(f"Packaged: {zip_path}.zip")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Make the script executable**

On Windows this is not required; running `python build_minimal.py --series xilinx/7series` is sufficient.

---

### Task 3: Verify minimal build

**Files:**
- None.

- [ ] **Step 1: Build for a single series**

Run: `cd /e/1_work/15_pinout && PolyLibs/.venv/Scripts/python build_minimal.py --series xilinx/7series --clean`
Expected: PyInstaller completes, `dist/pinout_file/` contains only `xilinx/7series`.

- [ ] **Step 2: Check size**

Run: `du -sh dist dist/pinout_file`
Expected: `dist/` roughly 35-40 MB instead of 108 MB.

- [ ] **Step 3: Verify discovery**

Run: `cd dist && PolyLibs/.venv/Scripts/python -m polylibs library scan --root .`
Expected: Only `xilinx/7series` models are listed.

---

## Self-Review

- **Spec coverage:** Build-time filter (Task 1), helper script (Task 2), verification (Task 3) cover all design sections.
- **Placeholder scan:** No TBD/TODO; all code and commands are concrete.
- **Type consistency:** Uses `Path`, `shutil.copytree`, and `subprocess.run` consistently.
