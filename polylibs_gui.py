#!/usr/bin/env python3
"""Standalone entry point for the PolyLibs GUI.

Works both as a Python script and as a PyInstaller-packaged .exe.
"""

import sys
from pathlib import Path

# Allow absolute imports of the polylibs package when running this script
# directly from the repo root.
ROOT = Path(__file__).resolve().parent

# Support two layouts:
#   - in-place dev layout: PolyLibs/polylibs/ package next to this script
#   - open-source layout: polylibs/ package at the same level as this script
if (ROOT / "PolyLibs" / "polylibs").is_dir():
    sys.path.insert(0, str(ROOT / "PolyLibs"))
elif (ROOT / "polylibs").is_dir():
    sys.path.insert(0, str(ROOT))
else:
    sys.path.insert(0, str(ROOT / "PolyLibs"))

from polylibs.gui import run_gui  # noqa: E402


# Legacy flat data directories that contain raw Xilinx pinout CSV files.
# Kept for backward compatibility with older deployments that still keep these
# folders next to the executable.
_LEGACY_DATA_DIR_NAMES = [
    "a7all",
    "k7all",
    "s7all/s7all",
    "v7all",
    "usaall",
    "zupall",
    "z7all/7zSeriesALL",
    "versal-all/versal-all",
]

# New hierarchical layout: vendor/series/raw-data folders.
_PINOUT_FILE_DIR = "pinout_file"


def _has_project_root(root: Path) -> bool:
    """Return True if *root* looks like a valid PolyLibs project root."""
    if (root / "library").is_dir():
        return True
    if (root / "data" / "pkg_db.json").is_file():
        return True
    if (root / _PINOUT_FILE_DIR).is_dir():
        return True
    return any((root / d.split("/", 1)[0]).is_dir() for d in _LEGACY_DATA_DIR_NAMES)


def _resolve_data_root() -> Path:
    """Find the project root that contains library/, data/ or pinout_file/.

    When running as a PyInstaller .exe the executable may live in a ``dist/``
    sub-folder; in that case we also check the parent directory so the user can
    run the exe directly or place it next to the runtime data folders.
    """
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.extend([exe_dir.parent, exe_dir])

    candidates.append(ROOT)
    candidates.append(Path.cwd())

    for root in candidates:
        root = root.resolve()
        if _has_project_root(root):
            return root

    # Fall back to the first candidate so the GUI can still launch and show
    # a helpful "no data" message.
    return candidates[0].resolve() if candidates else Path.cwd()


def _build_data_dirs(root: Path) -> list[Path]:
    """Return the data directories to pass to the GUI.

    The manifest-driven layout (library/) is preferred; ``pinout_file/`` is
    detected as a project-root marker above.  The flat legacy directories are
    only used as a fallback for older deployments.
    """
    if (root / "library").is_dir():
        return [root / "library"]
    legacy = [root / d for d in _LEGACY_DATA_DIR_NAMES if (root / d).is_dir()]
    if legacy:
        return legacy
    return []


def main() -> int:
    root = _resolve_data_root()
    data_dirs = _build_data_dirs(root)

    if not data_dirs:
        # Show a simple error dialog before exiting.  Import tkinter here so
        # the message box appears even when the GUI cannot initialise data.
        import tkinter as tk
        from tkinter import messagebox

        tk.Tk().withdraw()
        messagebox.showerror(
            "错误",
            f"找不到项目数据。\n"
            f"请将本程序放在包含 library/ 和 data/ 文件夹的目录中运行。\n"
            f"当前查找位置: {root}",
        )
        return 1

    run_gui(data_dirs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
