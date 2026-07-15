# Session Handoff

**Date:** 2026-07-15
**Project:** E:/1_work/16_pinout (PolyLibs)
**Status:** Initial release layout finalized; PolyLibs.exe rebuilt and verified

## What Was Done

### 1. Hierarchical pinout data layout
Created `pinout_file/` and moved all raw pinout CSV folders out of the project root:

```text
pinout_file/
└── xilinx/
    ├── 7series/
    │   ├── a7all/
    │   ├── k7all/
    │   ├── s7all/s7all/
    │   └── v7all/
    ├── ultrascale/usaall/
    ├── ultrascale_plus/usaall/
    ├── versal/versal-all/versal-all/
    ├── zynq7000/z7all/7zSeriesALL/
    └── zynq_us_plus/zupall/zupall/
```

The mixed `usaall/` directory was split by device prefix:
- `xc[kv]u\d+` (no trailing `p`) → `ultrascale/usaall/`
- `xcau*`, `x[ckqr]u*p*` → `ultrascale_plus/usaall/`

### 2. Updated all path references
- `library/xilinx/*/manifest.yaml` — `data_dirs` now point under `pinout_file/xilinx/...`
- `polylibs_gui.py` — root detection recognizes `library/`, `data/`, and `pinout_file/`; prefers manifest-driven `library/`
- `PolyLibs.spec` — post-build copies `pinout_file/` (plus legacy flat dirs as fallback)
- `PolyLibs/polylibs/gui.py` — `_SERIES_DIR_MAP`, default `run_gui()` dirs, user-facing error message
- `PolyLibs/tests/conftest.py`, `tests/test_scaffold.py` — fixtures reflect new paths
- `PolyLibs/scripts/extend_pkg_db.py` — scans `pinout_file/xilinx/...`
- `update_pkg_db.py` — data_dirs updated
- All corresponding files synced to `PolyLibs-opensource/`

### 3. Archived old fpga2cad project
Moved the following out of the project root into `archive/`:
- `fpga2cad/`
- `fpga2cad.bat`
- `build_exe.py`
- `fpga2cad.spec`
- `fpga2cad_new.spec`
- `test_cadence_gen.py`
- old `dist/output/` backup

### 4. Cleaned root clutter
Deleted: `__pycache__/`, `build/`, `allegro_25.1_P001_4349869_AllegroMiniDump.dmp`, `=6.0`, and moved reference PDFs/txt files into `docs/references/`.

### 5. Rebuilt distribution
- Ran `python -m PyInstaller PolyLibs.spec --noconfirm`
- New `dist/` contains only:
  - `PolyLibs.exe`
  - `data/`
  - `library/`
  - `pinout_file/`
- Verified portability by copying `dist/` to a temp directory, renaming it, and simulating frozen execution — models are discovered correctly.

## Test / Verification Results

| Suite | Result |
|-------|--------|
| `cd PolyLibs && python -m pytest -q` | **70 passed** |
| `cd PolyLibs-opensource && python -m pytest -q` | **70 passed** |
| Portable `dist/` scan | **531 unique models** across 6 Xilinx series |

Scan breakdown from portable verification:
- 7series: 96
- ultrascale: 50
- ultrascale_plus: 79
- versal: 139
- zynq7000: 22
- zynq_us_plus: 145
- **Total: 531**

## Current Root Layout

```text
E:/1_work/16_pinout/
├── PolyLibs/                  # Main development package (has .git)
├── PolyLibs-opensource/       # Backup copy prepared for open-source release
├── archive/                   # Old fpga2cad project and old dist/output
├── data/                      # pkg_db.json and related runtime data
├── dist/                      # Standalone distribution (exe + data)
├── docs/                      # Documentation and references/
├── library/                   # Vendor/series manifest.yaml files
├── output/                    # Generated library outputs / verification samples
├── pinout_file/               # Hierarchical raw pinout CSV data
├── .venv/                     # Python virtual environment
├── .superpowers/              # Kimi Code session config
├── FPGAer_Zone_258.jpg        # QR code image bundled in the exe
├── PolyLibs.spec              # PyInstaller spec
├── polylibs_gui.py            # GUI entry point
├── handoff.md                 # This file
├── extract_pkg_specs.py       # CSV extraction helpers
├── extract_all_pkg_specs.py
├── update_pkg_db.py
├── batch_footprints.py        # Batch footprint generation
├── batch_generate.py          # Batch full library generation
├── verify_batch.py
└── verify_footprint.py
```

## Known State

- `dist/` is self-contained and can be copied/renamed independently.
- `PolyLibs.exe` resolves its project root from `sys.executable` parent and finds `library/` + `pinout_file/`.
- `fpga2cad` is archived; the old `dist/fpga2cad_new.exe` is no longer rebuilt.
- No failing tests.

## Possible Next Steps

1. **Add a new vendor/series**:
   - Create `pinout_file/<vendor>/<series>/<raw_data_dir>/` with CSV/TXT pinout files.
   - Create `library/<vendor>/<series>/manifest.yaml` with `vendor`, `series`, `data_dirs`, and `column_map`.
   - Re-run `python -m PyInstaller PolyLibs.spec --noconfirm` only if the exe itself needs updating; otherwise just distribute the updated `dist/` contents.

2. **Polish the open-source backup**:
   - Decide whether `PolyLibs-opensource/` should become the GitHub repo root or remain a backup.
   - If making it the repo root, rename to `PolyLibs/` and delete the nested copy.
   - Add a top-level `.gitignore`, `LICENSE`, and `README.md` tailored for GitHub.

3. **Reduce distribution size**:
   - `dist/` is ~108 MB; `pinout_file/` accounts for ~90 MB.
   - For a minimal installer, ship only the series the user actually needs.

4. **GUI/UX improvements**:
   - Pre-fill advanced dimension defaults from package registry.
   - Add vendor selection dropdown above series selection.
   - Display the FPGAer_Zone image and text in the About pane.
