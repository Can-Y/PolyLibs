"""Update pkg_db.json from PDF-extracted specs, alias mappings, and heuristics."""

import json
import re
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(db: dict, path: Path):
    path.write_text(json.dumps(db, indent=2, sort_keys=True), encoding='utf-8')


def add_spec(db: dict, code: str, pitch: float, body_x: float, body_y: float):
    code = code.lower().strip()
    if not code:
        return
    if pitch <= 0.5:
        pad = 0.25
    elif pitch <= 0.65:
        pad = 0.30
    elif pitch <= 0.8:
        pad = 0.40
    elif pitch <= 1.0:
        pad = 0.45
    else:
        pad = 0.50
    db[code] = {
        "pitch_mm": pitch,
        "body_size_x": body_x,
        "body_size_y": body_y,
        "pad_diameter_mm": pad,
        "mask_opening_mm": round(pad + 0.05, 3),
        "paste_diameter_mm": round(max(0.1, pad - 0.05), 3),
    }


def add_alias(db: dict, alias: str, base: str):
    """Add alias pointing to base spec if base exists."""
    alias = alias.lower().strip()
    base = base.lower().strip()
    if alias in db or base not in db:
        return
    spec = db[base]
    add_spec(db, alias, spec["pitch_mm"], spec["body_size_x"], spec["body_size_y"])


def collect_codes(data_dirs: list[str]) -> set[str]:
    codes = set()
    for d in data_dirs:
        p = Path(d)
        if not p.exists():
            continue
        for f in p.glob('*.csv'):
            stem = f.stem.lower()
            if stem.endswith('pkg'):
                stem = stem[:-3]
            # Some filenames have two packages joined with _x
            parts = re.split(r'[_x]', stem)
            for part in parts:
                m = re.search(r'([a-z]+\d+)$', part)
                if m:
                    codes.add(m.group(1))
    return codes


GRADE_PREFIXES = ['p', 't', 's', 'i', 'a', 'q', 'x', 'e']


def alias_mappings(target_codes: set[str], db: dict) -> list[tuple[str, str]]:
    """Return per-code alias mappings for temperature/grade variants.

    For each target code that is not already in the database, try stripping a
    known grade prefix.  If the resulting base code exists in the database,
    the variant shares the same package geometry.
    """
    mappings: list[tuple[str, str]] = []
    for code in sorted(target_codes):
        if code in db:
            continue
        for prefix in GRADE_PREFIXES:
            if code.startswith(prefix) and len(code) > len(prefix):
                base = code[len(prefix):]
                if base in db:
                    mappings.append((code, base))
                    break
    return mappings


def heuristic_for_prefix(code: str) -> tuple[float, float, float] | None:
    """Return (pitch, body, pad) based on known package family conventions."""
    c = code.lower()

    # Fine-pitch / chip-scale BGA
    if any(c.startswith(p) for p in ['cpg', 'tcpg', 'csga', 'tcsga', 'cna']):
        if '236' in c or '238' in c:
            return 0.5, 10.0, 0.25
        if '225' in c or '196' in c:
            return 0.5, 10.0, 0.25
        if '324' in c or '325' in c:
            return 0.8, 15.0, 0.40
        return 0.8, 15.0, 0.40

    if any(c.startswith(p) for p in ['ftg', 'tftg', 'ftgb', 'tftgb']):
        if '196' in c:
            return 1.0, 15.0, 0.40
        return 1.0, 17.0, 0.45

    # CLG/SCLG Zynq-7000 packages (heuristic from common sizes)
    if any(c.startswith(p) for p in ['clg', 'sclg']):
        if '225' in c:
            return 0.8, 13.0, 0.40
        if '400' in c:
            return 0.8, 17.0, 0.40
        if '484' in c:
            return 1.0, 23.0, 0.45
        if '485' in c:
            return 0.8, 19.0, 0.40

    # Small wire-bond BGA
    if any(c.startswith(p) for p in ['fgg', 'tfgg', 'fga', 'fgga']):
        if '484' in c:
            return 1.0, 23.0, 0.45
        if '676' in c:
            return 1.0, 27.0, 0.45
        return 1.0, 23.0, 0.45

    if any(c.startswith(p) for p in ['ffg', 'tffg', 'ffv', 'tffv', 'ffr']):
        if '676' in c:
            return 1.0, 27.0, 0.45
        if '900' in c or '901' in c:
            return 1.0, 31.0, 0.45
        if '1156' in c or '1157' in c or '1158' in c:
            return 1.0, 35.0, 0.45
        if '1761' in c:
            return 1.0, 42.5, 0.50
        if any(n in c for n in ['1926', '1927', '1928', '1930', '1925']):
            return 1.0, 45.0, 0.50
        return 1.0, 35.0, 0.45

    if any(c.startswith(p) for p in ['flg', 'tflg', 'flv', 'flva', 'flvb', 'flvc', 'flvd', 'flve', 'flvf', 'flvj', 'flvk', 'pflv']):
        if '1517' in c:
            return 1.0, 40.0, 0.45
        if '1760' in c:
            return 1.0, 42.5, 0.50
        if any(n in c for n in ['1924', '1925', '1926', '1928', '1930', '1931', '1932']):
            return 1.0, 45.0, 0.50
        if any(n in c for n in ['2104', '2105']):
            return 1.0, 47.5, 0.50
        if '2577' in c:
            return 1.0, 52.5, 0.50
        if any(n in c for n in ['2377', '2892']):
            return 1.0, 55.0, 0.50
        return 1.0, 45.0, 0.50

    if any(c.startswith(p) for p in ['fhg', 'fhga', 'fhgb', 'fhgc', 'fhge', 'fhgj', 'fhgv', 'thcg', 'pfhg']):
        return 1.0, 45.0, 0.50

    if any(c.startswith(p) for p in ['fbg', 'tfbg', 'fbv', 'tfbv', 'rb', 'rs', 'sb', 'sbg', 'sbv', 'sbra', 'sbrj', 'sbvj', 'pfbv', 'psbv']):
        if '484' in c:
            return 1.0, 23.0, 0.45
        if '676' in c:
            return 1.0, 27.0, 0.45
        if '900' in c:
            return 1.0, 31.0, 0.45
        if '1155' in c:
            return 1.0, 35.0, 0.45
        return 1.0, 23.0, 0.45

    if any(c.startswith(p) for p in ['fbva', 'ffva', 'ffvb', 'ffvc', 'ffvd', 'ffve', 'ffvf', 'ffvj', 'ffvk', 'pffv', 'pffr']):
        if '676' in c:
            return 1.0, 27.0, 0.45
        if '900' in c:
            return 1.0, 31.0, 0.45
        if '1156' in c:
            return 1.0, 35.0, 0.45
        if '1517' in c:
            return 1.0, 40.0, 0.45
        if '1760' in c:
            return 1.0, 42.5, 0.50
        if '2104' in c:
            return 1.0, 47.5, 0.50
        return 1.0, 35.0, 0.45

    if any(c.startswith(p) for p in ['fsv', 'fsvb', 'fsvc', 'fsvd', 'fsve', 'fsvh', 'fsvj', 'fsvk', 'pfsv']):
        if '784' in c:
            return 1.0, 29.0, 0.45
        if any(n in c for n in ['1924', '1925', '1926', '1928', '1930', '1931', '1932']):
            return 1.0, 45.0, 0.50
        if '2104' in c:
            return 1.0, 47.5, 0.50
        if '2892' in c:
            return 1.0, 55.0, 0.50
        if '3824' in c:
            return 0.92, 60.0, 0.45
        return 1.0, 35.0, 0.45

    # Versal ACAP packages
    if any(c.startswith(p) for p in ['sfva', 'ssva', 'ssra', 'ssvl']):
        if '784' in c:
            return 1.0, 29.0, 0.45
        if '1089' in c:
            return 1.0, 35.0, 0.45
        if any(n in c for n in ['1221', '1365']):
            return 1.0, 37.5, 0.45
        if any(n in c for n in ['1440', '1441']):
            return 1.0, 40.0, 0.45
        if any(n in c for n in ['1760', '1761']):
            return 1.0, 42.5, 0.50
        if '2112' in c:
            return 1.0, 47.5, 0.50
        if '2397' in c:
            return 1.0, 50.0, 0.50
        return 1.0, 40.0, 0.45

    if any(c.startswith(p) for p in ['vsva', 'vsra', 'vsrb', 'vsrc', 'vsrd', 'vsvc', 'vsvd', 'vsvh', 'vsvi', 'vira', 'viva', 'vfv', 'vfvc', 'vfvf']):
        if any(n in c for n in ['1596', '1597']):
            return 1.0, 40.0, 0.45
        if any(n in c for n in ['1760', '1761', '1762', '1763']):
            return 1.0, 42.5, 0.50
        if any(n in c for n in ['2021', '2022']):
            return 1.0, 45.0, 0.50
        if any(n in c for n in ['2197', '2198']):
            return 1.0, 47.5, 0.50
        if any(n in c for n in ['2785', '2786']):
            return 1.0, 52.5, 0.50
        if any(n in c for n in ['3340', '3341', '3342']):
            return 1.0, 55.0, 0.50
        if any(n in c for n in ['3697', '3698']):
            return 1.0, 60.0, 0.55
        if any(n in c for n in ['4072', '4073']):
            return 1.0, 62.5, 0.55
        if any(n in c for n in ['4737', '4738']):
            return 1.0, 65.0, 0.55
        if any(n in c for n in ['5601', '5602']):
            return 1.0, 70.0, 0.55
        if any(n in c for n in ['6865', '6866']):
            return 1.0, 77.5, 0.60
        return 1.0, 55.0, 0.50

    # Versal Premium / HBM packages
    if any(c.startswith(p) for p in ['nbv', 'nfv', 'nrg', 'nsv', 'nsrg']):
        if any(n in c for n in ['1024', '1025']):
            return 1.0, 40.0, 0.45
        if any(n in c for n in ['1369', '1370']):
            return 1.0, 47.5, 0.50
        return 1.0, 47.5, 0.50

    return None


def ball_count_heuristic(code: str) -> tuple[float, float, float] | None:
    """Last-resort heuristic based on ball count suffix."""
    m = re.search(r'(\d+)$', code)
    if not m:
        return None
    n = int(m.group(1))
    if n <= 196:
        return 0.5, 10.0, 0.25
    if n <= 238:
        return 0.5, 10.0, 0.25
    if n <= 324:
        return 0.8, 13.0, 0.40
    if n <= 400:
        return 0.8, 17.0, 0.40
    if n <= 484:
        return 1.0, 23.0, 0.45
    if n <= 676:
        return 1.0, 27.0, 0.45
    if n <= 900:
        return 1.0, 31.0, 0.45
    if n <= 1156:
        return 1.0, 35.0, 0.45
    if n <= 1517:
        return 1.0, 40.0, 0.45
    if n <= 1760:
        return 1.0, 42.5, 0.50
    if n <= 2104:
        return 1.0, 47.5, 0.50
    if n <= 2892:
        return 1.0, 55.0, 0.50
    return 1.0, 60.0, 0.50


def main():
    root = Path(__file__).parent
    db_path = root / 'data' / 'pkg_db.json'
    db = load_json(db_path)
    print(f'Initial entries: {len(db)}')

    data_dirs = [
        'pinout_file/xilinx/7series/a7all',
        'pinout_file/xilinx/7series/k7all',
        'pinout_file/xilinx/7series/s7all/s7all',
        'pinout_file/xilinx/7series/v7all',
        'pinout_file/xilinx/ultrascale/usaall',
        'pinout_file/xilinx/ultrascale_plus/usaall',
        'pinout_file/xilinx/zynq_us_plus/zupall/zupall',
        'pinout_file/xilinx/zynq7000/z7all/7zSeriesALL',
        'pinout_file/xilinx/versal/versal-all/versal-all',
    ]
    target_codes = collect_codes(data_dirs)
    print(f'Target package codes: {len(target_codes)}')

    # Refresh grade/variant entries so they inherit the latest PDF-extracted
    # base specs instead of stale heuristic values.  Base codes that are not
    # themselves grade-prefixed variants of another known code are kept.
    for code in list(target_codes):
        if code not in db:
            continue
        for prefix in GRADE_PREFIXES:
            if code.startswith(prefix) and len(code) > len(prefix):
                base = code[len(prefix):]
                if base in db:
                    del db[code]
                    break

    # Apply alias mappings
    for alias, base in alias_mappings(target_codes, db):
        add_alias(db, alias, base)
    print(f'After alias mappings: {len(db)}')

    # Manual corrections for packages whose PDF table cell is blank or that
    # are not covered by the five scanned packaging guides.  Values come from
    # the corresponding product selection guides / QML datasheets.
    manual_overrides = {
        'sfva1221': (0.8, 29.0, 29.0),  # AM013 leaves size blank; PSG = 29x29
        'cna1509': (1.0, 40.0, 40.0),   # XQRKU060 CGA, footprint = FFVA1517
        'thcg1155': (1.0, 35.0, 35.0),  # V-7 HT FLG1155 equivalent
    }
    for code, (pitch, bx, by) in manual_overrides.items():
        if code in target_codes:
            add_spec(db, code, pitch, bx, by)

    # Apply prefix heuristics for still-missing codes
    still_missing = [c for c in target_codes if c not in db]
    for code in still_missing:
        result = heuristic_for_prefix(code)
        if result:
            add_spec(db, code, result[0], result[1], result[1])

    print(f'After prefix heuristics: {len(db)}')

    # Last resort: ball-count heuristic
    still_missing = [c for c in target_codes if c not in db]
    for code in still_missing:
        result = ball_count_heuristic(code)
        if result:
            add_spec(db, code, result[0], result[1], result[1])

    print(f'Final entries: {len(db)}')

    final_missing = sorted(c for c in target_codes if c not in db)
    print(f'Still missing: {len(final_missing)}')
    for c in final_missing:
        print(f'  {c}')

    save_json(db, db_path)
    print('Saved pkg_db.json')


if __name__ == '__main__':
    main()
