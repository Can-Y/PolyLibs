"""Static checks for generated Cadence scripts (no Cadence required)."""

import hashlib
from pathlib import Path

from polylibs.parser import parse_csv, find_device_csv
from polylibs.geometry import get_package_spec, compute_ball_coordinates
from polylibs.generators.cadence import CadenceGenerator, _padstack_name


def assert_balanced(text: str) -> None:
    """SKILL/TCL bracket & quote balance check (string-aware)."""
    parens = 0
    in_str = False
    esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "(":
                parens += 1
            elif ch == ")":
                parens -= 1
            assert parens >= 0, "unbalanced closing paren"
    assert parens == 0, f"unbalanced parens: {parens}"
    assert not in_str, "unterminated string"


def _footprint_il(data_dirs: list[Path]) -> str:
    path = find_device_csv("xc7a100tfgg484", data_dirs)
    device = parse_csv(path)
    spec = get_package_spec(device.package_code, ball_count=device.total_pins)
    coords = compute_ball_coordinates(device.pins, spec)
    fp = CadenceGenerator().generate_footprint(device, spec, coords)
    return next(iter(fp.values()))


def test_skill_balance(data_dirs: list[Path]):
    assert_balanced(_footprint_il(data_dirs))


def test_footprint_deterministic(data_dirs: list[Path]):
    assert _footprint_il(data_dirs) == _footprint_il(data_dirs)


# Golden hash: filled in during Task 2 Step 3 from actual output.
GOLDEN_FGG484_IL_SHA256 = "2a4b235cebbc1acff47eccc07db2d3cc61a6d37b156aeebcf495c856548dc244"


def test_footprint_golden(data_dirs: list[Path]):
    digest = hashlib.sha256(_footprint_il(data_dirs).encode()).hexdigest()
    assert digest == GOLDEN_FGG484_IL_SHA256


def _symbol_xml(data_dirs: list[Path]) -> str:
    from polylibs.classifier import classify_all
    path = find_device_csv("xc7a100tfgg484", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    spec = get_package_spec(device.package_code, ball_count=device.total_pins)
    sym = CadenceGenerator().generate_symbol(device, classified, spec)
    return next(iter(sym.values()))


def test_symbol_xml_wellformed(data_dirs: list[Path]):
    import xml.etree.ElementTree as ET
    ET.fromstring(_symbol_xml(data_dirs))


GOLDEN_FGG484_XML_SHA256 = "ffedac4d98f3585e6e41ea7e7183dc87fed1b8c87d4e36957cba61f110ffb4af"


def test_symbol_golden(data_dirs: list[Path]):
    digest = hashlib.sha256(_symbol_xml(data_dirs).encode()).hexdigest()
    assert digest == GOLDEN_FGG484_XML_SHA256
