"""Tests for the shared symbol section logic."""

from polylibs.parser import find_device_csv, parse_csv
from polylibs.classifier import classify_all
from polylibs.generators.symbol_sections import build_symbol_sections


def test_xczu1egubva494_unit_count_and_totals(data_dirs):
    path = find_device_csv("xczu1egubva494", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    units = build_symbol_sections(classified)

    assert len(units) == 23
    assert sum(len(u.pins) for u in units) == device.total_pins


def test_xczu1egubva494_vcco_psio_consolidated(data_dirs):
    path = find_device_csv("xczu1egubva494", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    units = build_symbol_sections(classified)

    psio_units = [u for u in units if u.name == "Power: VCCO_PSIO"]
    assert len(psio_units) == 1
    psio_names = {cp.record.pin_name for cp in psio_units[0].pins}
    assert all(n.startswith("VCCO_PS") for n in psio_names)
    for u in units:
        if u.name != "Power: VCCO_PSIO":
            assert all(not cp.record.pin_name.startswith("VCCO_PS") for cp in u.pins)


def test_xczu1egubva494_bank504_ddr_split(data_dirs):
    path = find_device_csv("xczu1egubva494", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    units = build_symbol_sections(classified)

    addr_ctrl = next(u for u in units if u.name == "Bank 504 ADDR+CTRL")
    data = next(u for u in units if u.name == "Bank 504 DATA")

    assert all(
        n.startswith("PS_DDR_") for n in (cp.record.pin_name for cp in addr_ctrl.pins)
    )
    assert not any(
        n.startswith(("PS_DDR_DQ", "PS_DDR_DM", "PS_DDR_DQS_"))
        for n in (cp.record.pin_name for cp in addr_ctrl.pins)
    )
    assert all(
        n.startswith(("PS_DDR_DQ", "PS_DDR_DM", "PS_DDR_DQS_"))
        for n in (cp.record.pin_name for cp in data.pins)
    )


def test_xczu1egubva494_bank505_pn_adjacency(data_dirs):
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
                assert n[-1].upper() != "P", f"{n} is a P without trailing N"


def test_xc7a100tfgg484_splits_into_multiple_units(data_dirs):
    path = find_device_csv("xc7a100tfgg484", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    units = build_symbol_sections(classified)

    assert len(units) > 1
    assert sum(len(u.pins) for u in units) == device.total_pins


def test_xc2ve3558ssva2397_totals_and_no_signal_duplicates(data_dirs):
    """Versal device: power/ground classification must keep duplicate names out of signal units."""
    path = find_device_csv("xc2ve3558ssva2397", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    units = build_symbol_sections(classified)

    assert sum(len(u.pins) for u in units) == device.total_pins
    for u in units:
        if u.name.startswith(("Power", "Ground", "No Connect")):
            continue
        names = [cp.record.pin_name for cp in u.pins]
        assert len(names) == len(set(names)), f"duplicate names in {u.name}: {names}"


def test_xc2ve3558ssva2397_mgt_pairs_adjacent_when_present(data_dirs):
    """Versal GTYP lanes keep P/N adjacent when both exist in the same unit."""
    path = find_device_csv("xc2ve3558ssva2397", data_dirs)
    device = parse_csv(path)
    classified = classify_all(device.pins)
    units = build_symbol_sections(classified)

    def complement(n: str) -> str:
        return n[:-1] + ("N" if n[-1].upper() == "P" else "P")

    for u in units:
        if not u.name.startswith("MGT Bank"):
            continue
        names = [cp.record.pin_name for cp in u.pins]
        name_set = set(names)
        for i, n in enumerate(names):
            if n[-1].upper() in "PN" and complement(n) in name_set:
                assert names[i + 1] == complement(n), f"{n} in {u.name} not adjacent to its pair"
