"""CLI entry point for polylibs."""

import argparse
import json
import sys
from pathlib import Path

from .library import LibraryScanner
from .manifest import load_manifest, validate_manifest


def _cmd_scan(args: argparse.Namespace) -> int:
    tree = LibraryScanner(Path(args.root)).scan()
    for vendor in tree.vendors.values():
        print(f"Vendor: {vendor.name} ({vendor.id})")
        for series in tree.series_for_vendor(vendor.id):
            print(f"  Series: {series.name} ({series.id})")
            for model in tree.models_for_series(series.id):
                print(f"    Model: {model.full_name}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if args.path:
        targets = [Path(args.path)]
    else:
        targets = (
            sorted((root / "library").rglob("manifest.yaml"))
            if (root / "library").exists()
            else []
        )
    errors = 0
    for manifest_path in targets:
        try:
            vendor, series, models = load_manifest(manifest_path)
            validate_manifest(vendor, series, models)
            print(f"OK: {manifest_path}")
        except Exception as e:
            print(f"FAIL: {manifest_path}: {e}")
            errors += 1
    return 1 if errors else 0


def _cmd_add_package(args: argparse.Namespace) -> int:
    root = Path(args.root)
    db_path = root / "data" / "pkg_db.json"
    db = json.loads(db_path.read_text(encoding="utf-8")) if db_path.exists() else {}
    new_entry = json.loads(args.json)
    if not isinstance(new_entry, dict) or len(new_entry) != 1:
        print("Error: JSON must be a single-key object like {\"fgg999\": {...}}")
        return 1
    db.update(new_entry)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Updated {db_path}")
    return 0


def _cmd_gui(args: argparse.Namespace) -> int:
    from .gui import run_gui

    run_gui()
    return 0


def main(argv: list[str] | None = None) -> int:
    root_parser = argparse.ArgumentParser(add_help=False)
    root_parser.add_argument("--root", default=".", help="project root directory")

    parser = argparse.ArgumentParser(prog="polylibs")
    sub = parser.add_subparsers(dest="command")

    lib_p = sub.add_parser("library", help="library management")
    lib_sub = lib_p.add_subparsers(dest="library_command")

    scan_cmd = lib_sub.add_parser("scan", help="scan library tree", parents=[root_parser])
    scan_cmd.set_defaults(func=_cmd_scan)

    validate_cmd = lib_sub.add_parser(
        "validate", help="validate manifests", parents=[root_parser]
    )
    validate_cmd.add_argument("path", nargs="?", help="manifest.yaml path or directory")
    validate_cmd.set_defaults(func=_cmd_validate)

    add_pkg = sub.add_parser(
        "add-package", help="add package spec to pkg_db.json", parents=[root_parser]
    )
    add_pkg.add_argument("json", help="JSON object with single package spec")
    add_pkg.set_defaults(func=_cmd_add_package)

    gui_cmd = sub.add_parser("gui", help="launch the GUI")
    gui_cmd.set_defaults(func=_cmd_gui)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        # Preserve the historical default: launch the GUI when called without args.
        return _cmd_gui(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
