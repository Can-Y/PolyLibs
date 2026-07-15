"""Altium Designer ASCII generator.

V1 outputs a CSV-style component import file for schematic symbols and an
ASCII land-pattern file for PCB footprints. These can be imported into
Altium without requiring the Altium API.
"""

from ..models import DevicePinout, PackageSpec, ClassifiedPin
from ..classifier import partition_for_symbol
from .base import Generator


class AltiumGenerator(Generator):
    @property
    def name(self) -> str:
        return "Altium"

    def generate_symbol(
        self,
        device: DevicePinout,
        pins: list[ClassifiedPin],
        spec: PackageSpec,
    ) -> dict[str, str]:
        sections = partition_for_symbol(pins)
        part_name = device.full_name

        lines = [
            "Comment,Designator,Footprint,Pin Designator,Pin Name,Pin Type,Section",
            f"{part_name},U,{device.package_code.upper()},,,,",
        ]

        for sec in sections:
            for cp in sec.pins:
                lines.append(
                    f",,,{cp.record.ball_id},{cp.record.pin_name},{cp.direction.value},{sec.name}"
                )

        return {f"{part_name}_altium_pins.csv": "\n".join(lines)}

    def generate_footprint(
        self,
        device: DevicePinout,
        spec: PackageSpec,
        coords: dict[str, tuple[float, float]],
    ) -> dict[str, str]:
        pkg_name = device.package_code.upper()
        pad_name = f"BGA_{spec.pitch_mm:.2f}MM_{spec.pad_diameter_mm:.2f}MM"

        lines = [
            "|RECORD=2|KIND=2|",  # footprint header placeholder
            f"|FOOTPRINT={pkg_name}|",
            "",
            "; Pads",
        ]

        for ball_id, (x, y) in sorted(coords.items()):
            lines.append(f"|RECORD=12|PADNAME={ball_id}|X={x:.4f}|Y={y:.4f}|PADSTACK={pad_name}|")

        lines.append("")
        lines.append("; Silkscreen outline")
        hx = spec.body_size_x / 2.0 + 0.5
        hy = spec.body_size_y / 2.0 + 0.5
        lines.append(f"|RECORD=27|X1={-hx:.2f}|Y1={-hy:.2f}|X2={hx:.2f}|Y2={-hy:.2f}|WIDTH=0.15|")
        lines.append(f"|RECORD=27|X1={hx:.2f}|Y1={-hy:.2f}|X2={hx:.2f}|Y2={hy:.2f}|WIDTH=0.15|")
        lines.append(f"|RECORD=27|X1={hx:.2f}|Y1={hy:.2f}|X2={-hx:.2f}|Y2={hy:.2f}|WIDTH=0.15|")
        lines.append(f"|RECORD=27|X1={-hx:.2f}|Y1={hy:.2f}|X2={-hx:.2f}|Y2={-hy:.2f}|WIDTH=0.15|")

        return {f"{pkg_name}_altium.txt": "\n".join(lines)}
