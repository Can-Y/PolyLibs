"""Extract package specs from Xilinx PDF package specification tables.

This script uses pdfplumber to read the package-dimensions tables in the
official Xilinx packaging guides and updates data/pkg_db.json.
Run it from the repo root with the local venv that has pdfplumber installed:

    .venv/Scripts/python extract_all_pkg_specs.py
"""

import json
import re
from pathlib import Path

try:
    import pdfplumber
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "pdfplumber is required. Install it in a venv, e.g.:\n"
        "  python -m venv .venv\n"
        "  .venv/Scripts/python -m pip install pdfplumber"
    ) from exc


PDF_FILES = {
    # family: (pdf filename, 0-based pages that contain the package-spec table)
    "7series": ("ug475_7Series_Pkg_Pinout.pdf", [9, 10]),
    "ultrascale": ("ug575-ultrascale-pkg-pinout.pdf", [11, 12, 13]),
    "zynq_us_plus": ("ug1075-zynq-ultrascale-pkg-pinout.pdf", [8, 9]),
    "zynq7000": ("ug865-Zynq-7000-Pkg-Pinout.pdf", [8]),
    "versal": ("am013-versal-pkg-pinout.pdf", [13, 14]),
}


def normalize_size(s: str) -> str:
    s = s or ""
    # Replace the odd multiplication glyphs produced by some PDF encodings.
    for ch in "\u00d7\u2715\u2716\u2a09\u2a2f\uff58":
        s = s.replace(ch, " x ")
    s = s.replace("X", "x").replace("M-W", "x").replace(",", "")
    return s


def parse_size(s: str) -> tuple[float, float] | None:
    s = normalize_size(s)
    m = re.search(r"(\d+\.?\d*)\s*x\s*(\d+\.?\d*)", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def parse_pitch(s: str) -> float | None:
    if not s:
        return None
    m = re.search(r"(\d+\.?\d*)", str(s))
    if m:
        val = float(m.group(1))
        # Sanity-check: valid pitches for these guides are 0.5..1.0 mm.
        if 0.4 <= val <= 1.1:
            return val
    return None


def split_package_codes(code_cell: str) -> list[str]:
    """Split a package-code cell into individual codes.

    Handles entries such as:
        CL/CLG225, FF1156/FFG1156/FFV1156, SBG/SBV485, FHGA2104(2)
    """
    if not code_cell:
        return []
    # Strip ordering-note suffixes like (2).
    code_cell = re.sub(r"\(\d+\)", "", code_cell)
    # First split on '/'; whitespace separators are not used for shared-suffix
    # package lists in these tables.
    parts = [p.strip() for p in code_cell.split("/") if p.strip()]

    # Some rows list prefix variants that share a trailing ball count, e.g.
    #   CL/CLG225  ->  CL225, CLG225
    #   SBG/SBV485 ->  SBG485, SBV485
    suffix: str | None = None
    for p in parts:
        m = re.search(r"(\d+)$", p)
        if m:
            suffix = m.group(1)
            break

    codes: list[str] = []
    for p in parts:
        if re.search(r"\d+$", p):
            codes.append(p.lower())
        elif suffix:
            codes.append((p + suffix).lower())

    # Keep only codes that look like package codes: letters followed by digits.
    return [c for c in codes if re.fullmatch(r"[a-z]+\d+", c)]


def find_header_indices(table: list[list[str | None]]) -> tuple[int, int, int] | None:
    """Return (header_row_index, pitch_col, size_col) for a package-spec table."""
    for ri, row in enumerate(table):
        pitch_col = size_col = None
        for ci, cell in enumerate(row):
            if cell is None:
                continue
            text = str(cell)
            if pitch_col is None and ("Pitch" in text or "pitch" in text):
                pitch_col = ci
        # Choose the first "Size" column that is after the pitch column and is
        # not the LSC "Ball Grid Size" column (Versal tables have both).
        if pitch_col is not None:
            for ci, cell in enumerate(row):
                if ci <= pitch_col or cell is None:
                    continue
                text = str(cell)
                if "Size" in text or "size" in text:
                    if "Grid" not in text and "LSC" not in text:
                        size_col = ci
                        break
        if pitch_col is not None and size_col is not None:
            return ri, pitch_col, size_col
    return None


def extract_pdf_specs(pdf_path: Path, pages: list[int] | None = None) -> dict[str, tuple[float, tuple[float, float]]]:
    specs: dict[str, tuple[float, tuple[float, float]]] = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        page_indices = pages if pages is not None else range(len(pdf.pages))
        for idx in page_indices:
            page = pdf.pages[idx]
            for table in page.extract_tables() or []:
                header = find_header_indices(table)
                if header is None:
                    continue
                header_row, pitch_col, size_col = header
                last_pitch: float | None = None
                last_size: tuple[float, float] | None = None
                for row in table[header_row + 1 :]:
                    if not row:
                        continue
                    code_cell = row[0]
                    if code_cell is None:
                        continue
                    code_text = str(code_cell).strip()
                    if not code_text:
                        continue
                    # Stop at notes / important sections.
                    if any(
                        marker in code_text
                        for marker in ("Notes:", "IMPORTANT", "Table", "BGA Packages")
                    ):
                        continue
                    codes = split_package_codes(code_text)
                    if not codes:
                        continue

                    pitch = parse_pitch(
                        row[pitch_col] if pitch_col < len(row) else None
                    )
                    size = parse_size(
                        row[size_col] if size_col < len(row) else None
                    )

                    # Fill down from the most recent populated row to handle
                    # merged cells that group several package codes together.
                    if pitch is not None:
                        last_pitch = pitch
                    if size is not None:
                        last_size = size

                    if pitch is None and last_pitch is not None:
                        pitch = last_pitch
                    if size is None and last_size is not None:
                        size = last_size

                    if pitch is None or size is None:
                        continue

                    for code in codes:
                        specs[code] = (pitch, size)
    return specs


def add_or_update_spec(db: dict, code: str, pitch: float, body: tuple[float, float]):
    """Store a package spec, deriving solder-mask and stencil openings from pitch."""
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
        "body_size_x": body[0],
        "body_size_y": body[1],
        "pad_diameter_mm": pad,
        "mask_opening_mm": round(pad + 0.05, 3),
        "paste_diameter_mm": round(max(0.1, pad - 0.05), 3),
    }


def load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_json(db: dict, path: Path):
    path.write_text(json.dumps(db, indent=2, sort_keys=True), encoding="utf-8")


def main():
    root = Path(__file__).parent
    db_path = root / "data" / "pkg_db.json"
    db = load_json(db_path)
    print(f"Initial entries: {len(db)}")

    for name, (filename, pages) in PDF_FILES.items():
        pdf_path = root / filename
        if not pdf_path.exists():
            print(f"Skip missing PDF: {filename}")
            continue
        specs = extract_pdf_specs(pdf_path, pages)
        print(f"{filename}: extracted {len(specs)} specs")
        for code, (pitch, size) in specs.items():
            add_or_update_spec(db, code, pitch, size)
        print(f"  db now: {len(db)}")

    save_json(db, db_path)
    print(f"Saved {len(db)} entries to pkg_db.json")


if __name__ == "__main__":
    main()
