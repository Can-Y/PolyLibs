"""Package geometry: BGA coordinates and package specifications."""

import json
import math
import re
from pathlib import Path

import yaml

from .models import PackageSpec, PinRecord


def _fuzzy_lookup(pkg_lower: str, db: dict) -> dict | None:
    """Try to find a known spec by matching prefix family and ball count.

    A suffix-only match can return the wrong package (e.g. ``fgg484`` matching
    ``sbvb484``).  We therefore require that the candidate key starts with the
    same package-family prefix as the requested code.
    """
    if pkg_lower in db:
        return db[pkg_lower]

    m = re.search(r'(\d+)$', pkg_lower)
    if not m:
        return None
    suffix = m.group(1)
    prefix = _package_family_prefix(pkg_lower)

    candidates: list[tuple[str, dict]] = []
    for key, spec in db.items():
        if key.endswith(suffix) and _package_family_prefix(key) == prefix:
            candidates.append((key, spec))

    if candidates:
        # Prefer the closest match by length of the package code.
        candidates.sort(key=lambda item: abs(len(item[0]) - len(pkg_lower)))
        return candidates[0][1]
    return None


def _package_family_prefix(pkg_lower: str) -> str:
    """Return the alphabetic family prefix of a package code.

    Examples:
        - ``fgg484`` -> ``f``
        - ``ffvb676`` -> ``ff``
        - ``csga324`` -> ``c``
        - ``sbva484`` -> ``s``
    """
    m = re.match(r'([a-z]+)', pkg_lower)
    return m.group(1) if m else ''


def _heuristic_spec(ball_count: int) -> tuple[float, float, float]:
    if ball_count <= 256:
        return 0.80, 17.0, 0.40
    if ball_count <= 484:
        return 1.00, 23.0, 0.45
    if ball_count <= 676:
        return 1.00, 27.0, 0.45
    if ball_count <= 900:
        return 1.00, 31.0, 0.45
    if ball_count <= 1156:
        return 1.00, 35.0, 0.45
    if ball_count <= 1517:
        return 1.00, 40.0, 0.45
    if ball_count <= 1760:
        return 1.00, 42.5, 0.50
    if ball_count <= 2104:
        return 1.00, 47.5, 0.50
    if ball_count <= 2892:
        return 1.00, 55.0, 0.50
    return 1.00, 60.0, 0.50


# Pitch/body hints keyed by package prefix.  These are conservative defaults
# grouped by package family; exact specs should still be added to pkg_db.json.
_PREFIX_HINTS: dict[str, tuple[float, float, float]] = {
    # 0.50 mm pitch wire-bond CSP / tiny BGA
    "cp": (0.50, 10.0, 0.25),
    "pu": (0.50, 12.0, 0.25),
    "pfc": (0.50, 10.0, 0.25),
    "pub": (0.50, 12.0, 0.25),
    "tcpg": (0.50, 10.0, 0.25),
    "tcps": (0.50, 10.0, 0.25),
    # 0.80 mm pitch CSP / fine-pitch BGA
    "csg": (0.80, 15.0, 0.40),
    "cs": (0.80, 15.0, 0.40),
    "ft": (0.80, 13.0, 0.40),
    "sb": (0.80, 19.0, 0.40),
    "psb": (0.80, 19.0, 0.40),
    "tcsg": (0.80, 15.0, 0.40),
    "cgsb": (0.80, 19.0, 0.40),
    "sfv": (0.80, 19.0, 0.40),
    # 1.00 mm pitch FPBGA / FFBGA / TFBGA families
    "fgg": (1.00, 23.0, 0.45),
    "fg": (1.00, 23.0, 0.45),
    "fbg": (1.00, 23.0, 0.45),
    "fb": (1.00, 23.0, 0.45),
    "ffg": (1.00, 23.0, 0.45),
    "ffr": (1.00, 23.0, 0.45),
    "ffv": (1.00, 23.0, 0.45),
    "ff": (1.00, 23.0, 0.45),
    "flg": (1.00, 23.0, 0.45),
    "flv": (1.00, 23.0, 0.45),
    "fl": (1.00, 23.0, 0.45),
    "fhg": (1.00, 23.0, 0.45),
    "fh": (1.00, 23.0, 0.45),
    "fsg": (1.00, 23.0, 0.45),
    "fsv": (1.00, 23.0, 0.45),
    "fs": (1.00, 23.0, 0.45),
    "tf": (1.00, 23.0, 0.45),
    "ts": (1.00, 23.0, 0.45),
    "t": (1.00, 23.0, 0.45),
    "pff": (1.00, 23.0, 0.45),
    "pfh": (1.00, 23.0, 0.45),
    "pfi": (1.00, 23.0, 0.45),
    "pfl": (1.00, 23.0, 0.45),
    "pfs": (1.00, 23.0, 0.45),
    "cgff": (1.00, 23.0, 0.45),
    "cgsf": (1.00, 23.0, 0.45),
    "cgub": (1.00, 23.0, 0.45),
    "dr": (1.00, 23.0, 0.45),
    "eg": (1.00, 23.0, 0.45),
    "ev": (1.00, 23.0, 0.45),
    "f": (1.00, 23.0, 0.45),
    # Fallbacks
    "s": (0.80, 19.0, 0.40),
    "c": (0.80, 15.0, 0.40),
    "p": (0.80, 19.0, 0.40),
}


def _prefix_heuristic_spec(pkg_lower: str, ball_count: int) -> tuple[float, float, float]:
    """Return a heuristic pitch/body/pad based on package family prefix."""
    # Use the longest matching prefix hint.
    matching = [
        (prefix, spec) for prefix, spec in _PREFIX_HINTS.items() if pkg_lower.startswith(prefix)
    ]
    if matching:
        pitch, base_body, pad = max(matching, key=lambda item: len(item[0]))[1]
    else:
        return _heuristic_spec(ball_count)

    # Very large FSV* / FS* packages with >3000 balls use 0.92 mm pitch.
    if pkg_lower.startswith("fs") and ball_count >= 3000:
        pitch = 0.92

    if ball_count > 0:
        side = math.ceil(ball_count ** 0.5)
        if pitch <= 0.5:
            margin = 2.5
        elif pitch <= 0.8:
            margin = 1.0
        else:
            margin = 3.0 if side <= 18 else 1.5 if side <= 30 else 1.0
        body = max(base_body, round(side * pitch + margin, 1))
    else:
        body = base_body
    return pitch, body, pad


class PackageRegistry:
    """External package geometry database with series-level overrides."""

    def __init__(self, data_root: Path):
        self.data_root = data_root
        self._db: dict[str, dict] = {}

    def load(self) -> "PackageRegistry":
        db_path = self.data_root / "data" / "pkg_db.json"
        if db_path.exists():
            self._db = json.loads(db_path.read_text(encoding="utf-8"))
        return self

    def add_series_packages(self, source: Path | dict) -> None:
        if isinstance(source, Path):
            text = source.read_text(encoding="utf-8")
            if source.suffix in (".yaml", ".yml"):
                data = yaml.safe_load(text)
            else:
                data = json.loads(text)
        else:
            data = source
        if isinstance(data, dict):
            self._db.update(data)

    def get_spec(
        self,
        package_code: str,
        ball_count: int = 0,
        override_pitch: float | None = None,
        override_body_size: tuple[float, float] | None = None,
        override_pad_dia: float | None = None,
    ) -> PackageSpec:
        pkg_lower = package_code.lower().strip()
        spec = self._db.get(pkg_lower) or _fuzzy_lookup(pkg_lower, self._db)

        if spec:
            pitch = spec["pitch_mm"]
            body_x = spec["body_size_x"]
            body_y = spec["body_size_y"]
            pad = spec["pad_diameter_mm"]
            mask = spec["mask_opening_mm"]
            paste = spec["paste_diameter_mm"]
        else:
            pitch, body, pad = _prefix_heuristic_spec(pkg_lower, ball_count)
            body_x = body_y = body
            mask = pad + 0.05
            paste = max(0.1, pad - 0.05)

        if override_pitch is not None:
            pitch = override_pitch
        if override_body_size is not None:
            body_x, body_y = override_body_size
        if override_pad_dia is not None:
            pad = override_pad_dia
            mask = pad + 0.05
            paste = max(0.1, pad - 0.05)

        return PackageSpec(pitch, body_x, body_y, pad, mask, paste)


_PKG_REGISTRY: PackageRegistry | None = None


def _default_data_root() -> Path:
    """Locate the project root containing ``data/pkg_db.json``.

    Search upward from the package directory so the same code works both in
    the repo layout (``PolyLibs/polylibs/...``) and in a standalone
    distribution where ``data/`` sits next to the package directory.
    """
    start = Path(__file__).parent.parent
    for candidate in (start, start.parent):
        if (candidate / "data" / "pkg_db.json").exists():
            return candidate
    return start


def get_package_spec(
    package_code: str,
    ball_count: int = 0,
    override_pitch: float | None = None,
    override_body_size: tuple[float, float] | None = None,
    override_pad_dia: float | None = None,
    data_root: Path | None = None,
) -> PackageSpec:
    """Get package spec, with optional overrides.

    Uses a global default registry.  A custom ``data_root`` can be supplied to
    force re-initialisation from a different runtime data directory.
    """
    global _PKG_REGISTRY
    if _PKG_REGISTRY is None or data_root is not None:
        root = data_root or _default_data_root()
        _PKG_REGISTRY = PackageRegistry(root).load()
    return _PKG_REGISTRY.get_spec(
        package_code,
        ball_count=ball_count,
        override_pitch=override_pitch,
        override_body_size=override_body_size,
        override_pad_dia=override_pad_dia,
    )


def compute_ball_coordinates(
    pins: list[PinRecord],
    spec: PackageSpec,
) -> dict[str, tuple[float, float]]:
    """Compute physical (X, Y) coordinates for BGA balls, origin at center."""
    if not pins:
        return {}
    max_col = max(p.col_index for p in pins)
    max_row = max(p.row_index for p in pins)
    min_col = min(p.col_index for p in pins)
    min_row = min(p.row_index for p in pins)
    col_center = (max_col + min_col) / 2.0
    row_center = (max_row + min_row) / 2.0
    pitch = spec.pitch_mm

    coords: dict[str, tuple[float, float]] = {}
    for pin in pins:
        x = round((pin.col_index - col_center) * pitch, 4)
        y = round((row_center - pin.row_index) * pitch, 4)
        coords[pin.ball_id] = (x, y)
    return coords


def get_grid_bounds(pins: list[PinRecord]) -> tuple[int, int, int, int]:
    if not pins:
        return 0, 0, 0, 0
    return (
        min(p.col_index for p in pins),
        max(p.col_index for p in pins),
        min(p.row_index for p in pins),
        max(p.row_index for p in pins),
    )
