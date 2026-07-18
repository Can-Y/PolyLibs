"""Pin classification and symbol partitioning."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import (
    PinRecord,
    ClassifiedPin,
    PinType,
    PinDirection,
    SymbolSection,
)

POWER_PATTERNS = [
    (re.compile(r'^VCCINT.*$', re.I), 'VCCINT'),
    (re.compile(r'^VCCAUX.*$', re.I), 'VCCAUX'),
    (re.compile(r'^VCCO_(\d+)$', re.I), None),
    (re.compile(r'^VCCO_PS.*$', re.I), 'VCCO_PSIO'),
    (re.compile(r'^VCC_PS.*$', re.I), 'VCC_PS'),
    (re.compile(r'^PS_MGTRAVCC.*$', re.I), 'PS_MGT'),
    (re.compile(r'^PS_MGTRAVTT.*$', re.I), 'PS_MGT'),
    (re.compile(r'^VCCBRAM$', re.I), 'VCCBRAM'),
    (re.compile(r'^VCCADC_?\d*$', re.I), 'VCCADC'),
    (re.compile(r'^VCCBATT_?\d*$', re.I), 'VCCBATT'),
    # Versal / GTYP transceiver analog supplies (GTYP_AVCC_*, GTYP_AVTT_, etc.)
    (re.compile(r'^GT.*AVCC.*$', re.I), 'MGTAVCC'),
    (re.compile(r'^GT.*AVTT.*$', re.I), 'MGTAVTT'),
    (re.compile(r'^GT.*AVCCAUX.*$', re.I), 'MGTVCCAUX'),
    (re.compile(r'^MGTAVCC.*$', re.I), 'MGTAVCC'),
    (re.compile(r'^MGTAVTT.*$', re.I), 'MGTAVTT'),
    (re.compile(r'^MGTVCCAUX.*$', re.I), 'MGTVCCAUX'),
    # Versal domain supplies (VCC_AIE, VCC_FPD, VCC_LPD, VCC_SOC, VCC_RAM, ...)
    (re.compile(r'^VCC_.*$', re.I), None),
    # Versal IO supplies (VCCIO_MIPI_507, VCCIO_USB2_504, ...)
    (re.compile(r'^VCCIO_.*$', re.I), None),
    (re.compile(r'^VBATT$', re.I), 'VBATT'),
]

GROUND_PATTERNS = [
    re.compile(r'^GND$', re.I),
    re.compile(r'^GNDADC_?\d*$', re.I),
    re.compile(r'^RSVDGND.*$', re.I),
    re.compile(r'^GND_PS.*$', re.I),
    re.compile(r'^GND_SENSE$', re.I),
    re.compile(r'^GND_SMON$', re.I),
    # Versal ground sense pins (GND_VCC_AIE_SENSE, GND_VCCINT_SENSE, ...)
    re.compile(r'^GND_.*$', re.I),
]

# Dedicated boot/configuration pin names (family-agnostic).
# Optional PS_ prefix (Zynq), optional JTAG_ prefix, optional _bank suffix.
# Deliberately narrow – does NOT match dual-purpose IOs whose name merely
# *contains* a config keyword (e.g. IO_L3P_T0_DQS_PUDC_B_14 is regular IO).
_CONFIG_NAMES = (
    r"DONE|TCK|TMS|TDI|TDO|PROGRAM_B|PROG_B|INIT_B|CCLK|PUDC_B|POR_B|"
    r"ERROR_OUT|ERROR_STATUS|SRST_B|"
    r"REF_CLK|"
    r"RTC_PADO|RTC_PADI|PADO|PADI|"
    r"RTC|"
    r"M[0-3]|MODE[0-9]|"
    r"CFGBVS|EMCCLK|CSI_B|FCS_B|RDWR_FCS_B|POR_OVERRIDE"
)
CONFIG_PATTERNS = [
    re.compile(rf"^(?:PS_)?(?:JTAG_)?(?:{_CONFIG_NAMES})(?:_\d+)?$", re.I),
]

MGT_PATTERNS = [
    re.compile(r'^(MGT|PS_MGT|GTH|GTY|GTX|GTP|MGTH)', re.I),
]

ANALOG_PATTERNS = [
    re.compile(r'^(VN|VP|VREF[NPR]|DXP|DXN|VCCADC|GNDADC|ADC_)_?\d*$', re.I),
]

NC_PATTERNS = [
    re.compile(r'^NC$', re.I),
    re.compile(r'^RSVD', re.I),
]


def classify_pin(record: PinRecord) -> ClassifiedPin:
    """Classify a single pin."""
    name = record.pin_name.strip()
    upper = name.upper()
    io_type = record.io_type.upper() if record.io_type else ''
    nc = record.no_connect.upper() if record.no_connect else ''

    # Ground (including reserved ground) must be detected before the broader
    # RSVD no-connect pattern swallows RSVDGND_* pins.
    pin_type = PinType.IO
    rail_name = ''

    for pattern, rail in POWER_PATTERNS:
        m = pattern.match(name)
        if m:
            pin_type = PinType.POWER
            rail_name = rail or (f'VCCO_{m.group(1)}' if m.lastindex else name.upper())
            break

    if pin_type == PinType.IO:
        for pattern in GROUND_PATTERNS:
            if pattern.match(name):
                pin_type = PinType.GROUND
                rail_name = 'GND'
                break

    if pin_type == PinType.IO and (nc in ('YES', 'NC') or upper == 'NC' or upper.startswith('RSVD')):
        return ClassifiedPin(record, PinType.NO_CONNECT, PinDirection.NC, section_name='No Connect')

    if pin_type == PinType.IO:
        for pattern in CONFIG_PATTERNS:
            if pattern.match(name):
                pin_type = PinType.CONFIG
                break

    if pin_type == PinType.IO:
        for pattern in MGT_PATTERNS:
            if pattern.match(name):
                pin_type = PinType.MGT
                break

    if pin_type == PinType.IO:
        for pattern in ANALOG_PATTERNS:
            if pattern.match(name):
                pin_type = PinType.ANALOG
                break

    if io_type == 'CONFIG' and pin_type == PinType.IO:
        pin_type = PinType.CONFIG
    elif io_type in ('GTP', 'GTX', 'GTH', 'GTY') and pin_type == PinType.IO:
        pin_type = PinType.MGT

    direction = _get_direction(pin_type, name)
    section = _get_section(record, pin_type, rail_name)

    return ClassifiedPin(record, pin_type, direction, rail_name=rail_name, section_name=section)


def _get_direction(pin_type: PinType, name: str) -> PinDirection:
    if pin_type == PinType.POWER:
        return PinDirection.POWER
    if pin_type == PinType.GROUND:
        return PinDirection.GROUND
    if pin_type == PinType.IO:
        return PinDirection.BIDIR
    if pin_type == PinType.MGT:
        return PinDirection.BIDIR
    if pin_type == PinType.ANALOG:
        return PinDirection.PASSIVE
    if pin_type == PinType.NO_CONNECT:
        return PinDirection.NC
    if pin_type == PinType.CONFIG:
        upper = name.upper()
        # DONE, TDO, ERROR_OUT, ERROR_STATUS → OUTPUT
        if re.search(r'(?:^|_)DONE', upper) or re.search(r'(?:^|_)TDO', upper) or re.search(r'ERROR_OUT|ERROR_STATUS', upper):
            return PinDirection.OUTPUT
        # PROGRAM, INIT → BIDIR
        if 'PROGRAM' in upper or 'INIT' in upper:
            return PinDirection.BIDIR
        return PinDirection.INPUT
    return PinDirection.PASSIVE


def _get_section(record: PinRecord, pin_type: PinType, rail_name: str) -> str:
    if pin_type == PinType.POWER:
        return f'Power: {rail_name}' if rail_name else 'Power'
    if pin_type == PinType.GROUND:
        return 'Ground'
    if pin_type == PinType.CONFIG:
        return 'Configuration'
    if pin_type == PinType.MGT:
        return 'MGT Transceivers'
    if pin_type == PinType.ANALOG:
        return 'Analog / ADC'
    if pin_type == PinType.NO_CONNECT:
        return 'No Connect'
    if pin_type == PinType.IO:
        bank = record.bank if record.bank and record.bank != 'NA' else '?'
        return f'Bank {bank}'
    return 'Miscellaneous'


def classify_all(pins: list[PinRecord]) -> list[ClassifiedPin]:
    return [classify_pin(p) for p in pins]


def partition_for_symbol(pins: list[ClassifiedPin]) -> list[SymbolSection]:
    """Group classified pins into symbol sections."""
    groups: dict[str, list[ClassifiedPin]] = {}
    for p in pins:
        groups.setdefault(p.section_name, []).append(p)

    # Sort within each group by ball_id
    for key in groups:
        groups[key].sort(key=lambda p: p.record.ball_id)

    sections = []
    for name, section_pins in groups.items():
        side = _assign_side(name)
        sections.append(SymbolSection(name=name, side=side, pins=section_pins))
    return sections


def _assign_side(name: str) -> str:
    if name.startswith('Bank'):
        return 'right'
    if name.startswith('Power') or name == 'Ground':
        return 'bottom'
    if name in ('Configuration', 'MGT Transceivers', 'Analog / ADC'):
        return 'top'
    return 'left'


@dataclass
class ClassificationRules:
    power_patterns: list[tuple[re.Pattern, str | None]] = field(default_factory=list)
    ground_patterns: list[re.Pattern] = field(default_factory=list)
    config_patterns: list[re.Pattern] = field(default_factory=list)
    mgt_patterns: list[re.Pattern] = field(default_factory=list)
    analog_patterns: list[re.Pattern] = field(default_factory=list)
    nc_patterns: list[re.Pattern] = field(default_factory=list)
    direction_rules: list[dict[str, Any]] = field(default_factory=list)


def _compile_rules(raw: dict[str, Any]) -> ClassificationRules:
    def compile_pattern(entry: dict[str, Any]) -> tuple[re.Pattern, str | None] | re.Pattern:
        pattern = re.compile(entry["pattern"], re.IGNORECASE)
        rail = entry.get("rail")
        return (pattern, rail) if rail is not None else pattern

    power = []
    for entry in raw.get("power_patterns", []):
        item = compile_pattern(entry)
        power.append(item if isinstance(item, tuple) else (item, None))

    return ClassificationRules(
        power_patterns=power,
        ground_patterns=[re.compile(p["pattern"], re.I) for p in raw.get("ground_patterns", [])],
        config_patterns=[re.compile(p["pattern"], re.I) for p in raw.get("config_patterns", [])],
        mgt_patterns=[re.compile(p["pattern"], re.I) for p in raw.get("mgt_patterns", [])],
        analog_patterns=[re.compile(p["pattern"], re.I) for p in raw.get("analog_patterns", [])],
        nc_patterns=[re.compile(p["pattern"], re.I) for p in raw.get("nc_patterns", [])],
        direction_rules=raw.get("direction_rules", [{"default": "BIDIRECTIONAL"}]),
    )


def load_classification_rules(source: Path | dict[str, Any]) -> ClassificationRules:
    if isinstance(source, Path):
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    else:
        raw = source
    if not isinstance(raw, dict):
        raise ValueError("classification rules must be a dict")
    return _compile_rules(raw)


def _rail_name(name: str, pattern: re.Pattern, rail_template: str | None) -> str:
    if rail_template is None:
        return name.upper()
    m = pattern.match(name)
    if m and m.lastindex is not None:
        return rail_template.format(*m.groups())
    return rail_template


def classify_with_rules(record: PinRecord, rules: ClassificationRules) -> ClassifiedPin:
    name = record.pin_name.strip()

    for pattern, rail_template in rules.power_patterns:
        if pattern.match(name):
            return ClassifiedPin(
                record, PinType.POWER, PinDirection.POWER,
                rail_name=_rail_name(name, pattern, rail_template),
                section_name="Power",
            )

    for pattern in rules.ground_patterns:
        if pattern.match(name):
            return ClassifiedPin(record, PinType.GROUND, PinDirection.GROUND, rail_name="GND", section_name="Ground")

    for pattern in rules.nc_patterns:
        if pattern.match(name):
            return ClassifiedPin(record, PinType.NO_CONNECT, PinDirection.NC, section_name="No Connect")

    for pattern in rules.config_patterns:
        if pattern.match(name):
            return ClassifiedPin(record, PinType.CONFIG, PinDirection.PASSIVE, section_name="Config")

    for pattern in rules.mgt_patterns:
        if pattern.match(name):
            return ClassifiedPin(record, PinType.MGT, PinDirection.BIDIR, section_name="MGT")

    for pattern in rules.analog_patterns:
        if pattern.match(name):
            return ClassifiedPin(record, PinType.ANALOG, PinDirection.PASSIVE, section_name="Analog")

    direction = _rule_direction(name, rules.direction_rules)
    return ClassifiedPin(record, PinType.IO, direction, section_name=f"Bank {record.bank}")


def _parse_direction(value: str) -> PinDirection:
    value = value.upper()
    mapping = {
        "INPUT": PinDirection.INPUT,
        "OUTPUT": PinDirection.OUTPUT,
        "BIDIRECTIONAL": PinDirection.BIDIR,
        "BIDIR": PinDirection.BIDIR,
        "POWER": PinDirection.POWER,
        "GROUND": PinDirection.GROUND,
        "PASSIVE": PinDirection.PASSIVE,
        "NC": PinDirection.NC,
    }
    if value in mapping:
        return mapping[value]
    return PinDirection[value]


def _rule_direction(name: str, direction_rules: list[dict[str, Any]]) -> PinDirection:
    for rule in direction_rules:
        if "when" in rule:
            when = rule["when"]
            name_pattern = when.get("name_pattern")
            if name_pattern and re.search(name_pattern, name, re.I):
                return _parse_direction(rule["direction"])
        elif "default" in rule:
            return _parse_direction(rule["default"])
    return PinDirection.BIDIR
