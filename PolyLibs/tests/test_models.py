"""Tests for polylibs.models."""

from polylibs.models import (
    Family,
    PinRecord,
    DevicePinout,
    PackageSpec,
    ClassifiedPin,
    SymbolSection,
    PinType,
    PinDirection,
)


def test_family_enum():
    assert Family.SERIES_7.name == "SERIES_7"
    assert Family.ULTRASCALE.name == "ULTRASCALE"
    assert Family.ULTRASCALE_PLUS.name == "ULTRASCALE_PLUS"


def test_family_has_generic():
    assert Family.GENERIC is not None
    assert Family.GENERIC.name == "GENERIC"


def test_pin_record_defaults():
    pin = PinRecord(
        ball_id="A1",
        pin_name="IO_L1P_T0_13",
        bank="13",
        io_type="HR",
        family=Family.SERIES_7,
    )
    assert pin.row_index == 0
    assert pin.col_index == 0


def test_device_pinout():
    device = DevicePinout(
        device_name="xc7a100t",
        package_code="fgg484",
        full_name="xc7a100tfgg484",
        family=Family.SERIES_7,
        total_pins=484,
    )
    assert device.full_name == "xc7a100tfgg484"


def test_package_spec():
    spec = PackageSpec(
        pitch_mm=1.0,
        body_size_x=23.0,
        body_size_y=23.0,
        pad_diameter_mm=0.45,
        mask_opening_mm=0.50,
        paste_diameter_mm=0.40,
    )
    assert spec.pitch_mm == 1.0


def test_classified_pin():
    pin = PinRecord(
        ball_id="A1",
        pin_name="VCCINT",
        bank="NA",
        io_type="NA",
        family=Family.SERIES_7,
    )
    cp = ClassifiedPin(
        record=pin,
        pin_type=PinType.POWER,
        direction=PinDirection.POWER,
        rail_name="VCCINT",
        section_name="Power",
    )
    assert cp.rail_name == "VCCINT"


def test_symbol_section():
    section = SymbolSection(name="Bank 13", side="right")
    assert section.pins == []
