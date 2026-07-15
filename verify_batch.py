#!/usr/bin/env python3
"""Verify batch-generated KiCad libraries: parse check + kicad-cli sample export."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BATCH = ROOT / "output" / "batch_kicad_all"


def list_devices() -> list[Path]:
    return [d for d in BATCH.iterdir() if d.is_dir()]


def quick_check(device_dir: Path) -> tuple[bool, str]:
    """Check .kicad_sym and .kicad_mod are non-empty and look valid."""
    kicad_dir = device_dir / "kicad"
    sym_files = list(kicad_dir.glob("*.kicad_sym"))
    mod_files = list(kicad_dir.glob("*.kicad_mod"))
    if not sym_files:
        return False, "missing .kicad_sym"
    if not mod_files:
        return False, "missing .kicad_mod"
    for f in sym_files + mod_files:
        text = f.read_text(encoding="utf-8")
        if len(text.strip()) < 100:
            return False, f"{f.name} too small"
        if text.count("(") < 5:
            return False, f"{f.name} malformed"
    return True, "ok"


def kicad_cli_sym(sym_file: Path, outdir: Path) -> tuple[bool, str]:
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = ["kicad-cli", "sym", "export", "svg", "-o", str(outdir), str(sym_file)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return r.returncode == 0, (r.stdout + r.stderr)[:200]
    except Exception as e:
        return False, str(e)


def kicad_cli_mod(mod_file: Path, outdir: Path) -> tuple[bool, str]:
    outdir.mkdir(parents=True, exist_ok=True)
    pretty = outdir / f"{mod_file.stem}_verify.pretty"
    pretty.mkdir(exist_ok=True)
    dest = pretty / mod_file.name
    dest.write_text(mod_file.read_text(encoding="utf-8"), encoding="utf-8")
    cmd = ["kicad-cli", "fp", "export", "svg", "-o", str(outdir), str(pretty)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return r.returncode == 0, (r.stdout + r.stderr)[:200]
    except Exception as e:
        return False, str(e)


def pick_sample(devices: list[Path], per_series: int = 3) -> list[Path]:
    """Pick a sample covering each series."""
    by_series: dict[str, list[Path]] = {}
    for d in devices:
        # device dir name like xc7a100tfgg484; find series from parent report.txt or path
        report = d / "report.txt"
        series = "unknown"
        if report.exists():
            for line in report.read_text(encoding="utf-8").splitlines():
                if line.startswith("Family:"):
                    series = line.split(":", 1)[1].strip()
                    break
        by_series.setdefault(series, []).append(d)
    sample: list[Path] = []
    for series, ds in sorted(by_series.items()):
        ds_sorted = sorted(ds)
        step = max(1, len(ds_sorted) // per_series)
        for i in range(per_series):
            idx = min(i * step, len(ds_sorted) - 1)
            sample.append(ds_sorted[idx])
    return sample


def main() -> int:
    devices = list_devices()
    print(f"Devices: {len(devices)}")

    # Quick parse check on all
    quick_errors = 0
    for d in devices:
        ok, msg = quick_check(d)
        if not ok:
            print(f"QUICK FAIL {d.name}: {msg}")
            quick_errors += 1
    print(f"Quick check: {len(devices) - quick_errors}/{len(devices)} ok")

    # kicad-cli sample verification
    sample = pick_sample(devices)
    print(f"kicad-cli sample size: {len(sample)}")
    sym_errors = 0
    mod_errors = 0
    for d in sample:
        kicad_dir = d / "kicad"
        for sym in kicad_dir.glob("*.kicad_sym"):
            ok, msg = kicad_cli_sym(sym, kicad_dir / "verify_svg")
            if not ok:
                print(f"SYM FAIL {d.name}: {msg}")
                sym_errors += 1
        for mod in kicad_dir.glob("*.kicad_mod"):
            ok, msg = kicad_cli_mod(mod, kicad_dir / "verify_svg")
            if not ok:
                print(f"MOD FAIL {d.name}: {msg}")
                mod_errors += 1

    print(f"kicad-cli sym sample: {len(sample) - sym_errors}/{len(sample)} ok")
    print(f"kicad-cli mod sample: {len(sample) - mod_errors}/{len(sample)} ok")

    if quick_errors or sym_errors or mod_errors:
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
