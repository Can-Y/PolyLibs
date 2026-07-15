"""Verify a generated KiCad footprint: pad ranges and KiCad CLI validity."""

import re
import subprocess
import sys
from pathlib import Path


def parse_kicad_mod(path: Path) -> dict[str, tuple[float, float]]:
    """Extract pad name -> (x, y) from a .kicad_mod file."""
    text = path.read_text(encoding="utf-8")
    pads: dict[str, tuple[float, float]] = {}
    # Match (pad "NAME" smd circle\n    (at X Y) ...
    for m in re.finditer(
        r'\(pad\s+"([^"]+)"\s+smd\s+circle\s+\(at\s+([-0-9.]+)\s+([-0-9.]+)',
        text,
    ):
        pads[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return pads


def analyze(pads: dict[str, tuple[float, float]], body_size: tuple[float, float]) -> dict:
    xs = [x for x, _ in pads.values()]
    ys = [y for _, y in pads.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y
    body_x, body_y = body_size
    return {
        "count": len(pads),
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "width": width,
        "height": height,
        "body_x": body_x,
        "body_y": body_y,
        "inside_body": width <= body_x and height <= body_y,
    }


def kicad_cli_check(kicad_mod: Path, kicad_cli: str = "kicad-cli") -> tuple[bool, str]:
    """Run kicad-cli fp export svg to validate the footprint file."""
    pretty = kicad_mod.parent / f"{kicad_mod.stem}_verify.pretty"
    pretty.mkdir(exist_ok=True)
    dest = pretty / kicad_mod.name
    dest.write_text(kicad_mod.read_text(encoding="utf-8"), encoding="utf-8")
    outdir = kicad_mod.parent / f"{kicad_mod.stem}_verify_svg"
    outdir.mkdir(exist_ok=True)
    cmd = [kicad_cli, "fp", "export", "svg", "-o", str(outdir), str(pretty)]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
        )
        return result.returncode == 0, (result.stdout or "") + (result.stderr or "")
    except Exception as e:
        return False, str(e)


def parse_svg_pads(svg_path: Path, pad_radius_mm: float = 0.225) -> dict[str, tuple[float, float]]:
    """Extract pad centres from an SVG exported by kicad-cli fp export svg.

    Pads are rendered as <circle> elements inside a group with KiCad's F.Cu
    colour (#C83434).  We accept circles whose radius matches the pad radius to
    avoid picking up silkscreen markers.
    """
    text = svg_path.read_text(encoding="utf-8")
    pads: list[tuple[float, float]] = []
    tol = 0.01
    # Match <circle cx="X" cy="Y" r="R" />
    for m in re.finditer(r'<circle\s+cx="([-0-9.]+)"\s+cy="([-0-9.]+)"\s+r="([-0-9.]+)"', text):
        r = float(m.group(3))
        if abs(r - pad_radius_mm) <= tol:
            pads.append((float(m.group(1)), float(m.group(2))))
    return pads


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <footprint.kicad_mod> [body_x body_y]", file=sys.stderr)
        return 2
    fp_path = Path(sys.argv[1])
    body_size = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) >= 4 else (23.0, 23.0)

    pads = parse_kicad_mod(fp_path)
    info = analyze(pads, body_size)

    print(f"Footprint: {fp_path}")
    print(f"Pads: {info['count']}")
    print(f"Pad X range: {info['min_x']:.4f} ~ {info['max_x']:.4f} (span {info['width']:.4f} mm)")
    print(f"Pad Y range: {info['min_y']:.4f} ~ {info['max_y']:.4f} (span {info['height']:.4f} mm)")
    print(f"Body size: {info['body_x']} x {info['body_y']} mm")
    print(f"Pads inside body: {info['inside_body']}")

    ok, msg = kicad_cli_check(fp_path)
    print(f"kicad-cli fp export svg: {'OK' if ok else 'FAILED'}")
    if not ok:
        print(msg)
        return 1

    svg_dir = fp_path.parent / f"{fp_path.stem}_verify_svg"
    svg_files = list(svg_dir.glob("*.svg"))
    if svg_files:
        svg_pads = parse_svg_pads(svg_files[0])
        svg_info = analyze({f"svg_{i}": p for i, p in enumerate(svg_pads)}, body_size)
        print(f"SVG pad count: {svg_info['count']}")
        print(f"SVG pad X range: {svg_info['min_x']:.4f} ~ {svg_info['max_x']:.4f} (span {svg_info['width']:.4f} mm)")
        print(f"SVG pad Y range: {svg_info['min_y']:.4f} ~ {svg_info['max_y']:.4f} (span {svg_info['height']:.4f} mm)")
        print(f"SVG pads inside body: {svg_info['inside_body']}")
        info = svg_info

    return 0 if info["inside_body"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
