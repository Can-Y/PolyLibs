"""Tests for polylibs.generators."""

import re
from pathlib import Path
from polylibs.generators.base import Generator
from polylibs.parser import parse_csv, find_device_csv
from polylibs.classifier import classify_all, partition_for_symbol
from polylibs.geometry import get_package_spec, compute_ball_coordinates
from polylibs.generators.pads import PadsGenerator
from polylibs.generators.cadence import CadenceGenerator
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

    assert any(k.endswith(".tcl") for k in symbol_files)
    assert any(k.endswith(".il") for k in footprint_files)

    tcl = next(v for k, v in symbol_files.items() if k.endswith(".tcl"))
    assert "DboCreatePin" in tcl or "Part" in tcl

    il = next(v for k, v in footprint_files.items() if k.endswith(".il"))
    assert "axlDBCreatePin" in il


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
