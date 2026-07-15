"""Tests for project scaffolding."""

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None  # type: ignore[assignment]

PROJECT_ROOT = Path(__file__).parent.parent


def test_project_root_is_PolyLibs():
    """Project root is named PolyLibs (or PolyLibs-opensource for the backup copy)."""
    assert PROJECT_ROOT.name in ("PolyLibs", "PolyLibs-opensource")


def test_polylibs_package_exists():
    """polylibs package is importable and exposes version."""
    import polylibs

    assert polylibs.__version__ == "0.1.0"
    assert "Xilinx FPGA" in polylibs.__doc__


def test_required_files_exist():
    """Required scaffolding files exist."""
    required = [
        "requirements.txt",
        "pyproject.toml",
        "polylibs/__init__.py",
        "tests/__init__.py",
        "tests/conftest.py",
    ]
    for rel in required:
        assert (PROJECT_ROOT / rel).is_file(), f"missing {rel}"


def test_required_directories_exist():
    """Required directories exist."""
    required = [
        "polylibs",
        "polylibs/generators",
        "tests",
        "data",
    ]
    for rel in required:
        assert (PROJECT_ROOT / rel).is_dir(), f"missing directory {rel}"


def test_requirements_txt_content():
    """requirements.txt pins pytest>=7.0."""
    req = (PROJECT_ROOT / "requirements.txt").read_text()
    assert "pytest>=7.0" in req


def test_pyproject_toml_content():
    """pyproject.toml has expected metadata and pytest options."""
    raw = (PROJECT_ROOT / "pyproject.toml").read_text()

    if tomllib is not None:
        config = tomllib.loads(raw)
        assert config["build-system"]["requires"] == ["setuptools>=61.0"]
        assert config["build-system"]["build-backend"] == "setuptools.build_meta"
        assert config["project"]["name"] == "polylibs"
        assert config["project"]["version"] == "0.1.0"
        assert config["project"]["requires-python"] == ">=3.10"
        assert "schematic symbol" in config["project"]["description"]
        assert config["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]
        assert config["tool"]["pytest"]["ini_options"]["pythonpath"] == ["polylibs"]
    else:
        # Python 3.10 without an external TOML parser: validate key strings.
        assert 'requires = ["setuptools>=61.0"]' in raw
        assert 'build-backend = "setuptools.build_meta"' in raw
        assert 'name = "polylibs"' in raw
        assert 'version = "0.1.0"' in raw
        assert 'requires-python = ">=3.10"' in raw
        assert 'description = "Xilinx FPGA schematic symbol and PCB footprint generator"' in raw
        assert 'testpaths = ["tests"]' in raw
        assert 'pythonpath = ["polylibs"]' in raw


def test_project_root_fixture(project_root: Path):
    """project_root fixture points to PolyLibs."""
    assert project_root == PROJECT_ROOT


def test_data_dirs_fixture(data_dirs: list[Path], project_root: Path):
    """data_dirs fixture returns all default data directories."""
    parent = project_root.parent
    assert data_dirs == [
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
