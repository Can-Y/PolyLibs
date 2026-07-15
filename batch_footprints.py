#!/usr/bin/env python3
"""Generate one KiCad footprint (.kicad_mod) per (series, package) combination."""

import sys
import traceback
from pathlib import Path

from PolyLibs.polylibs.gui import build_output, scan_devices_by_series, _series_dirs

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output" / "batch_footprints_by_package"


def main() -> int:
    devices = scan_devices_by_series(ROOT)
    series_dirs = _series_dirs(ROOT)

    # Map (series, package_upper) -> first device name + data_dirs
    targets: dict[tuple[str, str], tuple[str, list[Path]]] = {}
    for series, models in devices.items():
        for model, packages in models.items():
            for package in packages:
                key = (series, package)
                if key not in targets:
                    device = (model + package).lower()
                    targets[key] = (device, series_dirs.get(series, []))

    print(f"Unique series/package combinations: {len(targets)}")

    errors: list[str] = []
    generated = 0
    for (series, package), (device, data_dirs) in sorted(targets.items()):
        try:
            build_output(
                device_name=device,
                data_dirs=data_dirs,
                output_dir=OUTPUT,
                selected={"KiCad": True},
                generate_symbol=False,
                generate_footprint=True,
                overwrite=True,
            )
            generated += 1
        except Exception as e:
            msg = f"{series}/{package} ({device}): {e}"
            errors.append(msg)
            print(f"ERROR {msg}")
            traceback.print_exc()

    print(f"\nGenerated: {generated}/{len(targets)}")
    if errors:
        print(f"Errors: {len(errors)}")
        return 1
    print("All footprints generated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
