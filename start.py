#!/usr/bin/env python3
"""Check dependencies and launch the PolyLibs GUI."""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


# Runtime dependencies for the GUI. Format: (pip package name, import module name).
REQUIRED: list[tuple[str, str]] = [
    ("PyYAML", "yaml"),
    ("Pillow", "PIL"),
]


def _is_installed(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _install(packages: list[str]) -> None:
    cmd = [sys.executable, "-m", "pip", "install"]
    # Use --user when running from the system interpreter to avoid permission issues.
    if sys.prefix == sys.base_prefix:
        cmd.append("--user")
    cmd.extend(packages)
    print(f"Installing missing packages: {packages}")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


def _check_tkinter() -> bool:
    if not _is_installed("tkinter"):
        print(
            "Error: tkinter is required but not installed. "
            "It is usually bundled with Python on Windows; reinstall Python if missing.",
            file=sys.stderr,
        )
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check dependencies and start the PolyLibs GUI."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check/install dependencies and exit (do not launch GUI).",
    )
    args = parser.parse_args()

    if not _check_tkinter():
        return 1

    missing = [pkg for pkg, mod in REQUIRED if not _is_installed(mod)]
    if missing:
        _install(missing)
    else:
        print("All dependencies are already installed.")

    if args.check:
        return 0

    gui_script = Path(__file__).resolve().with_name("polylibs_gui.py")
    if not gui_script.is_file():
        print(f"Error: {gui_script} not found.", file=sys.stderr)
        return 1

    print(f"Starting {gui_script.name}...")
    subprocess.run([sys.executable, str(gui_script)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
