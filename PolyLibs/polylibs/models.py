"""Data models for polylibs."""

from dataclasses import dataclass, field
from enum import Enum, auto


class Family(Enum):
    """Xilinx FPGA family enumeration."""
    SERIES_7 = auto()
    ULTRASCALE = auto()
    ULTRASCALE_PLUS = auto()
    GENERIC = auto()


class PinType(Enum):
    """Functional pin type."""
    POWER = auto()
    GROUND = auto()
    IO = auto()
    CONFIG = auto()
    MGT = auto()
    ANALOG = auto()
    NO_CONNECT = auto()
    MISC = auto()


class PinDirection(Enum):
    """Pin direction for schematic symbols."""
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    BIDIR = "BIDIRECTIONAL"
    POWER = "POWER"
    GROUND = "GROUND"
    PASSIVE = "PASSIVE"
    NC = "NC"


@dataclass
class PinRecord:
    """A single pin from the package pinout."""
    ball_id: str
    pin_name: str
    bank: str
    io_type: str
    family: Family
    byte_group: str = "NA"
    slr: str = "NA"
    vccaux_group: str = "NA"
    no_connect: str = "NA"
    row_index: int = 0
    col_index: int = 0


@dataclass
class DevicePinout:
    """Complete parsed device pinout."""
    device_name: str
    package_code: str
    full_name: str
    family: Family
    total_pins: int
    pins: list[PinRecord] = field(default_factory=list)


@dataclass
class PackageSpec:
    """Physical specifications for a BGA package."""
    pitch_mm: float
    body_size_x: float
    body_size_y: float
    pad_diameter_mm: float
    mask_opening_mm: float
    paste_diameter_mm: float


@dataclass
class ClassifiedPin:
    """A pin with classification and direction."""
    record: PinRecord
    pin_type: PinType
    direction: PinDirection
    rail_name: str = ""
    section_name: str = ""


@dataclass
class SymbolSection:
    """A section of a split schematic symbol."""
    name: str
    side: str = "right"  # left, right, top, bottom
    pins: list[ClassifiedPin] = field(default_factory=list)
