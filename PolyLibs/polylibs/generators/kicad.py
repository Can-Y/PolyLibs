"""KiCad footprint/symbol generator.

Outputs modern KiCad s-expression ``.kicad_mod`` footprint files and
``.kicad_sym`` schematic symbol files.  No KiCad installation or API is
required; the files can be imported directly into the symbol/footprint editor.
"""

import re
import uuid

from ..classifier import partition_for_symbol
from ..models import DevicePinout, PackageSpec, ClassifiedPin, PinDirection, SymbolSection
from .base import Generator


_IO_DIFF_RE = re.compile(r'IO_L(\d+)([PN])_', re.I)
_MGT_REFCLK_RE = re.compile(r'^MGTREFCLK(\d+)([NP])_(\d+)', re.I)
_MGT_LANE_RE = re.compile(r'^MGT[RYHPTX]*(RX|TX)([NP])(\d+)_(\d+)', re.I)


def _natural_key(s: str) -> tuple:
    """Natural sort key: numbers compare numerically."""
    return tuple(int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s))


def _io_sort_key(name: str) -> tuple:
    """Sort key for IO bank pins: keep differential pairs together, P before N."""
    m = _IO_DIFF_RE.search(name)
    if m:
        pair = int(m.group(1))
        pol = 0 if m.group(2).upper() == 'P' else 1
        return (0, pair, pol, _natural_key(name))
    return (1, _natural_key(name), ())


def _mgt_sort_key(name: str) -> tuple:
    """Sort key for MGT pins: same channel and TX/RX differential pairs together."""
    m = _MGT_REFCLK_RE.match(name)
    if m:
        bank = int(m.group(3))
        clk = int(m.group(1))
        pol = 0 if m.group(2).upper() == 'P' else 1
        return (0, bank, 0, clk, pol, '')
    m = _MGT_LANE_RE.match(name)
    if m:
        bank = int(m.group(4))
        ch = int(m.group(3))
        dir_order = 0 if m.group(1).upper() == 'RX' else 1
        pol = 0 if m.group(2).upper() == 'P' else 1
        return (0, bank, 1, ch, dir_order, pol, '')
    return (1, _natural_key(name), '')


def _general_sort_key(name: str) -> tuple:
    """General sort key: group trailing P/N differential pairs, P before N."""
    m = re.match(r'(.+?)[_\-]?([PN])$', name, re.I)
    if m:
        return (0, _natural_key(m.group(1)), 0 if m.group(2).upper() == 'P' else 1)
    return (1, _natural_key(name), 0)


def _io_group_key(name: str) -> tuple:
    """Group key for IO bank pins: differential pairs share the same key."""
    m = _IO_DIFF_RE.search(name)
    if m:
        return (0, int(m.group(1)))
    return (1, _natural_key(name))


def _mgt_group_key(name: str) -> tuple:
    """Group key for MGT pins: same channel on the same side."""
    m = _MGT_REFCLK_RE.match(name)
    if m:
        return (0, 0, int(m.group(1)))  # REFCLK groups come first
    m = _MGT_LANE_RE.match(name)
    if m:
        return (0, 1, int(m.group(3)))
    return (1, _natural_key(name))


def _assign_sides(pins: list[ClassifiedPin], sec_name: str) -> tuple[list[ClassifiedPin], list[ClassifiedPin]]:
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

    # Group pins, sort groups, then place all groups on the left side so pin
    # numbers run top-to-bottom on a single side instead of alternating sides.
    groups: dict[tuple, list[ClassifiedPin]] = {}
    for cp in pins:
        groups.setdefault(group_key(cp), []).append(cp)
    sorted_group_keys = sorted(groups.keys())

    left: list[ClassifiedPin] = []
    for key in sorted_group_keys:
        group = sorted(groups[key], key=lambda cp: _section_pin_sort_key_for_group(sec_name, cp))
        left.extend(group)
    return left, []


def _section_pin_sort_key_for_group(sec_name: str, cp: ClassifiedPin) -> tuple:
    """Sort key used inside a group (pairs already kept together by grouping)."""
    name = cp.record.pin_name
    if sec_name.startswith("MGT Bank"):
        return _mgt_sort_key(name)
    if sec_name.startswith("Bank"):
        return _io_sort_key(name)
    return _general_sort_key(name)


_KICAD_PIN_TYPE = {
    PinDirection.INPUT: "input",
    PinDirection.OUTPUT: "output",
    PinDirection.BIDIR: "bidirectional",
    PinDirection.POWER: "power_in",
    PinDirection.GROUND: "power_in",
    PinDirection.PASSIVE: "passive",
    PinDirection.NC: "no_connect",
}


class KiCadGenerator(Generator):
    @property
    def name(self) -> str:
        return "KiCad"

    def generate_symbol(
        self,
        device: DevicePinout,
        pins: list[ClassifiedPin],
        spec: PackageSpec,
    ) -> dict[str, str]:
        part_name = device.full_name
        pkg_name = device.package_code.upper()
        sections = partition_for_symbol(pins)

        # Split MGT section by bank.  Keep each Power: {rail} section separate so
        # that the same power rail is not split across units.  Merge all Ground
        # pins into one section.
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
                for bank in sorted(bank_groups.keys(), key=lambda b: (not b.isdigit(), int(b) if b.isdigit() else b)):
                    other_sections.append(
                        SymbolSection(name=f"MGT Bank {bank}", side="top", pins=bank_groups[bank])
                    )
            else:
                other_sections.append(sec)

        if ground_pins:
            other_sections.append(SymbolSection(name="Ground", side="bottom", pins=ground_pins))
        sections = other_sections

        # Sort sections so that related functional groups are grouped together.
        def _sort_key(sec):
            if sec.name == "Ground":
                return (3, "")
            if sec.name.startswith("Power"):
                return (2, _natural_key(sec.name))
            if sec.name in ("Configuration", "Analog / ADC", "No Connect") or sec.name.startswith("MGT"):
                return (0, sec.name)
            return (1, sec.name)

        sections.sort(key=_sort_key)

        # Split any section larger than 64 pins into multiple units.
        MAX_PINS_PER_UNIT = 64

        def _section_pin_sort_key(sec_name: str, cp: ClassifiedPin) -> tuple:
            name = cp.record.pin_name
            if sec_name.startswith("MGT Bank"):
                return _mgt_sort_key(name) + (cp.record.ball_id,)
            if sec_name.startswith("Power"):
                return (cp.rail_name or "", _natural_key(name), cp.record.ball_id)
            if sec_name == "Ground":
                return _natural_key(name) + (cp.record.ball_id,)
            if sec_name.startswith("Bank"):
                return _io_sort_key(name) + (cp.record.ball_id,)
            return _general_sort_key(name) + (cp.record.ball_id,)

        expanded_sections: list[SymbolSection] = []
        for sec in sections:
            sorted_pins = sorted(sec.pins, key=lambda cp: _section_pin_sort_key(sec.name, cp))
            if len(sorted_pins) <= MAX_PINS_PER_UNIT:
                expanded_sections.append(SymbolSection(name=sec.name, side=sec.side, pins=sorted_pins))
                continue
            for idx, start in enumerate(range(0, len(sorted_pins), MAX_PINS_PER_UNIT)):
                chunk = sorted_pins[start:start + MAX_PINS_PER_UNIT]
                suffix = f"{sec.name}_{idx + 1}"
                expanded_sections.append(SymbolSection(name=suffix, side=sec.side, pins=chunk))
        sections = expanded_sections

        spacing = 2.54
        pin_len = 5.08  # doubled so pin numbers are not covered by the body
        margin = 2.54
        base_symbol_width = 50.8  # 20 * 2.54 mm, wider to allow pins on both sides

        lines = [
            '(kicad_symbol_lib',
            '  (version 20231129)',
            '  (generator "polylibs")',
        ]

        def _pin_line(cp: ClassifiedPin, x: float, y: float, angle: int, indent: int = 6) -> str:
            name = cp.record.pin_name.replace('"', '\\"')
            ball = cp.record.ball_id
            etype = _KICAD_PIN_TYPE.get(cp.direction, "passive")
            prefix = " " * indent
            return (
                f'{prefix}(pin {etype} line (at {x:.4f} {y:.4f} {angle}) (length {pin_len:.2f})'
                f' (name "{name}" (effects (font (size 1.27 1.27))))'
                f' (number "{ball}" (effects (font (size 1.27 1.27))))'
                ' )'
            )

        for sec in sections:
            # Each bank / functional group becomes its own independent symbol so
            # the user can place them separately on the schematic.
            safe_suffix = sec.name.replace(":", " ").replace("/", " ").strip()
            safe_suffix = "_".join(safe_suffix.split())
            sym_name = f"{part_name}_{safe_suffix}"

            sec_pins = sec.pins
            n_pins = len(sec_pins)

            # Distribute pins to sides.  For IO/MGT keep pairs/channels on one side;
            # for other sections place all pins on the left side.
            left_pins, right_pins = _assign_sides(sec_pins, sec.name)
            n_left = len(left_pins)
            n_right = len(right_pins)

            # Widen the unit if pin names are long, so left/right names don't overlap.
            max_name_len = max((len(cp.record.pin_name) for cp in sec_pins), default=0)
            name_width_mm = max_name_len * 0.7  # font size 1.27, char width ~0.7 mm
            required_width = (2 * name_width_mm + 4 * margin + 2 * pin_len) * 1.1  # 10% safety margin
            symbol_width = max(base_symbol_width, ((required_width // 2.54) + 1) * 2.54)

            block_h = (max(n_left, n_right, 1) - 1) * spacing + 2 * margin
            half_h = block_h / 2.0
            half_w = symbol_width / 2.0

            lines.append(f'  (symbol "{sym_name}"')
            lines.append('    (pin_names (offset 1.016))')
            lines.append('    (exclude_from_sim no)')
            lines.append('    (in_bom yes)')
            lines.append('    (on_board yes)')
            lines.append(f'    (property "Reference" "U" (at 0 {half_h + 3.5:.2f} 0)')
            lines.append('      (effects (font (size 1.27 1.27)) (justify bottom))')
            lines.append('    )')
            lines.append(f'    (property "Value" "{sym_name}" (at 0 {-half_h - 3.5:.2f} 0)')
            lines.append('      (effects (font (size 1.27 1.27)) (justify top))')
            lines.append('    )')
            lines.append(f'    (property "Footprint" "{pkg_name}" (at 0 {-half_h - 5.5:.2f} 0)')
            lines.append('      (effects (font (size 1.27 1.27)) (justify top) hide)')
            lines.append('    )')
            lines.append(f'    (property "Description" "Xilinx FPGA {part_name} - {sec.name}" (at 0 {half_h + 5.5:.2f} 0)')
            lines.append('      (effects (font (size 1.27 1.27)) (justify bottom) hide)')
            lines.append('    )')

            # Default unit for the independent symbol.
            lines.append(f'    (symbol "{sym_name}_0_1"')
            lines.append(f'      (text "{sec.name}" (at 0 {half_h - 0.5:.2f} 0)')
            lines.append('        (effects (font (size 1.27 1.27)) (justify bottom))')
            lines.append('      )')
            lines.append(
                f'      (rectangle (start {-half_w:.2f} {half_h:.2f}) (end {half_w:.2f} {-half_h:.2f})'
                ' (stroke (width 0.254) (type default)) (fill (type background)) )'
            )

            # Distribute pins on both sides to keep the unit compact.
            start_y = half_h - margin
            for i, cp in enumerate(left_pins):
                y = start_y - i * spacing
                x = -(half_w + pin_len)
                lines.append(_pin_line(cp, x, y, 0))

            for i, cp in enumerate(right_pins):
                y = start_y - i * spacing
                x = half_w + pin_len
                lines.append(_pin_line(cp, x, y, 180))

            lines.append('    )')
            lines.append('  )')

        lines.append(')')
        return {f"{part_name}.kicad_sym": "\n".join(lines)}

    def generate_footprint(
        self,
        device: DevicePinout,
        spec: PackageSpec,
        coords: dict[str, tuple[float, float]],
    ) -> dict[str, str]:
        pkg_name = device.package_code.upper()
        pad_size = spec.pad_diameter_mm
        half_x = spec.body_size_x / 2.0
        half_y = spec.body_size_y / 2.0
        silk_hx = half_x + 0.5
        silk_hy = half_y + 0.5

        def _uuid() -> str:
            return str(uuid.uuid4())

        def _fp_line(x1: float, y1: float, x2: float, y2: float, layer: str, width: float = 0.15) -> str:
            return (
                f'  (fp_line\n'
                f'    (start {x1:.4f} {y1:.4f})\n'
                f'    (end {x2:.4f} {y2:.4f})\n'
                f'    (stroke\n'
                f'      (width {width:.3f})\n'
                f'      (type default)\n'
                f'    )\n'
                f'    (layer "{layer}")\n'
                f'    (uuid "{_uuid()}")\n'
                f'  )'
            )

        def _property(name: str, value: str, at_y: float, layer: str, hide: bool = False) -> str:
            hide_line = "\n    (hide yes)" if hide else ""
            return (
                f'  (property "{name}" "{value}"\n'
                f'    (at 0 {at_y:.4f} 0)\n'
                f'    (layer "{layer}")'
                f'{hide_line}\n'
                f'    (uuid "{_uuid()}")\n'
                f'    (effects (font (size 1.27 1.27)))\n'
                f'  )'
            )

        lines = [
            f'(footprint "{pkg_name}"',
            '  (version 20240101)',
            '  (generator "polylibs")',
            f'  (uuid "{_uuid()}")',
            '  (layer "F.Cu")',
            f'  (descr "{device.full_name} {pkg_name} BGA")',
            '  (tags "BGA FPGA")',
            '  (attr smd)',
            '  (property "Reference" "REF**"',
            f'    (at 0 {-silk_hy - 1.5:.4f} 0)',
            '    (layer "F.SilkS")',
            f'    (uuid "{_uuid()}")',
            '    (effects (font (size 1 1) (thickness 0.15)))',
            '  )',
            '  (property "Value" "{}"'.format(pkg_name),
            f'    (at 0 {silk_hy + 1.5:.4f} 0)',
            '    (layer "F.Fab")',
            f'    (uuid "{_uuid()}")',
            '    (effects (font (size 1 1) (thickness 0.15)))',
            '  )',
            _property("Datasheet", "", 0.0, "F.Fab", hide=True),
            _property("Description", "", 0.0, "F.Fab", hide=True),
        ]

        # Silkscreen rectangle
        lines.append(_fp_line(-silk_hx, -silk_hy, silk_hx, -silk_hy, "F.SilkS"))
        lines.append(_fp_line(silk_hx, -silk_hy, silk_hx, silk_hy, "F.SilkS"))
        lines.append(_fp_line(silk_hx, silk_hy, -silk_hx, silk_hy, "F.SilkS"))
        lines.append(_fp_line(-silk_hx, silk_hy, -silk_hx, -silk_hy, "F.SilkS"))

        # Fabrication outline
        lines.append(_fp_line(-half_x, -half_y, half_x, -half_y, "F.Fab", 0.1))
        lines.append(_fp_line(half_x, -half_y, half_x, half_y, "F.Fab", 0.1))
        lines.append(_fp_line(half_x, half_y, -half_x, half_y, "F.Fab", 0.1))
        lines.append(_fp_line(-half_x, half_y, -half_x, -half_y, "F.Fab", 0.1))

        # Pin-1 marker near A1 (top-left in our coordinate system)
        a1_coord = coords.get("A1")
        if a1_coord is not None:
            ax, ay = a1_coord
            marker_x = ax - pad_size
            marker_y = ay + pad_size
            lines.append(
                f'  (fp_circle\n'
                f'    (center {marker_x:.4f} {marker_y:.4f})\n'
                f'    (end {marker_x + 0.5:.4f} {marker_y:.4f})\n'
                f'    (stroke\n'
                f'      (width 0.15)\n'
                f'      (type default)\n'
                f'    )\n'
                f'    (fill no)\n'
                f'    (layer "F.SilkS")\n'
                f'    (uuid "{_uuid()}")\n'
                f'  )'
            )

        for ball_id, (x, y) in sorted(coords.items()):
            lines.append(
                f'  (pad "{ball_id}" smd circle\n'
                f'    (at {x:.4f} {y:.4f})\n'
                f'    (size {pad_size:.4f} {pad_size:.4f})\n'
                '    (layers "F.Cu" "F.Mask" "F.Paste")\n'
                f'    (solder_mask_margin {spec.mask_opening_mm - pad_size:.4f})\n'
                f'    (uuid "{_uuid()}")\n'
                f'  )'
            )

        lines.append(')')
        return {f"{pkg_name}.kicad_mod": "\n".join(lines)}
