"""Cadence Allegro SKILL footprint and OrCAD Library XML symbol generator."""

from xml.sax.saxutils import escape as _sax_escape

from ..models import DevicePinout, PackageSpec, ClassifiedPin, SymbolSection
from .base import Generator
from .symbol_sections import build_symbol_sections


def _xml_escape(s: str) -> str:
    """Escape for XML attribute values (quotes included)."""
    return _sax_escape(s, {'"': '&quot;'})


def _padstack_name(spec: PackageSpec) -> str:
    """SMD circular padstack name encoding the pad diameter, e.g. SMDC025."""
    return f"SMDC{round(spec.pad_diameter_mm * 100):03d}"


# SKILL defun body inside an (implicit) progn construct is limited to 32767
# characters.  A single axlDBCreatePin line averages ~90 chars; batch each
# helper function to stay comfortably under the limit.
_SKILL_CONSTRUCT_LIMIT = 32767


def _pin_batch_size(padstack: str, sample_ball: str) -> int:
    """Return the max pins per batch helper, calibrated from one sample line."""
    sample = (
        f'  (axlDBCreatePin "{padstack}" 0.0000:0.0000'
        f' (make_axlPinText ?number "{sample_ball}" ?offset 0:0 ?text "1"))'
    )
    # Allow ~500 chars for longer ball-ids plus the defun wrapper.
    per_pin = len(sample) + 20
    return max(1, (_SKILL_CONSTRUCT_LIMIT - 500) // per_pin)


# SymbolPinScalar Defn@type, calibrated from a real SPB 17.2 export of
# Amplifier.olb (see docs/superpowers/specs/2026-07-16-cadence-generator-design.md §4.3).
_XML_PIN_TYPE = {
    "INPUT": 0,
    "BIDIRECTIONAL": 1,
    "OUTPUT": 2,
    "PASSIVE": 4,
    "NC": 4,
    "POWER": 7,
    "GROUND": 7,
}

# Constant child elements of a scalar symbol pin (mirrors the SPB 17.2 sample).
_XML_PIN_CHILDREN = (
    "          <IsLong><Defn val=\"1\"/></IsLong>\n"
    "          <IsClock><Defn val=\"0\"/></IsClock>\n"
    "          <IsDot><Defn val=\"0\"/></IsDot>\n"
    "          <IsLeftPointing><Defn val=\"0\"/></IsLeftPointing>\n"
    "          <IsRightPointing><Defn val=\"0\"/></IsRightPointing>\n"
    "          <IsNetStyle><Defn val=\"0\"/></IsNetStyle>\n"
    "          <IsNoConnect><Defn val=\"0\"/></IsNoConnect>\n"
    "          <IsGlobal><Defn val=\"0\"/></IsGlobal>\n"
    "          <IsNumberVisible><Defn val=\"1\"/></IsNumberVisible>"
)

# Capture grid: 1 unit = 0.01 inch (sample: pin length 30, pin pitch 10).
_XML_PITCH = 10
_XML_PIN_LEN = 30
_XML_BODY_W = 100

# Symbol body color (Capture palette index; 48 = factory default blue).
_XML_BODY_COLOR = 48


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
        part_name = device.full_name.upper()
        # Filter out NC pins — they don't need symbol representation.
        # Use natural partitioning (no unit-count compression).  Keeping each
        # unit within 64 pins avoids the ORDBDLL-1025 import failures seen on
        # large devices such as xc2ve3558ssva2397 when units were compressed to
        # 128 pins to meet a 25-unit target.
        active_pins = [p for p in pins if p.direction.value != "NC"]
        units = build_symbol_sections(active_pins)
        return {f"{part_name}_library.xml": self._symbol_xml(device, units)}

    def _symbol_xml(self, device: DevicePinout, units: list[SymbolSection]) -> str:
        """OrCAD Capture Library XML (schema: capture/tclscripts/capDB/olb.xsd).

        One LibPart per unit (heterogeneous package), mirroring the KiCad
        generator's sectioning. Structure verified on SPB 17.2 against a
        hand-built 2-unit heterogeneous part and an Amplifier.olb export.
        """
        part = _xml_escape(device.full_name.upper())
        package = _xml_escape(device.package_code.upper())
        homogeneous = "1" if len(units) == 1 else "0"
        # Alphabetic unit suffixes (A, B, C...) only fit 26 units; switch to
        # numeric (1, 2, 3...) for larger heterogeneous parts.
        alphabetic_numbering = "1" if len(units) <= 26 else "0"
        parts_text = "\n".join(self._unit_xml(part, unit) for unit in units)

        return f'''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<Lib xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="D:/Cadence/SPB_17.2/tools/capture/tclscripts/capDB/olb.xsd">

  <Defn name="{part}_library"/>

  <Package>
    <Defn alphabeticNumbering="{alphabetic_numbering}" isHomogeneous="{homogeneous}" name="{part}" pcbFootprint="{package}" pcbLib="" refdesPrefix="U"/>
{parts_text}
  </Package>

</Lib>
'''

    def _unit_xml(self, part: str, unit: SymbolSection) -> str:
        """One LibPart (unit): body rect, all pins on the left, pin numbers."""
        pins = unit.pins
        n = len(pins)
        # one row above the pins reserved for the section-name label
        body_h = (max(n, 1) + 2) * _XML_PITCH
        max_name = max((len(cp.record.pin_name) for cp in pins), default=0)
        body_w = max(_XML_BODY_W, max_name * 8 + 20)
        body_w = ((body_w + _XML_PITCH - 1) // _XML_PITCH) * _XML_PITCH
        x1, x2 = 0, body_w
        y1, y2 = 0, body_h
        section_name = _xml_escape(unit.name)

        pin_blocks = []
        pin_numbers = []
        for i, cp in enumerate(pins):
            sy = y2 - (i + 2) * _XML_PITCH
            name = _xml_escape(cp.record.pin_name)
            ptype = _XML_PIN_TYPE.get(cp.direction.value, 4)
            pin_blocks.append(
                "        <SymbolPinScalar>\n"
                f'          <Defn hotptX="{-_XML_PIN_LEN}" hotptY="{sy}"'
                f' name="{name}" position="{i}"'
                f' startX="0" startY="{sy}" type="{ptype}" visible="1"/>\n'
                f"{_XML_PIN_CHILDREN}\n"
                "        </SymbolPinScalar>"
            )
            pin_numbers.append(
                "        <PinNumber>\n"
                f'          <Defn number="{_xml_escape(cp.record.ball_id)}"'
                f' position="{i}"/>\n'
                "        </PinNumber>"
            )

        pins_text = "\n".join(pin_blocks)
        numbers_text = "\n".join(pin_numbers)

        return f'''    <LibPart>
      <Defn/>
      <NormalView>
        <Defn suffix=".Normal"/>
        <SymbolColor>
          <Defn val="{_XML_BODY_COLOR}"/>
        </SymbolColor>
        <SymbolBBox>
          <Defn x1="{x1}" x2="{x2}" y1="{y1}" y2="{y2}"/>
        </SymbolBBox>
        <IsPinNumbersVisible>
          <Defn val="1"/>
        </IsPinNumbersVisible>
        <IsPinNamesVisible>
          <Defn val="1"/>
        </IsPinNamesVisible>
        <PartValue>
          <Defn name="{part}"/>
        </PartValue>
        <Reference>
          <Defn name="U"/>
        </Reference>
        <Rect>
          <Defn fillStyle="1" hatchStyle="0" lineStyle="0" lineWidth="0" x1="{x1}" x2="{x2}" y1="{y1}" y2="{y2}"/>
        </Rect>
        <CommentText>
          <Defn locX="5" locY="{y2 - 10}" name="{section_name}" textJustification="0" x1="5" x2="{x2 - 5}" y1="{y2 - 10}" y2="{y2}"/>
          <TextFont>
            <Defn escapement="0" height="-9" italic="0" name="Arial" orientation="0" weight="400" width="4"/>
          </TextFont>
        </CommentText>
{pins_text}
      </NormalView>
      <PhysicalPart>
        <Defn/>
{numbers_text}
      </PhysicalPart>
    </LibPart>'''

    def generate_footprint(
        self,
        device: DevicePinout,
        spec: PackageSpec,
        coords: dict[str, tuple[float, float]],
    ) -> dict[str, str]:
        if not coords:
            raise ValueError("coords is empty; nothing to generate")
        for field_name, value in (
            ("pad_diameter_mm", spec.pad_diameter_mm),
            ("body_size_x", spec.body_size_x),
            ("body_size_y", spec.body_size_y),
        ):
            if value <= 0:
                raise ValueError(f"invalid PackageSpec.{field_name}: {value}")

        pkg_name = device.package_code.upper()
        padstack = _padstack_name(spec)
        pad = spec.pad_diameter_mm
        mask = spec.mask_opening_mm
        paste = spec.paste_diameter_mm

        sorted_pins = sorted(coords.items())
        batch_n = _pin_batch_size(padstack, sorted_pins[0][0])

        # Split pins into batches; each batch becomes a tiny defun.
        batches: list[list[tuple[str, tuple[float, float]]]] = []
        for i in range(0, len(sorted_pins), batch_n):
            batches.append(sorted_pins[i : i + batch_n])

        lines = [
            f"; Allegro SKILL footprint builder — {pkg_name}",
            "; Generated by PolyLibs. Run inside an open Package Symbol (.dra)",
            "; editing session:  skill load(\"<this file>\")",
        ]

        # Emit one batch helper per chunk so no single construct exceeds the
        # 32767-char SKILL limit.
        batch_func_names: list[str] = []
        for idx, batch in enumerate(batches):
            fname = f"polylibs_pins_{idx + 1}"
            batch_func_names.append(fname)
            lines.append(f"(defun {fname} ()")
            for ball_id, (x, y) in batch:
                lines.append(
                    f'  (axlDBCreatePin "{padstack}" {x:.4f}:{y:.4f}'
                    f' (make_axlPinText ?number "{ball_id}" ?offset 0:0 ?text "1"))'
                )
            lines.append("  t")
            lines.append(")")

        # Main entry point — calls all batch helpers then draws outlines.
        lines.extend([
            "",
            "(defun polylibs_build ()",
            '  (unless (equal (axlDesignType nil) "SYMBOL")',
            '    (error "not a symbol drawing (.dra) - use File > New, Drawing Type: Package symbol"))',
            '  (axlDBChangeDesignUnits "millimeters" 4)',
            "",
            "  ; --- padstack (skip silently if it already exists) ---",
            "  (let (padTop padMask padPaste ps)",
            '    (setq padTop (make_axlPadStackPad ?layer "TOP"',
            "      ?type (quote REGULAR) ?figure (quote CIRCLE)",
            f"      ?figureSize {pad:.4f}:{pad:.4f}))",
            '    (setq padMask (make_axlPadStackPad ?layer "SOLDERMASK_TOP"',
            "      ?type (quote REGULAR) ?figure (quote CIRCLE)",
            f"      ?figureSize {mask:.4f}:{mask:.4f}))",
            '    (setq padPaste (make_axlPadStackPad ?layer "PASTEMASK_TOP"',
            "      ?type (quote REGULAR) ?figure (quote CIRCLE)",
            f"      ?figureSize {paste:.4f}:{paste:.4f}))",
            f'    (setq ps (axlDBCreatePadStack "{padstack}" nil',
            "      (list padTop padMask padPaste) t))",
            f'    (unless ps (printf "WARN: padstack {padstack} not created',
            '      (already exists?)\\n"))',
            "  )",
            "",
            "  ; --- pins (batched) ---",
        ])

        for fname in batch_func_names:
            lines.append(f"  ({fname})")

        hx = spec.body_size_x / 2.0
        hy = spec.body_size_y / 2.0
        ss_hx = hx + 0.5
        ss_hy = hy + 0.5
        pb_hx = hx + 1.0
        pb_hy = hy + 1.0

        lines.extend([
            "",
            "  ; --- outlines ---",
            f"  (unless (axlDBCreateRectangle (list {-pb_hx:.4f}:{-pb_hy:.4f}"
            f' {pb_hx:.4f}:{pb_hy:.4f}) t "PACKAGE GEOMETRY/PLACE_BOUND_TOP")',
            '    (printf "ERROR: create PLACE_BOUND_TOP failed\\n"))',
            f"  (unless (axlDBCreateRectangle (list {-ss_hx:.4f}:{-ss_hy:.4f}"
            f' {ss_hx:.4f}:{ss_hy:.4f}) nil "PACKAGE GEOMETRY/SILKSCREEN_TOP")',
            '    (printf "ERROR: create SILKSCREEN_TOP failed\\n"))',
            f"  (unless (axlDBCreateRectangle (list {-hx:.4f}:{-hy:.4f}"
            f' {hx:.4f}:{hy:.4f}) nil "PACKAGE GEOMETRY/ASSEMBLY_TOP")',
            '    (printf "ERROR: create ASSEMBLY_TOP failed\\n"))',
            "",
            "  ; --- pin-1 marker + refdes ---",
        ])

        # Find the corner ball (top-left = max Y, min X) for the pin-1 marker.
        # Some packages skip A1 numbering; use geometry, not the name.
        pin1_ball_id = max(coords.keys(), key=lambda bid: (coords[bid][1], -coords[bid][0]))
        ax, ay = coords[pin1_ball_id]
        lines.append(
            f"  (unless (axlDBCreateCircle (list {ax:.4f}:{ay:.4f} 0.25)"
            f' 0.10 "PACKAGE GEOMETRY/SILKSCREEN_TOP")'
        )
        lines.append(
            '    (printf "ERROR: create A1 marker failed\\n"))'
        )
        lines.extend([
            f'  (unless (axlDBCreateText "REF*" 0.0:{ss_hy + 0.5:.4f}',
            '    (make_axlTextOrientation ?textBlock "1" ?rotation 0.0'
            ' ?mirrored nil ?justify "left") "REF DES/SILKSCREEN_TOP")',
            '    (printf "ERROR: create REF* text failed\\n"))',
            "  t",
            ")",
            "(polylibs_build)",
        ])
        return {f"{pkg_name}.il": "\n".join(lines)}
