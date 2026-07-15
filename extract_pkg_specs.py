"""Extract package specs from Xilinx PDF text dumps and update pkg_db.json."""

import json
import re
from pathlib import Path


def parse_size(s: str) -> tuple[float, float] | None:
    """Parse strings like '23 x 23' or '42.5 x 42.5' into (x, y)."""
    s = s.strip().replace(',', '')
    m = re.search(r'(\d+\.?\d*)\s*[xX×]\s*(\d+\.?\d*)', s)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def parse_pitch(s: str) -> float | None:
    """Parse pitch from a string fragment."""
    m = re.search(r'(\d+\.?\d+)', s.strip())
    if m:
        return float(m.group(1))
    return None


def add_spec(db: dict, code: str, pitch: float, body: tuple[float, float]):
    """Add a spec to the database, skipping if already present."""
    code = code.lower().strip()
    if not code or code in db:
        return
    # Estimate pad diameter from pitch (common Xilinx NSMD recommendations)
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
        "body_size_x": body[0],
        "body_size_y": body[1],
        "pad_diameter_mm": pad,
        "mask_opening_mm": round(pad + 0.05, 3),
        "paste_diameter_mm": round(max(0.1, pad - 0.05), 3),
    }


def extract_7series(path: Path, db: dict):
    """Extract package specs from ug475 7series text."""
    text = path.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()

    in_table = False
    table_lines = []
    for line in lines:
        if 'Table 1-1: 7 Series FPGAs Package Specifications' in line:
            in_table = True
            continue
        if in_table:
            if 'Table 1-2:' in line or 'Notes:' in line and len(table_lines) > 20:
                break
            table_lines.append(line)

    # The table has rows like:
    # CPGA196                                           BGA  0.5  8x8      100
    # FTB196/FTGB196                                    BGA  1.0  15 x 15  100
    # Some rows have description in the middle column and pitch/size in right columns.
    # Because columns are misaligned due to layout, we try a few patterns.

    for line in table_lines:
        stripped = line.strip()
        if not stripped or 'Package Specifications' in stripped or 'Pitch' in stripped:
            continue

        # Look for package code part at start, then pitch, then size
        # Pattern: CODE(S) [description] BGA  PITCH  SIZE [MAX_IO]
        # Use regex to find pitch and size anywhere in line
        size = parse_size(stripped)
        pitch = parse_pitch(stripped)

        if not size or not pitch:
            continue

        # Extract leading package codes before any description words
        # The codes are at the start, may contain slashes
        front = stripped.split('BGA')[0] if 'BGA' in stripped else stripped
        # Remove known description words from front
        front = re.split(r'\b(Wire-bond|chip-scale|Flip-chip|Ruggedized|fine-pitch|lidless|SSI|overhang)\b', front)[0]
        # Extract slash-separated package codes
        codes = re.findall(r'[A-Za-z]+\d+', front)

        for code in codes:
            add_spec(db, code, pitch, size)


def extract_ultrascale(path: Path, db: dict):
    """Extract package specs from ug575 ultrascale text."""
    text = path.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()

    in_table = False
    table_lines = []
    for line in lines:
        if 'Package Specifications' in line and 'Table' in line:
            in_table = True
            continue
        if in_table:
            if ('Notes:' in line and len(table_lines) > 20) or 'Figure' in line:
                break
            table_lines.append(line)

    for line in table_lines:
        stripped = line.strip()
        if not stripped or 'Package Specifications' in stripped or 'Pitch' in stripped:
            continue
        size = parse_size(stripped)
        pitch = parse_pitch(stripped)
        if not size or not pitch:
            continue
        front = stripped.split('BGA')[0] if 'BGA' in stripped else stripped
        front = re.split(r'\b(Wire-bond|Flip-Chip|Fine-Pitch|Lidless|Ruggedized)\b', front)[0]
        codes = re.findall(r'[A-Za-z]+\d+', front)
        for code in codes:
            add_spec(db, code, pitch, size)


def extract_zynq_us_plus(path: Path, db: dict):
    """Extract package specs from ug1075 zynq ultrascale+ text."""
    text = path.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()

    in_table = False
    table_lines = []
    for line in lines:
        if 'Package Specifications' in line and 'Table' in line:
            in_table = True
            continue
        if in_table:
            if ('Notes:' in line and len(table_lines) > 20) or 'Figure' in line:
                break
            table_lines.append(line)

    for line in table_lines:
        stripped = line.strip()
        if not stripped or 'Package Specifications' in stripped or 'Pitch' in stripped:
            continue
        size = parse_size(stripped)
        pitch = parse_pitch(stripped)
        if not size or not pitch:
            continue
        front = stripped.split('BGA')[0] if 'BGA' in stripped else stripped
        front = re.split(r'\b(Wire-bond|Flip-Chip|Fine-Pitch|Lidless|Ruggedized)\b', front)[0]
        codes = re.findall(r'[A-Za-z]+\d+', front)
        for code in codes:
            add_spec(db, code, pitch, size)


def load_existing(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {}


def save_db(db: dict, path: Path):
    path.write_text(json.dumps(db, indent=2, sort_keys=True), encoding='utf-8')


def main():
    root = Path(__file__).parent
    db = load_existing(root / 'data' / 'pkg_db.json')

    print(f'Existing entries: {len(db)}')

    extract_7series(root / '7series.txt', db)
    print(f'After 7series: {len(db)}')

    extract_ultrascale(root / 'ultrascale.txt', db)
    print(f'After ultrascale: {len(db)}')

    extract_zynq_us_plus(root / 'zynq_us_plus.txt', db)
    print(f'After zynq_us_plus: {len(db)}')

    save_db(db, root / 'data' / 'pkg_db.json')
    print('Saved.')


if __name__ == '__main__':
    main()
