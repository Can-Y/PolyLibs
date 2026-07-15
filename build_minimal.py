#!/usr/bin/env python3
"""Build a minimal PolyLibs distribution with only selected pinout series.

Runtime pinout data lives under the project-root ``pinout_file/`` directory.
This script rebuilds the PyInstaller executable if needed, copies the resulting
``dist/`` tree to the output directory, then overlays ``pinout_file/`` from the
project root (either the full tree with ``--all`` or only the requested series).
"""

import argparse
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
        help="Package the resulting minimal dist into dist_packages/PolyLibs_<label>.zip.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the PyInstaller step; use the existing dist/ as source.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for the minimal dist (default: dist_minimal).",
    )
    args = parser.parse_args()

    if not args.all and not args.series:
        parser.error("Specify --series at least once or use --all.")

    project_root = Path(__file__).resolve().parent
    src_dist = project_root / "dist"
    src_pinout = project_root / "pinout_file"

    if not src_pinout.is_dir():
        print(
            "Error: pinout_file/ not found at project root.",
            file=sys.stderr,
        )
        return 1

    if not args.skip_build:
        print("Rebuilding dist/ with PyInstaller...")
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "PolyLibs.spec", "--noconfirm"],
            cwd=project_root,
            check=True,
        )
    elif not src_dist.is_dir():
        print(
            "Error: dist/ not found and --skip-build was used.",
            file=sys.stderr,
        )
        return 1

    label = "all" if args.all else "_".join(
        s.replace("/", "_") for s in args.series
    )
    output_dir = args.output_dir or (project_root / "dist_minimal")
    if args.zip:
        output_dir = project_root / "dist_packages" / f"PolyLibs_{label}"

    if output_dir.exists():
        shutil.rmtree(output_dir)

    print(f"Copying {src_dist} to {output_dir}...")
    shutil.copytree(src_dist, output_dir)

    # Ensure the output package is self-contained: copy runtime data and manifests
    # from the project root (PyInstaller no longer bundles them in dist/)."
    for src_name in ["data", "library"]:
        src = project_root / src_name
        if src.exists():
            shutil.copytree(src, output_dir / src_name, dirs_exist_ok=True)

    # Remove any stale pinout_file/ that PyInstaller may have bundled inside dist/.
    stale_pinout = output_dir / "pinout_file"
    if stale_pinout.exists():
        shutil.rmtree(stale_pinout)

    dst_pinout = output_dir / "pinout_file"
    if args.all:
        print(f"Copying full {src_pinout} to {dst_pinout}...")
        shutil.copytree(src_pinout, dst_pinout)
    else:
        included = {
            tuple(part.strip().strip("/").split("/"))
            for part in ",".join(args.series).split(",")
            if part.strip()
        }
        print(f"Copying selected series {included!r}...")
        dst_pinout.mkdir(parents=True, exist_ok=True)
        for vendor, series in sorted(included):
            src_series = src_pinout / vendor / series
            if not src_series.is_dir():
                print(
                    f"Warning: series not found: {vendor}/{series}",
                    file=sys.stderr,
                )
                continue
            dst_series = dst_pinout / vendor / series
            dst_series.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src_series, dst_series)

    if args.zip:
        zip_path = output_dir.parent / f"PolyLibs_{label}"
        if zip_path.with_suffix(".zip").exists():
            zip_path.with_suffix(".zip").unlink()
        archive = shutil.make_archive(str(zip_path), "zip", str(output_dir))
        shutil.rmtree(output_dir)
        print(f"Packaged: {archive}")
    else:
        print(f"Minimal dist ready: {output_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
