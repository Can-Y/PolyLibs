"""Shared test fixtures."""

from pathlib import Path
import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the project root (PolyLibs/)."""
    return Path(__file__).parent.parent


@pytest.fixture
def data_dirs(project_root: Path) -> list[Path]:
    """Return default data directories relative to project root."""
    parent = project_root.parent
    return [
        parent / "pinout_file" / "xilinx" / "7series" / "a7all",
        parent / "pinout_file" / "xilinx" / "7series" / "k7all",
        parent / "pinout_file" / "xilinx" / "7series" / "s7all" / "s7all",
        parent / "pinout_file" / "xilinx" / "7series" / "v7all",
        parent / "pinout_file" / "xilinx" / "ultrascale" / "usaall",
        parent / "pinout_file" / "xilinx" / "ultrascale_plus" / "usaall",
        parent / "pinout_file" / "xilinx" / "zynq_us_plus" / "zupall" / "zupall",
        parent / "pinout_file" / "xilinx" / "zynq7000" / "z7all" / "7zSeriesALL",
        parent / "pinout_file" / "xilinx" / "versal" / "versal-all" / "versal-all",
    ]
