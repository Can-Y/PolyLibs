"""Cadence OrCAD Capture TCL and Allegro SKILL generator."""

import datetime
from ..models import DevicePinout, PackageSpec, ClassifiedPin
from ..classifier import partition_for_symbol
from .base import Generator


class CadenceGenerator(Generator):
    @property
    def name(self) -> str:
        return "Cadence"

    def generate_symbol(
        self,
        device: DevicePinout,
        pins: list[ClassifiedPin],
        spec: PackageSpec,
    ) -> dict[str, str]:
        sections = partition_for_symbol(pins)
        part_name = device.full_name.upper()

        lines = [
            f"# Capture TCL — {part_name}",
            "proc main {} {",
            f'  puts "Creating {part_name}..."',
            f'  set lLib [DboCreateLib "{part_name}.olb"]',
            f'  if {{$lLib == ""}} {{',
            f'    set lLib [DboFindLibrary "{part_name}.olb"]',
            "  }",
            f'  set lPart [DboCreatePart $lLib "{part_name}"]',
            f'  DboSetPartProp $lPart "PCB Footprint" '
            f'"{device.package_code.upper()}"',
            f'  DboSetPartProp $lPart "Part Number" "{part_name}"',
        ]

        x_right, x_left = 1000, -1000
        y_right, y_left = 0, 0
        y_step = 100

        for sec in sections:
            side = sec.side
            for cp in sec.pins:
                direction = _dir(cp)
                pin_name = _esc(cp.record.pin_name)
                ball = cp.record.ball_id
                if side == "right":
                    lines.append(
                        f'  DboCreatePin $lPart "{pin_name}" "{ball}" '
                        f'"Line" {direction} {x_right} {y_right} "RIGHT"'
                    )
                    y_right -= y_step
                elif side == "left":
                    lines.append(
                        f'  DboCreatePin $lPart "{pin_name}" "{ball}" '
                        f'"Line" {direction} {x_left} {y_left} "LEFT"'
                    )
                    y_left -= y_step

        spacing = 100

        bottom_pins = sorted(
            (cp for sec in sections if sec.side == "bottom" for cp in sec.pins),
            key=lambda p: p.record.ball_id,
        )
        if bottom_pins:
            x_start = -((len(bottom_pins) - 1) * spacing) // 2
            y_bottom = -max(abs(y_right), abs(y_left)) - 500
            for i, cp in enumerate(bottom_pins):
                direction = _dir(cp)
                pin_name = _esc(cp.record.pin_name)
                ball = cp.record.ball_id
                x = x_start + i * spacing
                lines.append(
                    f'  DboCreatePin $lPart "{pin_name}" "{ball}" '
                    f'"Line" {direction} {x} {y_bottom} "BOTTOM"'
                )

        top_pins = sorted(
            (cp for sec in sections if sec.side == "top" for cp in sec.pins),
            key=lambda p: p.record.ball_id,
        )
        if top_pins:
            x_start = -((len(top_pins) - 1) * spacing) // 2
            y_top = 500
            for i, cp in enumerate(top_pins):
                direction = _dir(cp)
                pin_name = _esc(cp.record.pin_name)
                ball = cp.record.ball_id
                x = x_start + i * spacing
                lines.append(
                    f'  DboCreatePin $lPart "{pin_name}" "{ball}" '
                    f'"Line" {direction} {x} {y_top} "TOP"'
                )

        lines.extend([
            "  DboSaveLibrary $lLib",
            '  puts "Done"',
            "}",
            "main",
        ])

        return {f"{part_name}_symbol.tcl": "\n".join(lines)}

    def generate_footprint(
        self,
        device: DevicePinout,
        spec: PackageSpec,
        coords: dict[str, tuple[float, float]],
    ) -> dict[str, str]:
        pkg_name = device.package_code.upper()
        padstack_name = f"BGA_{spec.pitch_mm:.2f}MM_{spec.pad_diameter_mm:.2f}MM"
        date_str = datetime.date.today().isoformat()

        lines = [
            f"; Allegro SKILL — {pkg_name}",
            f"; Generated {date_str}",
            "(defun polylibs_create_footprint ()",
            '  (setq dba (axlDBCreateSymbol '
            f'(list (quote name) "{pkg_name}" (quote type) "package")))',
            '  (unless dba (printf "Failed to create symbol\\n") (return nil))',
            f'  (setq padstackName "{padstack_name}")',
        ]

        for ball_id, (x, y) in sorted(coords.items()):
            lines.append(
                '  (axlDBCreatePin dba (list (quote name) padstackName '
                f'(quote type) "through" (quote xy) (list {x:.4f} {y:.4f}) '
                f'(quote number) "{ball_id}"))'
            )

        # Package outline
        hx = spec.body_size_x / 2.0
        hy = spec.body_size_y / 2.0
        ss_hx = hx + 0.5
        ss_hy = hy + 0.5
        pb_hx = hx + 1.0
        pb_hy = hy + 1.0

        lines.extend([
            '  (axlDBCreateShape dba (list '
            f'(list {-pb_hx:.2f} {-pb_hy:.2f}) '
            f'(list {pb_hx:.2f} {-pb_hy:.2f}) '
            f'(list {pb_hx:.2f} {pb_hy:.2f}) '
            f'(list {-pb_hx:.2f} {pb_hy:.2f})) '
            '"place_bound_top" "PACKAGE GEOMETRY")',
            '  (axlDBCreateShape dba (list '
            f'(list {-ss_hx:.2f} {-ss_hy:.2f}) '
            f'(list {ss_hx:.2f} {-ss_hy:.2f}) '
            f'(list {ss_hx:.2f} {ss_hy:.2f}) '
            f'(list {-ss_hx:.2f} {ss_hy:.2f})) '
            '"package_geometry" "SILKSCREEN_TOP")',
            '  (axlDBCreateShape dba (list '
            f'(list {-hx:.2f} {-hy:.2f}) '
            f'(list {hx:.2f} {-hy:.2f}) '
            f'(list {hx:.2f} {hy:.2f}) '
            f'(list {-hx:.2f} {hy:.2f})) '
            '"package_geometry" "ASSEMBLY_TOP")',
            '  t',
            ')',
            '(polylibs_create_footprint)',
        ])

        return {f"{pkg_name}.il": "\n".join(lines)}


def _esc(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$')


def _dir(cp: ClassifiedPin) -> str:
    d = cp.direction
    mapping = {
        "INPUT": '"Input"',
        "OUTPUT": '"Output"',
        "BIDIRECTIONAL": '"Bidirectional"',
        "POWER": '"Power"',
        "GROUND": '"Ground"',
        "PASSIVE": '"Passive"',
        "NC": '"Passive"',
    }
    return mapping.get(d.value, '"Passive"')
