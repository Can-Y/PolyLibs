"""Extend pkg_db.json with generated defaults for package codes found in data.

Existing exact entries are never overwritten; this script only adds missing
codes inferred from the package family prefix and ball count.
"""

import json
import math
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "pkg_db.json"

# Base pitch/pad hints for package families (longest match wins).
PREFIX_HINTS: list[tuple[str, float, float]] = [
    # 0.50 mm pitch wire-bond CSP / tiny BGA
    ("cp", 0.50, 0.25),
    ("pu", 0.50, 0.25),
    ("pfc", 0.50, 0.25),
    ("pub", 0.50, 0.25),
    ("tcpg", 0.50, 0.25),
    ("tcps", 0.50, 0.25),
    # 0.80 mm pitch CSP / fine-pitch BGA
    ("csg", 0.80, 0.40),
    ("cs", 0.80, 0.40),
    ("ft", 0.80, 0.40),
    ("sb", 0.80, 0.40),
    ("psb", 0.80, 0.40),
    ("tcsg", 0.80, 0.40),
    ("cgsb", 0.80, 0.40),
    ("sfv", 0.80, 0.40),
    # 1.00 mm pitch FPBGA / FFBGA / TFBGA families
    ("fsv", 1.00, 0.45),  # large FSV* packages may use 0.92mm for 3824
    ("f", 1.00, 0.45),
    ("t", 1.00, 0.45),
    ("pff", 1.00, 0.45),
    ("pfh", 1.00, 0.45),
    ("pfi", 1.00, 0.45),
    ("pfl", 1.00, 0.45),
    ("pfs", 1.00, 0.45),
    ("cgff", 1.00, 0.45),
    ("cgsf", 1.00, 0.45),
    ("cgub", 1.00, 0.45),
    ("dr", 1.00, 0.45),
    ("eg", 1.00, 0.45),
    ("ev", 1.00, 0.45),
    # Fallbacks
    ("s", 0.80, 0.40),
    ("c", 0.80, 0.40),
    ("p", 0.80, 0.40),
]


def _learn_hints(known_codes: set[str]) -> list[tuple[str, float, float]]:
    """Augment base hints with alphabetic prefixes learned from known codes."""
    base = {prefix: (pitch, pad) for prefix, pitch, pad in PREFIX_HINTS}
    for code in known_codes:
        m = re.match(r"([a-z]+)", code)
        if not m:
            continue
        prefix = m.group(1)
        if prefix not in base:
            # Infer pitch/pad from the closest shorter prefix hint.
            for plen in range(len(prefix), 0, -1):
                sub = prefix[:plen]
                if sub in base:
                    base[prefix] = base[sub]
                    break
            else:
                base[prefix] = (1.00, 0.45)
    # Sort by length descending so longest prefixes match first.
    return [
        (prefix, pitch, pad)
        for prefix, (pitch, pad) in sorted(
            base.items(), key=lambda x: len(x[0]), reverse=True
        )
    ]


def _prefix_hint(pkg: str, hints: list[tuple[str, float, float]]) -> tuple[float, float]:
    for prefix, pitch, pad in hints:
        if pkg.startswith(prefix):
            return pitch, pad
    return 1.00, 0.45


def _body_size(balls: int, pitch: float) -> float:
    side = math.ceil(math.sqrt(balls))
    if pitch <= 0.5:
        margin = 2.5
    elif pitch <= 0.8:
        margin = 1.0
    else:
        margin = 3.0 if side <= 18 else 1.5 if side <= 30 else 1.0
    return round(side * pitch + margin, 1)


def _infer_spec(pkg: str, hints: list[tuple[str, float, float]]) -> dict:
    m = re.search(r"(\d+)$", pkg)
    balls = int(m.group(1)) if m else 0
    pitch, pad = _prefix_hint(pkg, hints)
    if pkg.startswith("fs") and balls >= 3000:
        pitch = 0.92
    body = _body_size(balls, pitch)
    mask = round(pad + 0.05, 3)
    paste = round(max(0.1, pad - 0.05), 3)
    return {
        "body_size_x": body,
        "body_size_y": body,
        "mask_opening_mm": mask,
        "pad_diameter_mm": pad,
        "paste_diameter_mm": paste,
        "pitch_mm": pitch,
    }


def _extract_package_code(stem: str, known_codes: set[str]) -> str | None:
    """Extract package code from a CSV stem."""
    lower = stem.lower()
    if lower.endswith("pkg"):
        lower = lower[:-3]

    # First try exact known-code suffix matches.
    matches = [(code, lower.rfind(code)) for code in known_codes if lower.endswith(code)]
    valid = [(code, idx) for code, idx in matches if idx > 0]
    if valid:

        def _score(item: tuple[str, int]) -> tuple[int, int, int]:
            code, idx = item
            device = lower[:idx]
            ends_letter = 1 if device and device[-1].isalpha() else 0
            return ends_letter, len(code), idx

        return max(valid, key=_score)[0]

    # Fallback: pick the most suffix-like candidate with a package-like prefix.
    hints = _learn_hints(known_codes)
    candidates = []
    for m in re.finditer(r"[a-z]+\d+", lower):
        pkg = m.group(0)
        idx = m.start()
        if idx == 0:
            continue
        hint_len = 0
        for prefix, _, _ in hints:
            if pkg.startswith(prefix) and len(prefix) > hint_len:
                hint_len = len(prefix)
        if hint_len:
            candidates.append((pkg, idx, hint_len))

    if not candidates:
        return None

    # Prefer candidates that start later (more suffix-like), then stronger hint.
    candidates.sort(key=lambda x: (x[1], x[2], len(x[0])), reverse=True)
    return candidates[0][0]


def _collect_package_codes(known_codes: set[str]) -> set[str]:
    root = PROJECT_ROOT.parent
    codes: set[str] = set()
    data_dirs = [
        root / "pinout_file" / "xilinx" / "7series" / "a7all",
        root / "pinout_file" / "xilinx" / "7series" / "k7all",
        root / "pinout_file" / "xilinx" / "7series" / "v7all",
        root / "pinout_file" / "xilinx" / "ultrascale" / "usaall",
        root / "pinout_file" / "xilinx" / "ultrascale_plus" / "usaall",
        root / "pinout_file" / "xilinx" / "zynq_us_plus" / "zupall" / "zupall",
        root / "pinout_file" / "xilinx" / "zynq7000" / "z7all" / "7zSeriesALL",
        root / "pinout_file" / "xilinx" / "versal" / "versal-all" / "versal-all",
    ]
    for d in data_dirs:
        if not d.is_dir():
            continue
        for csv_file in d.rglob("*.csv"):
            code = _extract_package_code(csv_file.stem, known_codes)
            if code:
                codes.add(code)
    return codes


def main() -> None:
    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    known = set(db.keys())
    codes = _collect_package_codes(known)
    hints = _learn_hints(known)
    added = 0
    for pkg in sorted(codes):
        if pkg in db:
            continue
        db[pkg] = _infer_spec(pkg, hints)
        added += 1
    DB_PATH.write_text(json.dumps(db, indent=2) + "\n", encoding="utf-8")
    print(f"Added {added} package code(s); total {len(db)}")


if __name__ == "__main__":
    main()
