"""Tests for polylibs.classifier."""

import re

from polylibs.models import PinRecord, Family, PinType, PinDirection
from polylibs.classifier import (
    classify_pin,
    classify_all,
    partition_for_symbol,
    ClassificationRules,
    classify_with_rules,
)


def _pin(name: str, bank: str = "NA", io_type: str = "NA") -> PinRecord:
    return PinRecord(
        ball_id="A1",
        pin_name=name,
        bank=bank,
        io_type=io_type,
        family=Family.SERIES_7,
    )


def test_classify_vccint():
    cp = classify_pin(_pin("VCCINT"))
    assert cp.pin_type == PinType.POWER
    assert cp.direction == PinDirection.POWER
    assert cp.rail_name == "VCCINT"


def test_classify_gnd():
    cp = classify_pin(_pin("GND"))
    assert cp.pin_type == PinType.GROUND
    assert cp.direction == PinDirection.GROUND


def test_classify_rsvdgnd():
    cp = classify_pin(_pin("RSVDGND"))
    assert cp.pin_type == PinType.GROUND
    assert cp.direction == PinDirection.GROUND


def test_classify_nc_rsvd():
    cp = classify_pin(_pin("RSVD"))
    assert cp.pin_type == PinType.NO_CONNECT
    assert cp.direction == PinDirection.NC


def test_classify_io():
    cp = classify_pin(_pin("IO_L1P_T0_13", bank="13", io_type="HR"))
    assert cp.pin_type == PinType.IO
    assert cp.direction == PinDirection.BIDIR
    assert cp.section_name == "Bank 13"


def test_classify_config():
    cp = classify_pin(_pin("TCK"))
    assert cp.pin_type == PinType.CONFIG
    assert cp.direction == PinDirection.INPUT


def test_classify_mgt():
    cp = classify_pin(_pin("MGTREFCLK0P_112"))
    assert cp.pin_type == PinType.MGT


def test_classify_nc():
    cp = classify_pin(_pin("NC"))
    assert cp.pin_type == PinType.NO_CONNECT


def test_partition_groups():
    pins = [
        classify_pin(_pin("VCCINT")),
        classify_pin(_pin("GND")),
        classify_pin(_pin("IO_L1P_T0_13", bank="13")),
        classify_pin(_pin("TCK")),
    ]
    sections = partition_for_symbol(pins)
    names = {s.name for s in sections}
    assert "Power: VCCINT" in names
    assert "Ground" in names
    assert "Bank 13" in names
    assert "Configuration" in names


def test_rule_classifier_power_and_io():
    rules = ClassificationRules(
        power_patterns=[(re.compile(r"^VCC$"), "VCCINT")],
        ground_patterns=[re.compile(r"^GND$")],
        config_patterns=[],
        mgt_patterns=[],
        analog_patterns=[],
        nc_patterns=[],
        direction_rules=[{"default": "BIDIRECTIONAL"}],
    )
    pwr = PinRecord(
        ball_id="A1",
        pin_name="VCC",
        bank="0",
        io_type="POWER",
        family=Family.GENERIC,
    )
    io = PinRecord(
        ball_id="A2",
        pin_name="IO_1",
        bank="1",
        io_type="LVCMOS",
        family=Family.GENERIC,
    )
    assert classify_with_rules(pwr, rules).pin_type == PinType.POWER
    assert classify_with_rules(io, rules).pin_type == PinType.IO
