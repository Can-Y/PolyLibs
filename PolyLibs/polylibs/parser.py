"""CSV discovery, format detection, and parsing."""

import csv
import json
import logging
import re
from pathlib import Path

from .models import Family, PinRecord, DevicePinout
from .manifest import Series


logger = logging.getLogger(__name__)


# BGA column letters skip characters that can be confused with digits.
_BGA_ALPHABET = [c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if c not in {'I', 'O', 'Q', 'S', 'X', 'Z'}]


def _bga_alpha_to_index(alpha: str) -> int:
    """Convert BGA row letters to a 0-based index.

    Standard BGA ball labels omit I, O, Q, S, X and Z to avoid confusion with
    digits.  Row labels therefore count like A..Y (20 letters), then AA, AB,
    etc.  We treat the label as a base-20 number where A=1, B=2, ..., Y=20 and
    subtract one to obtain a zero-based index.
    """
    alpha = alpha.upper()
    result = 0
    for ch in alpha:
        if ch not in _BGA_ALPHABET:
            raise ValueError(f"Invalid BGA row letter '{ch}' in '{alpha}'")
        result = result * len(_BGA_ALPHABET) + (_BGA_ALPHABET.index(ch) + 1)
    return result - 1


def ball_id_to_indices(ball_id: str) -> tuple[int, int]:
    """Convert BGA ball ID like 'AA16' to (col_index, row_index).

    Xilinx convention: the numeric part is the column (X direction) and the
    alphabetic part is the row (Y direction), so e.g. a 29-column x 18-row
    package is wider than it is tall.
    """
    m = re.match(r'^([A-Za-z]+)(\d+)$', ball_id.strip())
    if not m:
        raise ValueError(f"Invalid BGA ball ID: {ball_id!r}")
    alpha, numeric = m.groups()
    col = int(numeric) - 1
    row = _bga_alpha_to_index(alpha)
    return col, row


def detect_format(lines: list[str]) -> tuple[Family, list[str], int]:
    """Detect FPGA family and column headers."""
    cleaned = [line.lstrip('\ufeff') for line in lines]
    for i, line in enumerate(cleaned):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if 'Pin' in stripped and 'Pin Name' in stripped:
            reader = csv.reader([stripped])
            cols = [c.strip() for c in next(reader)]
            num_cols = len(cols)
            if num_cols == 8 or 'VCCAUX Group' in cols:
                return Family.SERIES_7, cols, i
            elif num_cols == 7 or 'No-Connect' in cols:
                return Family.ULTRASCALE, cols, i
            else:
                return Family.ULTRASCALE_PLUS, cols, i
    raise ValueError("Could not detect header line in CSV file")


def parse_csv(filepath: Path) -> DevicePinout:
    """Parse a Xilinx package pinout CSV file."""
    filename = filepath.stem
    if filename.lower().endswith('pkg'):
        full_device = filename[:-3]
    else:
        full_device = filename

    raw = filepath.read_text(encoding='utf-8-sig', errors='replace')
    # Some AMD Versal CSVs contain a stray standalone '"' line that swallows the
    # entire pin table into one multi-line quoted field.  Strip those lines.
    lines = [
        line for line in raw.splitlines()
        if line.strip() != '"'
    ]
    family, columns, header_idx = detect_format(lines)

    col_map = {
        col_name.lower().replace(' ', '_').replace('-', '_'): idx
        for idx, col_name in enumerate(columns)
    }

    pins: list[PinRecord] = []
    total_pins_declared = 0

    # Use the pre-processed lines (stray quotes already removed) for parsing.
    reader = csv.reader(lines)
    for row_idx, row in enumerate(reader):
            if row_idx <= header_idx:
                continue
            if not row or all(c.strip() == '' for c in row):
                continue
            first = row[0].strip()
            if not first or first.startswith('#'):
                continue
            if first.lower().startswith('total number of pins'):
                try:
                    total_pins_declared = int(row[1].strip()) if len(row) > 1 else 0
                except (ValueError, IndexError):
                    pass
                continue

            ball_id = first
            pin_name = row[1].strip() if len(row) > 1 else ''
            try:
                col_idx, row_idx_ball = ball_id_to_indices(ball_id)
            except ValueError:
                col_idx, row_idx_ball = -1, -1

            def get_col(name: str) -> str:
                key = name.lower().replace(' ', '_').replace('-', '_')
                idx = col_map.get(key, -1)
                if 0 <= idx < len(row):
                    return row[idx].strip()
                return 'NA'

            pins.append(PinRecord(
                ball_id=ball_id,
                pin_name=pin_name,
                bank=get_col('bank'),
                io_type=get_col('i/o_type') or get_col('io_type'),
                family=family,
                byte_group=get_col('memory_byte_group'),
                slr=get_col('super_logic_region'),
                vccaux_group=get_col('vccaux_group') if family == Family.SERIES_7 else 'NA',
                no_connect=get_col('no-connect') if family in (Family.SERIES_7, Family.ULTRASCALE) else 'NA',
                col_index=col_idx,
                row_index=row_idx_ball,
            ))

    if total_pins_declared and total_pins_declared != len(pins):
        logger.warning(
            "declared %d pins but parsed %d", total_pins_declared, len(pins)
        )

    device_name, package_code = _split_device_package(full_device)
    return DevicePinout(
        device_name=device_name,
        package_code=package_code,
        full_name=full_device,
        family=family,
        total_pins=len(pins),
        pins=pins,
    )


def _load_pkg_codes() -> set[str]:
    """Load all known package codes from the package database.

    The database lives at ``<project-root>/data/pkg_db.json``.  Search upward
    from the package directory so the same code works both in the repo layout
    (``PolyLibs/polylibs/...``) and in a standalone distribution
    (``PolyLibs-opensource/polylibs/...``).
    """
    start = Path(__file__).parent.parent
    for candidate in (start.parent, start):
        db_path = candidate / "data" / "pkg_db.json"
        if db_path.exists():
            try:
                db = json.loads(db_path.read_text(encoding="utf-8"))
                # Single-character keys are usually data-entry noise and cause
                # incorrect splits (e.g. 'a' matching inside 'csga324').
                return {k for k in db.keys() if len(k) >= 2}
            except (json.JSONDecodeError, OSError):
                return set()
    return set()


_PKG_CODES: set[str] | None = None


def _pkg_codes() -> set[str]:
    global _PKG_CODES
    if _PKG_CODES is None:
        _PKG_CODES = _load_pkg_codes()
    return _PKG_CODES


def _split_device_package(full_name: str) -> tuple[str, str]:
    """Split 'xc7a100tfgg484' into ('xc7a100t', 'fgg484').

    Uses the package database for known package-code suffixes.  When a name is
    ambiguous (e.g. ``xc7a100tfgg484`` matches both ``tfgg484`` and ``fgg484``)
    we prefer the split whose device prefix ends with a recognised speed-grade
    suffix letter, then fall back to a conservative regex.
    """
    full_lower = full_name.lower()
    known = _pkg_codes()

    # Find every known package code that appears as a substring and leaves a
    # non-empty device prefix.
    matches = [(code, full_lower.rfind(code)) for code in known if code in full_lower]
    valid = [(code, idx) for code, idx in matches if idx > 0]

    if len(valid) > 1:
        # Disambiguate by preferring a device prefix that ends with a common
        # speed-grade / device suffix letter.  This resolves cases such as
        # ``xc7a100tfgg484`` (prefer ``xc7a100t`` + ``fgg484`` over
        # ``xc7a100`` + ``tfgg484``).
        def _score(item: tuple[str, int]) -> tuple[int, int, int]:
            code, idx = item
            device = full_name[:idx]
            ends_letter = 1 if device and device[-1].isalpha() else 0
            return ends_letter, len(code), idx

        code, idx = max(valid, key=_score)
        return full_name[:idx], full_name[idx:]

    if valid:
        code, idx = valid[0]
        return full_name[:idx], full_name[idx:]

    # Fallback: split before the last alphabetic run that is followed by digits.
    m = re.search(r'([a-z]+\d+)$', full_lower)
    if m:
        idx = m.start()
        if idx > 0:
            return full_name[:idx], full_name[idx:]

    return full_name, ''


def find_device_csv(device_name: str, data_dirs: list[Path]) -> Path:
    """Find the CSV file for a device model."""
    name_lower = device_name.lower().strip()
    if name_lower.endswith('pkg'):
        name_lower = name_lower[:-3]

    candidates: list[Path] = []
    for data_dir in data_dirs:
        if not data_dir.is_dir():
            continue
        for csv_file in data_dir.glob('**/*.csv'):
            stem = csv_file.stem.lower()
            if stem.endswith('pkg'):
                stem = stem[:-3]
            if stem == name_lower or stem.startswith(name_lower):
                candidates.append(csv_file)

    if not candidates:
        raise FileNotFoundError(f"No pinout CSV found for device '{device_name}'")

    exact = [c for c in candidates if c.stem.lower().replace('pkg', '') == name_lower]
    if exact:
        return exact[0]
    if len(candidates) > 1:
        logger.warning(
            "multiple matches for '%s', using %s", device_name, candidates[0].stem
        )
    return candidates[0]


def parse_csv_with_mapping(csv_path: Path, series: Series) -> DevicePinout:
    """Parse a vendor-neutral pinout CSV using the series column map."""
    filename = csv_path.stem
    if filename.lower().endswith("pkg"):
        full_device = filename[:-3]
    else:
        full_device = filename

    raw = csv_path.read_text(encoding="utf-8-sig", errors="replace")
    lines = [line for line in raw.splitlines() if line.strip() != '"']
    reader = csv.reader(lines)
    # Xilinx CSVs carry a long '#' comment preamble before the real header
    # row; skip comment/blank lines so the first real row becomes the header.
    headers: list[str] = []
    for row in reader:
        if not row or all(c.strip() == "" for c in row):
            continue
        if row[0].strip().startswith("#"):
            continue
        headers = [h.strip() for h in row]
        break
    header_index = {h: i for i, h in enumerate(headers)}

    col_idx = {
        key: header_index.get(raw_name, -1)
        for key, raw_name in series.column_map.items()
    }

    def get(key: str, row: list[str]) -> str:
        idx = col_idx.get(key, -1)
        if 0 <= idx < len(row):
            return row[idx].strip()
        return "NA"

    pins: list[PinRecord] = []
    for row in reader:
        if not row or all(c.strip() == "" for c in row):
            continue
        first = row[0].strip()
        if not first or first.startswith("#"):
            continue
        if first.lower().startswith("total number of pins"):
            # Xilinx CSV footer row, not a pin.
            continue

        ball_id = get("pin", row) or first
        try:
            col_idx_ball, row_idx_ball = ball_id_to_indices(ball_id)
        except ValueError:
            col_idx_ball, row_idx_ball = -1, -1

        pins.append(
            PinRecord(
                ball_id=ball_id,
                pin_name=get("pin_name", row),
                bank=get("bank", row),
                io_type=get("io_type", row),
                family=series.family,
                byte_group=get("byte_group", row),
                slr=get("slr", row),
                vccaux_group=get("vccaux_group", row),
                no_connect=get("no_connect", row),
                col_index=col_idx_ball,
                row_index=row_idx_ball,
            )
        )

    device_name, package_code = _split_device_package(full_device)
    return DevicePinout(
        device_name=device_name,
        package_code=package_code,
        full_name=full_device,
        family=series.family,
        total_pins=len(pins),
        pins=pins,
    )
