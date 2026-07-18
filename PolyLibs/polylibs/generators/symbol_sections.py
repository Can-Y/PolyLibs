"""Canonical symbol unit partitioning and pin layout logic shared by generators."""

import re

from ..classifier import partition_for_symbol
from ..models import ClassifiedPin, SymbolSection


DEFAULT_MAX_PINS_PER_UNIT = 64
DEFAULT_MAX_UNITS = 25

_PROTECTED_MERGE_NAMES = frozenset({"VCCO_PSIO", "ADDR+CTRL", "DATA"})

_IO_DIFF_RE = re.compile(r"IO_L(\d+)([PN])_", re.I)
# Legacy MGT* / GTH / GTY / GTX / GTP transceivers (number before P/N).
_MGT_REFCLK_RE = re.compile(r"^(?:GTP|GTX|GTH|GTY|MGT[RYHPTX]*)REFCLK(\d+)([NP])_(\d+)", re.I)
_MGT_LANE_RE = re.compile(r"^(?:GTP|GTX|GTH|GTY|MGT[RYHPTX]*)(RX|TX)([NP])(\d+)_(\d+)", re.I)
# Versal GTYP / GTYP_MMI transceivers (P/N before number).
_MGT_VERSAL_REFCLK_RE = re.compile(r"^(?:GTYP_MMI_|GTYP_)REFCLK([NP])(\d+)_(\d+)", re.I)
_MGT_VERSAL_LANE_RE = re.compile(r"^(?:GTYP_MMI_|GTYP_)(RX|TX)([NP])(\d+)_(\d+)", re.I)
_PS_MGT_REFCLK_RE = re.compile(r"^PS_MGTREFCLK(\d+)([NP])_(\d+)$", re.I)
_PS_MGT_LANE_RE = re.compile(r"^PS_MGT(R?)(RX|TX)([NP])(\d+)_(\d+)$", re.I)


def natural_key(s: str) -> tuple:
    """Natural sort key: numbers compare numerically."""
    return tuple(int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s))


def io_sort_key(name: str) -> tuple:
    """Sort key for IO bank pins: keep differential pairs together, P before N."""
    m = _IO_DIFF_RE.search(name)
    if m:
        pair = int(m.group(1))
        pol = 0 if m.group(2).upper() == "P" else 1
        return (0, pair, pol, natural_key(name))
    return (1, natural_key(name), ())


def mgt_sort_key(name: str) -> tuple:
    """Sort key for UltraScale/UltraScale+/Versal MGT pins."""
    m = _MGT_REFCLK_RE.match(name)
    if m:
        bank = int(m.group(3))
        clk = int(m.group(1))
        pol = 0 if m.group(2).upper() == "P" else 1
        return (0, bank, 0, clk, pol, "")
    m = _MGT_VERSAL_REFCLK_RE.match(name)
    if m:
        bank = int(m.group(3))
        clk = int(m.group(2))
        pol = 0 if m.group(1).upper() == "P" else 1
        return (0, bank, 0, clk, pol, "")
    m = _MGT_LANE_RE.match(name)
    if m:
        bank = int(m.group(4))
        ch = int(m.group(3))
        dir_order = 0 if m.group(1).upper() == "RX" else 1
        pol = 0 if m.group(2).upper() == "P" else 1
        return (0, bank, 1, ch, dir_order, pol, "")
    m = _MGT_VERSAL_LANE_RE.match(name)
    if m:
        bank = int(m.group(4))
        ch = int(m.group(3))
        dir_order = 0 if m.group(1).upper() == "RX" else 1
        pol = 0 if m.group(2).upper() == "P" else 1
        return (0, bank, 1, ch, dir_order, pol, "")
    # Fallback: keep residual _RN/_RP or _N/_P pairs together (e.g. GTYP_RREF_RN/RP).
    if name.upper().endswith(("_RN", "_RP")):
        return (2, natural_key(name[:-3]), 0 if name[-1].upper() == "P" else 1)
    if re.match(r".+_(P|N)$", name, re.I):
        return (2, natural_key(name[:-2]), 0 if name[-1].upper() == "P" else 1)
    return (3, natural_key(name), "")


def ps_mgt_sort_key(name: str) -> tuple:
    """Sort key for Zynq PS MGT pins: keep REFCLK and TX/RX P/N pairs adjacent."""
    m = _PS_MGT_REFCLK_RE.match(name, re.I)
    if m:
        bank = int(m.group(3))
        clk = int(m.group(1))
        pol = 0 if m.group(2).upper() == "P" else 1
        return (0, bank, 0, clk, pol, "")
    m = _PS_MGT_LANE_RE.match(name, re.I)
    if m:
        bank = int(m.group(5))
        ch = int(m.group(4))
        dir_order = 0 if m.group(2).upper() == "RX" else 1
        pol = 0 if m.group(3).upper() == "P" else 1
        return (0, bank, 1, dir_order, ch, pol, "")
    return (1, natural_key(name), "")


def general_sort_key(name: str) -> tuple:
    """General sort key: group trailing P/N differential pairs, P before N."""
    m = re.match(r"(.+?)[_\-]?([PN])$", name, re.I)
    if m:
        return (0, natural_key(m.group(1)), 0 if m.group(2).upper() == "P" else 1)
    return (1, natural_key(name), 0)


def _io_group_key(name: str) -> tuple:
    """Group key for IO bank pins: differential pairs share the same key."""
    m = _IO_DIFF_RE.search(name)
    if m:
        return (0, int(m.group(1)))
    return (1, natural_key(name))


def _mgt_group_key(name: str) -> tuple:
    """Group key for MGT pins: same channel / REFCLK on the same side."""
    m = _PS_MGT_REFCLK_RE.match(name)
    if m:
        return (0, 0, int(m.group(1)))
    m = _PS_MGT_LANE_RE.match(name)
    if m:
        return (0, 1, int(m.group(4)))
    m = _MGT_REFCLK_RE.match(name)
    if m:
        return (0, 0, int(m.group(1)))
    m = _MGT_VERSAL_REFCLK_RE.match(name)
    if m:
        return (0, 0, int(m.group(2)))
    m = _MGT_LANE_RE.match(name)
    if m:
        return (0, 1, int(m.group(3)))
    m = _MGT_VERSAL_LANE_RE.match(name)
    if m:
        return (0, 1, int(m.group(3)))
    return (1, natural_key(name))


def _section_pin_sort_key(sec_name: str, cp: ClassifiedPin) -> tuple:
    """Sort key for a single pin inside a section."""
    name = cp.record.pin_name
    if sec_name.startswith("MGT Bank"):
        if name.startswith("PS_MGT"):
            return ps_mgt_sort_key(name) + (cp.record.ball_id,)
        return mgt_sort_key(name) + (cp.record.ball_id,)
    if sec_name.startswith("Power"):
        return (cp.rail_name or "", natural_key(name), cp.record.ball_id)
    if sec_name == "Ground":
        return natural_key(name) + (cp.record.ball_id,)
    if sec_name.startswith("Bank"):
        return io_sort_key(name) + (cp.record.ball_id,)
    return general_sort_key(name) + (cp.record.ball_id,)


def _category(name: str) -> str:
    """Broad category used when compressing units."""
    if name == "Ground":
        return "Ground"
    if name.startswith("Power"):
        return "Power"
    if name.startswith("No Connect"):
        return "No Connect"
    if name.startswith("MGT Bank"):
        return "MGT"
    if name.startswith("Bank"):
        return "Bank"
    return "Other"


def _is_protected(name: str) -> bool:
    return any(protected in name for protected in _PROTECTED_MERGE_NAMES)


def compress_symbol_sections(
    units: list[SymbolSection],
    *,
    max_units: int = DEFAULT_MAX_UNITS,
    max_pins: int = DEFAULT_MAX_PINS_PER_UNIT,
) -> list[SymbolSection]:
    """Greedy-merge adjacent units until the unit count is within the Cadence limit.

    Merges prefer same-category neighbours and avoid units whose names contain
    user-preserved keywords (e.g. ``VCCO_PSIO``, ``ADDR+CTRL``, ``DATA``).  If
    no same-category merge fits within ``max_pins``, the size limit is relaxed
    until a merge becomes possible.
    """
    units = list(units)
    current_max_pins = max_pins
    while len(units) > max_units:
        best_same_idx = -1
        best_same_size = None
        best_cross_idx = -1
        best_cross_size = None
        for i in range(len(units) - 1):
            left, right = units[i], units[i + 1]
            if _is_protected(left.name) or _is_protected(right.name):
                continue
            combined = len(left.pins) + len(right.pins)
            if combined > current_max_pins:
                continue
            if _category(left.name) == _category(right.name):
                if best_same_size is None or combined < best_same_size:
                    best_same_size = combined
                    best_same_idx = i
            else:
                if best_cross_size is None or combined < best_cross_size:
                    best_cross_size = combined
                    best_cross_idx = i

        if best_same_idx >= 0:
            best_idx = best_same_idx
        elif best_cross_idx >= 0:
            best_idx = best_cross_idx
        else:
            current_max_pins *= 2
            continue

        left, right = units[best_idx], units[best_idx + 1]
        merged = SymbolSection(
            name=f"{left.name} + {right.name}",
            side=left.side,
            pins=sorted(
                left.pins + right.pins,
                key=lambda cp: _section_pin_sort_key(left.name, cp),
            ),
        )
        units[best_idx : best_idx + 2] = [merged]
    return units


def assign_sides(
    pins: list[ClassifiedPin], sec_name: str
) -> tuple[list[ClassifiedPin], list[ClassifiedPin]]:
    """Assign pins to the left side so pin numbers run top-to-bottom on one side.

    Differential pairs / channels are still grouped together, but all groups are
    placed on the left side of the symbol instead of alternating left/right.
    """
    if sec_name.startswith("MGT Bank"):
        group_key = lambda cp: _mgt_group_key(cp.record.pin_name)
    elif sec_name.startswith("Bank"):
        group_key = lambda cp: _io_group_key(cp.record.pin_name)
    else:
        # For power, ground, config, etc. place each pin individually.
        return (pins, [])

    groups: dict[tuple, list[ClassifiedPin]] = {}
    for cp in pins:
        groups.setdefault(group_key(cp), []).append(cp)
    sorted_group_keys = sorted(groups.keys())

    left: list[ClassifiedPin] = []
    for key in sorted_group_keys:
        group = sorted(groups[key], key=lambda cp: _section_pin_sort_key(sec_name, cp))
        left.extend(group)
    return left, []


def build_symbol_sections(
    pins: list[ClassifiedPin],
    *,
    max_pins_per_unit: int = DEFAULT_MAX_PINS_PER_UNIT,
    max_units: int | None = None,
) -> list[SymbolSection]:
    """Split classified pins into canonical symbol units.

    The returned list is ordered and every unit is ready to render: pins are
    sorted and any unit larger than ``max_pins_per_unit`` is split into
    numbered chunks.
    """
    sections = partition_for_symbol(pins)

    # Merge all Ground sections into one unit.
    ground_pins: list[ClassifiedPin] = []
    other_sections: list[SymbolSection] = []
    for sec in sections:
        if sec.name == "Ground":
            ground_pins.extend(sec.pins)
        elif sec.name == "MGT Transceivers":
            bank_groups: dict[str, list[ClassifiedPin]] = {}
            for cp in sec.pins:
                bank = cp.record.bank if cp.record.bank and cp.record.bank != "NA" else "?"
                bank_groups.setdefault(bank, []).append(cp)
            for bank in sorted(
                bank_groups.keys(),
                key=lambda b: (not b.isdigit(), int(b) if b.isdigit() else b),
            ):
                other_sections.append(
                    SymbolSection(name=f"MGT Bank {bank}", side="top", pins=bank_groups[bank])
                )
        else:
            other_sections.append(sec)
    if ground_pins:
        other_sections.append(SymbolSection(name="Ground", side="bottom", pins=ground_pins))
    sections = other_sections

    # Consolidate all VCCO_PS* pins into one dedicated power unit.
    psio_pins: list[ClassifiedPin] = []
    kept_sections: list[SymbolSection] = []
    for sec in sections:
        rest = [cp for cp in sec.pins if not cp.record.pin_name.startswith("VCCO_PS")]
        psio_pins.extend(cp for cp in sec.pins if cp.record.pin_name.startswith("VCCO_PS"))
        if rest:
            kept_sections.append(SymbolSection(name=sec.name, side=sec.side, pins=rest))
    if psio_pins:
        kept_sections.append(SymbolSection(name="Power: VCCO_PSIO", side="bottom", pins=psio_pins))
    sections = kept_sections

    # Split Bank 504 DDR pins into address/control and data units.
    ddr_split_sections: list[SymbolSection] = []
    for sec in sections:
        if sec.name == "Bank 504":
            addr_ctrl: list[ClassifiedPin] = []
            data: list[ClassifiedPin] = []
            other: list[ClassifiedPin] = []
            for cp in sec.pins:
                name = cp.record.pin_name
                if name.startswith(("PS_DDR_DQ", "PS_DDR_DM", "PS_DDR_DQS_")):
                    data.append(cp)
                elif name.startswith("PS_DDR_"):
                    addr_ctrl.append(cp)
                else:
                    other.append(cp)
            if addr_ctrl:
                ddr_split_sections.append(
                    SymbolSection(name="Bank 504 ADDR+CTRL", side=sec.side, pins=addr_ctrl)
                )
            if data:
                ddr_split_sections.append(
                    SymbolSection(name="Bank 504 DATA", side=sec.side, pins=data)
                )
            if other:
                ddr_split_sections.append(SymbolSection(name=sec.name, side=sec.side, pins=other))
        else:
            ddr_split_sections.append(sec)
    sections = ddr_split_sections

    # Order sections consistently.
    def _sort_key(sec: SymbolSection) -> tuple:
        if sec.name == "Ground":
            return (3, "")
        if sec.name.startswith("Power"):
            return (2, natural_key(sec.name))
        if sec.name in ("Configuration", "Analog / ADC", "No Connect") or sec.name.startswith("MGT"):
            return (0, sec.name)
        return (1, sec.name)

    sections.sort(key=_sort_key)

    # Sort pins inside each section and enforce max-pins-per-unit limit.
    expanded: list[SymbolSection] = []
    for sec in sections:
        sorted_pins = sorted(sec.pins, key=lambda cp: _section_pin_sort_key(sec.name, cp))
        if len(sorted_pins) <= max_pins_per_unit:
            expanded.append(SymbolSection(name=sec.name, side=sec.side, pins=sorted_pins))
            continue
        for idx, start in enumerate(range(0, len(sorted_pins), max_pins_per_unit)):
            chunk = sorted_pins[start : start + max_pins_per_unit]
            expanded.append(SymbolSection(name=f"{sec.name}_{idx + 1}", side=sec.side, pins=chunk))

    if max_units is not None and len(expanded) > max_units:
        expanded = compress_symbol_sections(
            expanded, max_units=max_units, max_pins=max_pins_per_unit
        )
    return expanded
