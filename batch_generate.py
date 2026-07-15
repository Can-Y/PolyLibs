#!/usr/bin/env python3
"""Batch-generate KiCad libraries for every series/model/package combination."""

import sys
import traceback
from pathlib import Path

from PolyLibs.polylibs.gui import build_output, scan_devices_by_series, _series_dirs

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output" / "batch_kicad_all"
DATA_DIRS = list(_series_dirs(ROOT).values())
flat_data_dirs = [d for sub in DATA_DIRS for d in sub]


def main() -> int:
    devices = scan_devices_by_series(ROOT)
    total = sum(len(p) for m in devices.values() for p in m.values())
    print(f"Total combinations: {total}")

    errors: list[tuple[str, str]] = []
    generated = 0

    for series, models in devices.items():
        for model, packages in models.items():
            for package in packages:
                device = (model + package).lower()
                data_dirs = _series_dirs(ROOT).get(series, flat_data_dirs)
                try:
                    build_output(
                        device_name=device,
                        data_dirs=data_dirs,
                        output_dir=OUTPUT,
                        selected={"KiCad": True},
                        generate_symbol=True,
                        generate_footprint=True,
                        overwrite=True,
                    )
                    generated += 1
                except Exception as e:
                    msg = f"{series}/{device}: {e}"
                    errors.append((device, msg))
                    print(f"ERROR {msg}")
                    traceback.print_exc()

    print(f"\nGenerated: {generated}/{total}")
    if errors:
        print(f"Errors: {len(errors)}")
        for _, msg in errors:
            print(f"  {msg}")
        return 1
    print("All generated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
