"""Abstract base class for EDA generators."""

from abc import ABC, abstractmethod
from ..models import DevicePinout, PackageSpec, ClassifiedPin


class Generator(ABC):
    """Base class for schematic symbol and PCB footprint generators."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable generator name."""

    @abstractmethod
    def generate_symbol(
        self,
        device: DevicePinout,
        pins: list[ClassifiedPin],
        spec: PackageSpec,
    ) -> dict[str, str]:
        """Return mapping of filename -> content for schematic symbol files."""

    @abstractmethod
    def generate_footprint(
        self,
        device: DevicePinout,
        spec: PackageSpec,
        coords: dict[str, tuple[float, float]],
    ) -> dict[str, str]:
        """Return mapping of filename -> content for PCB footprint files."""
