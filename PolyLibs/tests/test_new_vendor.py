"""Test that the example new vendor is discovered in the real project layout."""

from pathlib import Path

from polylibs.library import LibraryScanner


def test_example_vendor_discovered(project_root: Path):
    root = project_root.parent
    tree = LibraryScanner(root).scan()

    assert "example" in tree.vendors
    assert tree.vendors["example"].name == "ExampleVendor"

    assert "example_series" in tree.series
    assert tree.series["example_series"].family.name == "GENERIC"

    models = tree.models["example_series"]
    assert len(models) == 1
    assert models[0].full_name == "ex1csg324"
    assert models[0].device == "ex1"
    assert models[0].package == "csg324"
