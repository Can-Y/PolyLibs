# Reduce Distribution Size Design

**Date:** 2026-07-15  
**Project:** PolyLibs (E:/1_work/15_pinout)  
**Goal:** Allow building a smaller `dist/` package that ships only the pinout series a user actually needs.

## Background

- Current `dist/` is ~108 MB; `pinout_file/` accounts for ~90 MB.
- `PolyLibs.spec` copies the entire `data/`, `library/`, and `pinout_file/` trees into `dist/` after PyInstaller builds the executable.
- Many end-users need only one Xilinx series (e.g., 7series ~13 MB, versal ~26 MB), so shipping all six series is wasteful.

## Design

Add a build-time include filter to `PolyLibs.spec` and a small helper script `build_minimal.py` that invokes PyInstaller with the filter.

### Behavior

- By default (`POLYLIBS_PINOUT_INCLUDE` unset), `PolyLibs.spec` continues to copy **all** pinout data — fully backward compatible.
- When `POLYLIBS_PINOUT_INCLUDE` is set to a comma-separated list like `xilinx/7series,xilinx/zynq7000`, the spec copies only those `pinout_file/<vendor>/<series>` subtrees.
- Legacy flat pinout directories are copied only when their corresponding series is included (they are currently archived, so this is mostly defensive).
- `build_minimal.py` accepts `--series xilinx/7series --series xilinx/zynq7000` and/or `--all`, sets the environment variable, runs PyInstaller, and optionally zips the result into `dist_packages/`.

### Files to change / create

1. Modify `PolyLibs.spec`:
   - Read `POLYLIBS_PINOUT_INCLUDE`.
   - Replace the wholesale `shutil.copytree(pinout_file, dist/pinout_file)` with a selective copy over `pinout_file/<vendor>/<series>`.
   - Apply the same filter to legacy flat directories.

2. Create `build_minimal.py`:
   - CLI for selecting series.
   - Sets the environment variable and runs `PyInstaller PolyLibs.spec --noconfirm`.
   - Optionally packages `dist/` into a zip.

### Verification

- Run a full build without the filter: `python PolyLibs.spec` should still produce 108 MB and all 531 models.
- Run a minimal build for `xilinx/7series`: expected `dist/` ~35 MB (19 MB exe + 13 MB data + small overhead).
- Launch `dist/PolyLibs.exe` or run `python -m polylibs library scan --root dist` to confirm only the selected series is discovered.

## Out of scope

- Compressing CSVs inside `dist/`.
- Splitting the executable itself.
- Runtime selection of series in the GUI.
- Updating the open-source backup (`PolyLibs-opensource/`) unless explicitly requested.

## Trade-offs

- **Build-time filter vs. post-build pruning:** Filtering during copy avoids copying unused data, saving build time and disk space during packaging. Post-build pruning is simpler but wasteful.
- **Env var vs. CLI arg:** PyInstaller specs cannot receive CLI args directly; an environment variable is the standard way to parameterize a spec.
- **Backward compatibility:** Default behavior remains full distribution, so existing workflows are unaffected.
