"""Tkinter GUI for polylibs."""

import json
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk

from .parser import find_device_csv, parse_csv, parse_csv_with_mapping, _split_device_package
from .classifier import classify_all, load_classification_rules, classify_with_rules
from .geometry import get_package_spec, compute_ball_coordinates, PackageRegistry
from .manifest import Model, Series
from .generators.pads import PadsGenerator
from .generators.cadence import CadenceGenerator
from .generators.altium import AltiumGenerator
from .generators.kicad import KiCadGenerator
from .library import LibraryScanner, LibraryTree


class GeneratorRegistry:
    def __init__(self):
        self._gens = {
            "PADS": PadsGenerator(),
            "Cadence": CadenceGenerator(),
            "Altium": AltiumGenerator(),
            "KiCad": KiCadGenerator(),
        }

    def all_generators(self):
        return list(self._gens.values())

    def get(self, name: str):
        return self._gens.get(name)


# Map logical Xilinx series names to the relative data directories that contain
# their pinout CSV files.  Multiple directories can belong to the same series.
_SERIES_DIR_MAP = {
    "7series": [
        "pinout_file/xilinx/7series/a7all",
        "pinout_file/xilinx/7series/k7all",
        "pinout_file/xilinx/7series/s7all/s7all",
        "pinout_file/xilinx/7series/v7all",
    ],
    "ultrascale": ["pinout_file/xilinx/ultrascale/usaall"],
    "ultrascale_plus": ["pinout_file/xilinx/ultrascale_plus/usaall"],
    "zynq_us_plus": ["pinout_file/xilinx/zynq_us_plus/zupall/zupall"],
    "zynq7000": ["pinout_file/xilinx/zynq7000/z7all/7zSeriesALL"],
    "versal": ["pinout_file/xilinx/versal/versal-all/versal-all"],
}


def _series_dirs(root: Path) -> dict[str, list[Path]]:
    """Return existing data directories grouped by series name."""
    result = {}
    for series, rel_dirs in _SERIES_DIR_MAP.items():
        dirs = [root / d for d in rel_dirs if (root / d).is_dir()]
        if dirs:
            result[series] = dirs
    return result


def scan_devices_by_series(root: Path) -> dict[str, dict[str, list[str]]]:
    """Scan pinout CSV files and group by series -> model -> packages.

    Returns a nested dict: {series: {model_upper: [package_upper, ...]}}.
    """
    series_dirs = _series_dirs(root)
    result: dict[str, dict[str, set[str]]] = {}
    for series, dirs in series_dirs.items():
        models: dict[str, set[str]] = {}
        for d in dirs:
            for csv_file in d.glob("**/*.csv"):
                stem = csv_file.stem.lower()
                if stem.endswith("pkg"):
                    stem = stem[:-3]
                device, package = _split_device_package(stem)
                if not device or not package:
                    continue
                models.setdefault(device.upper(), set()).add(package.upper())
        if models:
            result[series] = {k: sorted(v) for k, v in sorted(models.items())}
    return result


def _parse_body_size(s: str) -> tuple[float, float] | None:
    if not s.strip():
        return None
    import re
    m = re.match(r'(\d+\.?\d*)\s*[xX×]\s*(\d+\.?\d*)', s.strip())
    if m:
        return float(m.group(1)), float(m.group(2))
    raise ValueError(f"Invalid body size: {s!r}")


def build_output(
    device_name: str,
    data_dirs: list[Path],
    output_dir: Path,
    selected: dict[str, bool],
    generate_symbol: bool,
    generate_footprint: bool,
    override_pitch: str = "",
    override_body_size: str = "",
    override_pad_dia: str = "",
    overwrite: bool = True,
) -> dict:
    device_name = device_name.strip()
    csv_path = find_device_csv(device_name, data_dirs)
    device = parse_csv(csv_path)
    classified = classify_all(device.pins)

    # Up-front output-directory writability check.
    if output_dir.exists() and not os.access(output_dir, os.W_OK):
        raise PermissionError(f"Output directory is not writable: {output_dir}")

    pitch = float(override_pitch) if override_pitch.strip() else None
    pad_dia = float(override_pad_dia) if override_pad_dia.strip() else None
    body_size = _parse_body_size(override_body_size) if override_body_size.strip() else None

    spec = get_package_spec(
        device.package_code,
        ball_count=device.total_pins,
        override_pitch=pitch,
        override_body_size=body_size,
        override_pad_dia=pad_dia,
    )
    coords = compute_ball_coordinates(device.pins, spec)

    return _write_generated_files(
        device=device,
        classified=classified,
        spec=spec,
        coords=coords,
        output_dir=output_dir,
        selected=selected,
        generate_symbol=generate_symbol,
        generate_footprint=generate_footprint,
        overwrite=overwrite,
    )


def _write_generated_files(
    device,
    classified,
    spec,
    coords,
    output_dir: Path,
    selected: dict[str, bool],
    generate_symbol: bool,
    generate_footprint: bool,
    overwrite: bool = True,
) -> dict:
    """Write symbol/footprint/report outputs for an already-classified device."""
    outdir = output_dir / device.full_name
    outdir.mkdir(parents=True, exist_ok=True)

    registry = GeneratorRegistry()
    files_written = []

    for name, enabled in selected.items():
        if not enabled:
            continue
        gen = registry.get(name)
        if gen is None:
            continue
        tool_dir = outdir / name.lower()
        tool_dir.mkdir(parents=True, exist_ok=True)

        if generate_symbol:
            for filename, content in gen.generate_symbol(device, classified, spec).items():
                path = tool_dir / filename
                if path.exists() and not overwrite:
                    raise FileExistsError(
                        f"File already exists and overwrite=False: {path}"
                    )
                path.write_text(content, encoding="utf-8")
                files_written.append(str(path.relative_to(outdir)))

        if generate_footprint:
            for filename, content in gen.generate_footprint(device, spec, coords).items():
                path = tool_dir / filename
                if path.exists() and not overwrite:
                    raise FileExistsError(
                        f"File already exists and overwrite=False: {path}"
                    )
                path.write_text(content, encoding="utf-8")
                files_written.append(str(path.relative_to(outdir)))

    report_path = outdir / "report.txt"
    if report_path.exists() and not overwrite:
        raise FileExistsError(
            f"File already exists and overwrite=False: {report_path}"
        )
    lines = [
        f"Device: {device.full_name}",
        f"Package: {device.package_code}",
        f"Family: {device.family.name}",
        f"Total pins: {device.total_pins}",
        f"Pitch: {spec.pitch_mm} mm",
        f"Body: {spec.body_size_x} x {spec.body_size_y} mm",
        f"Pad diameter: {spec.pad_diameter_mm} mm",
        "",
        "Files generated:",
    ]
    lines.extend(files_written)
    report_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "device": device.full_name,
        "total_pins": device.total_pins,
        "output_dir": str(outdir),
        "files": files_written,
    }


def build_output_from_library(
    model: Model,
    series: Series,
    output_dir: Path,
    registry: PackageRegistry,
    selected: dict[str, bool],
    generate_symbol: bool = True,
    generate_footprint: bool = True,
    override_pitch: str = "",
    override_body_size: str = "",
    override_pad_dia: str = "",
    overwrite: bool = True,
) -> dict:
    """Generate outputs for a library-backed model using vendor-neutral parsing."""
    device = parse_csv_with_mapping(model.pinout, series)
    # The CSV filename may be generic (e.g. pinout.csv); use the manifest model
    # name for output directories and package lookup.
    device.device_name = model.device
    device.package_code = model.package
    device.full_name = model.full_name

    if series.classification:
        rules = load_classification_rules(series.classification)
        classified = [classify_with_rules(pin, rules) for pin in device.pins]
    else:
        classified = classify_all(device.pins)

    pitch = float(override_pitch) if override_pitch.strip() else None
    pad_dia = float(override_pad_dia) if override_pad_dia.strip() else None
    body_size = _parse_body_size(override_body_size) if override_body_size.strip() else None

    spec = registry.get_spec(
        device.package_code,
        ball_count=device.total_pins,
        override_pitch=pitch,
        override_body_size=body_size,
        override_pad_dia=pad_dia,
    )
    if model.package_spec and model.package_spec.exists():
        registry.add_series_packages(
            json.loads(model.package_spec.read_text(encoding="utf-8"))
        )
        spec = registry.get_spec(device.package_code, ball_count=device.total_pins)

    coords = compute_ball_coordinates(device.pins, spec)

    return _write_generated_files(
        device=device,
        classified=classified,
        spec=spec,
        coords=coords,
        output_dir=output_dir,
        selected=selected,
        generate_symbol=generate_symbol,
        generate_footprint=generate_footprint,
        overwrite=overwrite,
    )


class Application:
    FORMATS = ["KiCad"]
    _LEGACY_VENDOR = "Xilinx"

    def __init__(self, root: tk.Tk, data_dirs: list[Path]):
        self.root = root
        self.data_dirs = data_dirs
        self.root_dir = data_dirs[0].parent if data_dirs else Path.cwd()
        self.root.title("PolyLibs — 一站式 FPGA 库生成器")
        self.root.geometry("650x650")

        # Build vendor → series → model → package tree from library manifests.
        self.library_tree = LibraryScanner(self.root_dir).scan()
        if self.library_tree.vendors:
            self._use_library = True
            self.devices = self._build_device_tree(self.library_tree)
            self.series_dirs = {
                series.id: list(series.data_dirs)
                for series in self.library_tree.series.values()
            }
        else:
            # Fallback to the legacy series directory map.
            self._use_library = False
            legacy = scan_devices_by_series(self.root_dir)
            self.devices = {self._LEGACY_VENDOR: legacy}
            self.series_dirs = _series_dirs(self.root_dir)
        self._vendor_names = {vid: v.name for vid, v in getattr(self, "library_tree", LibraryTree()).vendors.items()}
        if not self._use_library:
            self._vendor_names[self._LEGACY_VENDOR] = self._LEGACY_VENDOR
        self._has_devices = bool(self.devices)

        row = 0
        ttk.Label(root, text="厂商:").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.vendor_var = tk.StringVar()
        self.vendor_combo = ttk.Combobox(
            root, textvariable=self.vendor_var, state="readonly", width=30
        )
        self.vendor_combo.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        self.vendor_combo["values"] = sorted(self.devices.keys())
        self.vendor_combo.bind("<<ComboboxSelected>>", self._on_vendor_changed)

        row += 1
        ttk.Label(root, text="系列:").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.series_var = tk.StringVar()
        self.series_combo = ttk.Combobox(
            root, textvariable=self.series_var, state="readonly", width=30
        )
        self.series_combo.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        self.series_combo.bind("<<ComboboxSelected>>", self._on_series_changed)

        row += 1
        ttk.Label(root, text="型号:").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            root, textvariable=self.model_var, state="readonly", width=30
        )
        self.model_combo.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_changed)

        row += 1
        ttk.Label(root, text="封装:").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.pkg_var = tk.StringVar()
        self.pkg_combo = ttk.Combobox(
            root, textvariable=self.pkg_var, state="readonly", width=30
        )
        self.pkg_combo.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        self.pkg_combo.bind("<<ComboboxSelected>>", self._on_package_changed)

        row += 1
        ttk.Label(root, text="输出格式:").grid(row=row, column=0, sticky="nw", padx=5, pady=5)
        format_frame = ttk.Frame(root)
        format_frame.grid(row=row, column=1, sticky="ew", padx=5, pady=5)

        self.selected = {}
        for i, name in enumerate(self.FORMATS):
            var = tk.BooleanVar(value=True)
            self.selected[name] = var
            ttk.Checkbutton(format_frame, text=name, variable=var).grid(
                row=i // 2, column=i % 2, sticky="w", padx=5
            )

        row += 1
        ttk.Label(root, text="输出:").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.sym_var = tk.BooleanVar(value=True)
        self.foot_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(root, text="原理图符号", variable=self.sym_var).grid(
            row=row, column=1, sticky="w", padx=5
        )

        row += 1
        ttk.Checkbutton(root, text="PCB 封装", variable=self.foot_var).grid(
            row=row, column=1, sticky="w", padx=5
        )

        row += 1
        ttk.Label(root, text="输出目录:").grid(row=row, column=0, sticky="w", padx=5, pady=5)
        out_frame = ttk.Frame(root)
        out_frame.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        self.out_var = tk.StringVar(value=str(Path.cwd() / "output"))
        ttk.Entry(out_frame, textvariable=self.out_var, width=40).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(out_frame, text="浏览", command=self._browse).pack(side="left", padx=5)

        row += 1
        ttk.Label(root, text="高级选项:").grid(row=row, column=0, sticky="nw", padx=5, pady=5)
        adv_frame = ttk.Frame(root)
        adv_frame.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(adv_frame, text="球间距 mm:").grid(row=0, column=0, sticky="w")
        self.pitch_var = tk.StringVar()
        ttk.Entry(adv_frame, textvariable=self.pitch_var, width=10).grid(row=0, column=1, padx=5)
        ttk.Label(adv_frame, text="封装尺寸 mm:").grid(row=1, column=0, sticky="w")
        self.body_var = tk.StringVar()
        ttk.Entry(adv_frame, textvariable=self.body_var, width=10).grid(row=1, column=1, padx=5)
        ttk.Label(adv_frame, text="焊盘直径 mm:").grid(row=2, column=0, sticky="w")
        self.pad_var = tk.StringVar()
        ttk.Entry(adv_frame, textvariable=self.pad_var, width=10).grid(row=2, column=1, padx=5)

        row += 1
        self.generate_btn = ttk.Button(root, text="生成", command=self._generate)
        self.generate_btn.grid(row=row, column=1, sticky="w", padx=5, pady=10)

        row += 1
        self.log = tk.Text(root, height=10, state="disabled")
        self.log.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        root.grid_rowconfigure(row, weight=1)
        root.grid_columnconfigure(1, weight=1)

        # Footer logo and subscription text.
        self._logo_photo = self._load_logo()
        if self._logo_photo:
            footer = ttk.Frame(root)
            footer.grid(row=row + 1, column=0, columnspan=2, sticky="s", padx=5, pady=5)
            ttk.Label(footer, image=self._logo_photo).pack()
            ttk.Label(footer, text="欢迎关注公众号FPGAer_Zone").pack()

        # Initialize default selections.
        if self.vendor_combo["values"]:
            self.vendor_var.set(self.vendor_combo["values"][0])
            self._on_vendor_changed()
            self._on_package_changed()

        if not self._has_devices:
            self.generate_btn.configure(state="disabled")
            self._log(
                f"错误: 在项目根目录 {self.root_dir} 未找到任何器件数据，"
                "请确认 library/ 与 pinout_file/ 文件夹与本程序在同一目录。"
            )

    @staticmethod
    def _build_device_tree(tree: LibraryTree) -> dict[str, dict[str, dict[str, list[str]]]]:
        result: dict[str, dict[str, dict[str, list[str]]]] = {}
        for vendor in tree.vendors.values():
            result[vendor.id] = {}
            for series in tree.series_for_vendor(vendor.id):
                models: dict[str, list[str]] = {}
                for model in tree.models_for_series(series.id):
                    models.setdefault(model.device, []).append(model.package)
                result[vendor.id][series.id] = {
                    k: sorted(v) for k, v in sorted(models.items())
                }
        return result

    def _on_vendor_changed(self, event=None):
        vendor = self.vendor_var.get()
        series = sorted(self.devices.get(vendor, {}).keys())
        self.series_combo["values"] = series
        if series:
            self.series_var.set(series[0])
        else:
            self.series_var.set("")
        self._on_series_changed()

    def _on_series_changed(self, event=None):
        vendor = self.vendor_var.get()
        series = self.series_var.get()
        models = sorted(self.devices.get(vendor, {}).get(series, {}).keys())
        self.model_combo["values"] = models
        if models:
            self.model_var.set(models[0])
        else:
            self.model_var.set("")
        self._on_model_changed()

    def _on_model_changed(self, event=None):
        vendor = self.vendor_var.get()
        series = self.series_var.get()
        model = self.model_var.get()
        packages = sorted(self.devices.get(vendor, {}).get(series, {}).get(model, []))
        self.pkg_combo["values"] = packages
        if packages:
            self.pkg_var.set(packages[0])
        else:
            self.pkg_var.set("")
        self._on_package_changed()

    def _on_package_changed(self, event=None):
        """Populate advanced options with the package's default geometry."""
        package = self.pkg_var.get()
        if not package:
            return

        series_id = self.series_var.get()
        try:
            if self._use_library:
                series = self.library_tree.series.get(series_id)
                if series:
                    registry = PackageRegistry(self.root_dir).load()
                    if series.packages:
                        registry.add_series_packages(series.packages)
                    spec = registry.get_spec(package)
                else:
                    spec = get_package_spec(package)
            else:
                spec = get_package_spec(package)

            self.pitch_var.set(str(spec.pitch_mm))
            self.body_var.set(f"{spec.body_size_x}x{spec.body_size_y}")
            self.pad_var.set(str(spec.pad_diameter_mm))
        except Exception:
            # Leave fields unchanged if lookup fails.
            pass

    def _browse(self):
        path = filedialog.askdirectory(initialdir=self.out_var.get())
        if path:
            self.out_var.set(path)

    def _log(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _generate(self):
        vendor = self.vendor_var.get()
        series = self.series_var.get()
        model = self.model_var.get()
        package = self.pkg_var.get()
        if not vendor or not series or not model or not package:
            messagebox.showerror("错误", "请选择厂商、系列、型号和封装")
            return

        device = (model + package).lower()
        data_dirs = self.series_dirs.get(series, self.data_dirs)

        selected = {name: var.get() for name, var in self.selected.items()}
        if not any(selected.values()):
            messagebox.showerror("错误", "请至少选择一种输出格式")
            return

        output_dir = Path(self.out_var.get())
        if output_dir.exists() and not os.access(output_dir, os.W_OK):
            messagebox.showerror("错误", f"输出目录不可写: {output_dir}")
            return

        device_dir = output_dir / device.lower()
        overwrite = True
        if device_dir.exists() and any(device_dir.iterdir()):
            overwrite = messagebox.askyesno(
                "覆盖确认",
                f"目录 {device_dir} 已存在且包含文件。\n是否覆盖？",
            )
            if not overwrite:
                return

        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

        def worker():
            try:
                self.root.after(0, lambda: self._log(f"开始生成: {device}"))
                library_model = None
                library_series = None
                if self._use_library:
                    library_series = self.library_tree.series.get(series)
                    if library_series:
                        for candidate in self.library_tree.models_for_series(series):
                            if candidate.device == model and candidate.package == package:
                                library_model = candidate
                                break

                if library_model is not None:
                    registry = PackageRegistry(self.root_dir).load()
                    if library_series.packages:
                        registry.add_series_packages(library_series.packages)
                    summary = build_output_from_library(
                        model=library_model,
                        series=library_series,
                        output_dir=output_dir,
                        registry=registry,
                        selected=selected,
                        generate_symbol=self.sym_var.get(),
                        generate_footprint=self.foot_var.get(),
                        override_pitch=self.pitch_var.get(),
                        override_body_size=self.body_var.get(),
                        override_pad_dia=self.pad_var.get(),
                        overwrite=overwrite,
                    )
                else:
                    summary = build_output(
                        device_name=device,
                        data_dirs=data_dirs,
                        output_dir=output_dir,
                        selected=selected,
                        generate_symbol=self.sym_var.get(),
                        generate_footprint=self.foot_var.get(),
                        override_pitch=self.pitch_var.get(),
                        override_body_size=self.body_var.get(),
                        override_pad_dia=self.pad_var.get(),
                        overwrite=overwrite,
                    )
                self.root.after(0, lambda: self._log(f"完成: {summary['output_dir']}"))
                self.root.after(0, lambda: self._log(f"共生成 {len(summary['files'])} 个文件"))
                self.root.after(0, lambda: messagebox.showinfo("完成", f"生成成功\n{summary['output_dir']}"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"错误: {e}"))
                self.root.after(0, lambda: messagebox.showerror("错误", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _resource_path(self, name: str) -> Path:
        """Resolve a runtime resource path for both script and PyInstaller exe."""
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / name
        return self.root_dir / name

    def _load_logo(self, size: int = 100) -> ImageTk.PhotoImage | None:
        """Load and resize the FPGAer_Zone logo image."""
        try:
            image_path = self._resource_path("FPGAer_Zone_258.jpg")
            if not image_path.exists():
                return None
            img = Image.open(image_path)
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None


def run_gui(data_dirs: list[Path] | None = None):
    if data_dirs is None:
        root = Path(__file__).parent.parent.parent
        data_dirs = [
            root / "library",
        ]
    root = tk.Tk()
    app = Application(root, data_dirs)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
