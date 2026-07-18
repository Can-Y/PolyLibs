"""Tests for polylibs.generators."""

import re
from pathlib import Path
from polylibs.generators.base import Generator
from polylibs.parser import parse_csv, find_device_csv
from polylibs.classifier import classify_all, partition_for_symbol
from polylibs.geometry import get_package_spec, compute_ball_coordinates
from polylibs.generators.pads import PadsGenerator
from polylibs.generators.cadence import CadenceGenerator, _XML_BODY_COLOR
from polylibs.generators.symbol_sections import build_symbol_sections
from polylibs.generators.altium import AltiumGenerator
from polylibs.generators.kicad import KiCadGenerator


def test_generator_is_abstract():
    import inspect
    assert inspect.isabstract(Generator)


def test_pads_pin_type_mapping():
    from polylibs.generators.pads import _PADS_PIN_TYPE
    assert _PADS_PIN_TYPE["INPUT"] == "IN"
    assert _PADS_PIN_TYPE["OUTPUT"] == "OUT"
    assert _PADS_PIN_TYPE["BIDIRECTIONAL"] == "BI"
    assert _PADS_PIN_TYPE["POWER"] == "PWR"
    assert _PADS_PIN_TYPE["GROUND"] == "GND"


def test_pads_generator_outputs(data_dirs: list[Path]):
    path = find_device_csv("xc7a100tfgg484", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    spec = get_package_spec(device.package_code, ball_count=device.total_pins)
    coords = compute_ball_coordinates(device.pins, spec)

    gen = PadsGenerator()
    symbol_files = gen.generate_symbol(device, classified, spec)
    footprint_files = gen.generate_footprint(device, spec, coords)

    assert any("part" in k.lower() for k in symbol_files)
    assert any("decal" in k.lower() or ".dec" in k.lower() for k in footprint_files)

    # All ball IDs appear in the decal
    decal_content = next(v for k, v in footprint_files.items() if ".dec" in k.lower())
    for ball_id in coords:
        assert ball_id in decal_content


def test_cadence_generator_outputs(data_dirs: list[Path]):
    path = find_device_csv("xc7a100tfgg484", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    spec = get_package_spec(device.package_code, ball_count=device.total_pins)
    coords = compute_ball_coordinates(device.pins, spec)

    gen = CadenceGenerator()
    symbol_files = gen.generate_symbol(device, classified, spec)
    footprint_files = gen.generate_footprint(device, spec, coords)

    import xml.etree.ElementTree as ET

    assert any(k.endswith("_library.xml") for k in symbol_files)
    assert any(k.endswith(".il") for k in footprint_files)

    xml_text = next(v for k, v in symbol_files.items() if k.endswith("_library.xml"))
    root = ET.fromstring(xml_text)
    assert root.tag == "Lib"
    package = root.find("Package")
    assert package is not None
    lib_parts = package.findall("LibPart")
    units = build_symbol_sections(classified)
    assert len(lib_parts) == len(units)
    assert len(lib_parts) > 1  # FGG484 splits into several bank/power units
    assert package.find("Defn").get("isHomogeneous") == "0"
    # alphabeticNumbering="2" makes Capture reject multi-unit imports
    # (ORDBDLL-1025 "A Cell with this name already exists", SPB 17.2 verified)
    assert package.find("Defn").get("alphabeticNumbering") == "1"
    total = 0
    for lib_part, unit in zip(lib_parts, units):
        normal = lib_part.find("NormalView")
        assert normal is not None
        assert normal.find("Defn").get("suffix") == ".Normal"
        pins = normal.findall("SymbolPinScalar")
        assert len(pins) == len(unit.pins)
        total += len(pins)
        positions = [int(p.find("Defn").get("position")) for p in pins]
        assert positions == list(range(len(pins)))
        rect = normal.find("Rect")
        assert rect is not None
        assert rect.find("Defn").get("fillStyle") == "1"
        color = normal.find("SymbolColor/Defn")
        assert color is not None and color.get("val") == str(_XML_BODY_COLOR)
        physical = lib_part.find("PhysicalPart")
        assert physical is not None
        numbers = [d.get("number") for d in physical.findall("PinNumber/Defn")]
        assert sorted(numbers) == sorted(cp.record.ball_id for cp in unit.pins)
    assert total == device.total_pins

    il = next(v for k, v in footprint_files.items() if k.endswith(".il"))
    assert "axlDBCreatePin" in il

    # --- SKILL footprint structure (Task 1) ---
    assert "axlDBCreatePadStack" in il
    assert "through" not in il.lower()
    assert "axlDBCreateSymbol" not in il
    assert "millimeters" in il
    assert il.count("axlDBCreatePin") == len(coords)
    for layer in ("PLACE_BOUND_TOP", "SILKSCREEN_TOP", "ASSEMBLY_TOP"):
        assert f'"PACKAGE GEOMETRY/{layer}"' in il
    assert "axlDBCreateCircle" in il  # A1 pin-1 marker
    assert '"REF DES/SILKSCREEN_TOP"' in il
    # SKILL let binds a bare symbol list, not CL-style ((vars)) — SPB 17.2
    # rejects the latter with "illegal binding form".
    assert "(let (padTop padMask padPaste ps)" in il
    assert "(let ((" not in il
    # per-step failure reporting (spec §5): 3 rects + A1 circle + REF* text
    assert il.count("ERROR: create") == 5
    # hard guard: pins require a symbol editor (axlDBCreatePin is .dra-only)
    assert '(axlDesignType nil) "SYMBOL"' in il
    for ball_id in coords:
        assert f'?number "{ball_id}"' in il


def test_cadence_symbol_vcco_psio_unit(data_dirs: list[Path]):
    """All VCCO_PS* pins (PSIO + PSDDR) share one dedicated power unit."""
    path = find_device_csv("xczu1egubva494", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    units = build_symbol_sections(classified)

    psio_units = [u for u in units if u.name == "Power: VCCO_PSIO"]
    assert len(psio_units) == 1
    names = sorted(cp.record.pin_name for cp in psio_units[0].pins)
    assert names == sorted([
        "VCCO_PSIO0_500", "VCCO_PSIO0_500",
        "VCCO_PSIO1_501", "VCCO_PSIO1_501",
        "VCCO_PSIO2_502", "VCCO_PSIO2_502",
        "VCCO_PSIO3_503", "VCCO_PSIO3_503",
        "VCCO_PSDDR_504", "VCCO_PSDDR_504",
        "VCCO_PSDDR_504", "VCCO_PSDDR_504",
        "VCCO_PSDDR_504",
    ])
    for u in units:
        if u.name != "Power: VCCO_PSIO":
            assert all(not cp.record.pin_name.startswith("VCCO_PS") for cp in u.pins)
    bank500 = next(u for u in units if u.name == "Bank 500")
    assert any(cp.record.pin_name.startswith("PS_MIO") for cp in bank500.pins)
    assert sum(len(u.pins) for u in units) == device.total_pins


def test_cadence_symbol_ddr_split(data_dirs: list[Path]):
    """Bank 504 DDR pins are split into ADDR+CTRL and DATA units."""
    path = find_device_csv("xczu1egubva494", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    units = build_symbol_sections(classified)

    addr_ctrl = next(u for u in units if u.name == "Bank 504 ADDR+CTRL")
    data = next(u for u in units if u.name == "Bank 504 DATA")

    data_names = {cp.record.pin_name for cp in data.pins}
    addr_names = {cp.record.pin_name for cp in addr_ctrl.pins}

    assert all(n.startswith(("PS_DDR_DQ", "PS_DDR_DM", "PS_DDR_DQS_")) for n in data_names)
    assert not any(n.startswith(("PS_DDR_DQ", "PS_DDR_DM", "PS_DDR_DQS_")) for n in addr_names)
    assert all(n.startswith("PS_DDR_") for n in addr_names)
    assert not any(cp.record.pin_name.startswith("VCCO_PSDDR") for cp in data.pins)
    assert not any(cp.record.pin_name.startswith("VCCO_PSDDR") for cp in addr_ctrl.pins)
    assert sum(len(u.pins) for u in units) == device.total_pins


def test_cadence_symbol_mgt_pn_adjacency(data_dirs: list[Path]):
    """Bank 505 PS MGT differential pairs keep P and N adjacent."""
    path = find_device_csv("xczu1egubva494", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    units = build_symbol_sections(classified)

    bank505 = next(u for u in units if u.name == "MGT Bank 505")
    names = [cp.record.pin_name for cp in bank505.pins]

    def pair_name(n: str) -> str:
        return n[:-1] + ("N" if n[-1].upper() == "P" else "P")

    for i, n in enumerate(names):
        if n[-1].upper() in "PN":
            pn = pair_name(n)
            if i + 1 < len(names):
                assert names[i + 1] == pn, f"{n} at index {i} not followed by {pn}"
            else:
                # last pin cannot be the P of a pair without its N following
                assert n[-1].upper() != "P", f"{n} is a P without trailing N"
    assert sum(len(u.pins) for u in units) == device.total_pins


def test_altium_generator_outputs(data_dirs: list[Path]):
    path = find_device_csv("xc7a100tfgg484", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    spec = get_package_spec(device.package_code, ball_count=device.total_pins)
    coords = compute_ball_coordinates(device.pins, spec)

    gen = AltiumGenerator()
    symbol_files = gen.generate_symbol(device, classified, spec)
    footprint_files = gen.generate_footprint(device, spec, coords)

    assert len(symbol_files) >= 1
    assert len(footprint_files) >= 1

    content = "\n".join(symbol_files.values())
    assert device.full_name.upper() in content.upper()
    assert "Pin Designator" in content
    assert "Pin Name" in content
    assert "Pin Type" in content


    # Verify at least one known pin appears in the CSV-style output.
    assert device.pins[0].ball_id in content
    assert device.pins[0].pin_name in content


def test_kicad_generator_outputs(data_dirs: list[Path]):
    path = find_device_csv("xc7a100tfgg484", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    spec = get_package_spec(device.package_code, ball_count=device.total_pins)
    coords = compute_ball_coordinates(device.pins, spec)

    gen = KiCadGenerator()
    symbol_files = gen.generate_symbol(device, classified, spec)
    footprint_files = gen.generate_footprint(device, spec, coords)

    # Footprint
    assert any(k.endswith(".kicad_mod") for k in footprint_files)
    mod = next(v for k, v in footprint_files.items() if k.endswith(".kicad_mod"))
    assert mod.startswith('(footprint "')
    assert '(attr smd)' in mod
    assert '(layer "F.Cu")' in mod
    for ball_id in coords:
        assert f'"{ball_id}"' in mod

    # Symbol - now split into multiple independent symbols (one per bank/group).
    assert any(k.endswith(".kicad_sym") for k in symbol_files)
    sym = next(v for k, v in symbol_files.items() if k.endswith(".kicad_sym"))
    assert sym.startswith('(kicad_symbol_lib')
    assert sym.count('(symbol "') >= 2  # multiple independent symbols
    assert device.pins[0].ball_id in sym
    assert device.pins[0].pin_name in sym

    # All pins in each unit should be on the left side (top-to-bottom on one side).
    for unit_match in re.finditer(r'\(symbol "([^"]+_0_1)"', sym):
        start = unit_match.start()
        depth = 0
        end = start
        for i in range(start, len(sym)):
            if sym[i] == '(':
                depth += 1
            elif sym[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        block = sym[start:end]
        left_pins = re.findall(r'\(pin \w+ line \(at -\d+\.\d+ ', block)
        right_pins = re.findall(r'\(pin \w+ line \(at \d+\.\d+ \d+\.\d+ 180\)', block)
        if left_pins or right_pins:
            assert len(right_pins) == 0, f"Found {len(right_pins)} right-side pins in {unit_match.group(1)}"
