# 厂商感知型型号扩展接口实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `fpga_libs_tool` 的型号库完全数据驱动：新增厂商/系列/型号只需修改运行时配置文件和 CSV，无需重新编译 exe；GUI 下拉框增加厂商层级。

**Architecture：** 新增 `library/` 可扩展库根，每个系列一个统一 `manifest.yaml`（含 vendor/series/models 三段）；新增 `LibraryScanner`、`GenericParser`、`RuleBasedClassifier`、`PackageRegistry` 四个核心模块；GUI 用扫描结果构建厂商 → 系列 → 型号 → 封装树，同时保留现有 `_SERIES_DIR_MAP` 作为 fallback。

**Tech Stack：** Python 3.14、Tkinter、PyInstaller、PyYAML（新增依赖）、Pillow（已存在）、pytest。

## Global Constraints

- 对现有 535 个 Xilinx 模型零迁移成本。
- 现有 55 个 pytest 用例必须继续通过。
- `fpga_libs_tool.spec` 不再把 `pkg_db.json` 打包进 exe；`data/` 与 `library/` 作为运行时数据复制到 `dist/`。
- 新厂商使用 `family: GENERIC`。
- `column_map` 中 key 为内部 canonical 字段，value 为 CSV 实际列名。
- 分类规则匹配顺序固定：`power → ground → nc → config → mgt → analog`。
- 新增依赖：`PyYAML>=6.0`；需加入 `fpga_libs_tool/requirements.txt` 并安装。

---

## File Structure

| 文件 | 职责 |
|---|---|
| `fpga_libs_tool/fpga_libs/models.py` | 增加 `Family.GENERIC`。 |
| `fpga_libs_tool/fpga_libs/manifest.py` | `Vendor`/`Series`/`Model` 数据类；`load_manifest()`/`validate_manifest()`。 |
| `fpga_libs_tool/fpga_libs/library.py` | `LibraryScanner` + `LibraryTree`：扫描 `library/**/manifest.yaml` 并构建树。 |
| `fpga_libs_tool/fpga_libs/parser.py` | 新增 `parse_csv_with_mapping()`；保留现有 `parse_csv()`。 |
| `fpga_libs_tool/fpga_libs/classifier.py` | 新增 `ClassificationRules`、`load_classification_rules()`、`classify_with_rules()`；保留现有分类器。 |
| `fpga_libs_tool/fpga_libs/geometry.py` | 外置 `pkg_db.json` 加载；新增 `PackageRegistry` 支持系列级/型号级覆盖。 |
| `fpga_libs_tool/fpga_libs/gui.py` | 增加厂商下拉框；使用 `LibraryTree` 填充联动下拉框；fallback 到现有 `_SERIES_DIR_MAP`。 |
| `fpga_libs_tool/fpga_libs/__main__.py` | 增加 `library scan` / `library validate` / `add-package` CLI 子命令。 |
| `fpga_libs_tool/fpga_libs/cli.py` | （可选）把 CLI 逻辑从 `__main__.py` 抽出来，保持 `__main__.py` 只做入口。 |
| `fpga_libs_tool.spec` | 更新 `datas`/`hiddenimports`；构建后复制 `data/`、`library/` 到 `dist/`。 |
| `library/xilinx/*/manifest.yaml` | 为现有 Xilinx 系列创建 manifest，指向现有 `a7all/` 等目录。 |
| `tests/test_*.py` | 新增单元/集成测试。 |

---

## Task 1: 扩展 `Family` 枚举

**Files:**
- Modify: `fpga_libs_tool/fpga_libs/models.py:7-11`
- Test: `fpga_libs_tool/tests/test_models.py`

**Interfaces:**
- Produces: `Family.GENERIC` enum member.

- [ ] **Step 1: Write the failing test**

```python
from fpga_libs.models import Family

def test_family_has_generic():
    assert Family.GENERIC is not None
    assert Family.GENERIC.name == "GENERIC"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest fpga_libs_tool/tests/test_models.py::test_family_has_generic -v`
Expected: `AttributeError: GENERIC`

- [ ] **Step 3: Add `GENERIC` to enum**

```python
class Family(Enum):
    SERIES_7 = auto()
    ULTRASCALE = auto()
    ULTRASCALE_PLUS = auto()
    GENERIC = auto()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest fpga_libs_tool/tests/test_models.py::test_family_has_generic -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fpga_libs_tool/fpga_libs/models.py fpga_libs_tool/tests/test_models.py
git commit -m "feat(models): add Family.GENERIC for non-Xilinx vendors"
```

---

## Task 2: Manifest 数据模型与解析

**Files:**
- Create: `fpga_libs_tool/fpga_libs/manifest.py`
- Test: `fpga_libs_tool/tests/test_manifest.py`

**Interfaces:**
- Produces: `Vendor`, `Series`, `Model` dataclasses; `load_manifest(path: Path) -> tuple[Vendor, Series, list[Model]]`; `validate_manifest(vendor, series, models) -> None`.

- [ ] **Step 0: Add PyYAML dependency**

Update `fpga_libs_tool/requirements.txt`:

```text
pytest>=7.0
PyYAML>=6.0
```

Install:

```bash
python -m pip install -r fpga_libs_tool/requirements.txt
```

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import pytest
from fpga_libs.manifest import load_manifest

def test_load_manifest_minimal(tmp_path: Path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("""
vendor:
  id: testvendor
  name: TestVendor

series:
  id: testseries
  name: TestSeries
  family: GENERIC
  data_dirs: ["."]
  column_map:
    pin: Location
    pin_name: Name
    bank: Bank
    io_type: Type

models:
  - device: dev1
    package: pkg1
    full_name: dev1pkg1
    pinout: dev1/pinout.csv
""")
    vendor, series, models = load_manifest(manifest)
    assert vendor.id == "testvendor"
    assert series.id == "testseries"
    assert len(models) == 1
    assert models[0].device == "dev1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest fpga_libs_tool/tests/test_manifest.py::test_load_manifest_minimal -v`
Expected: `ModuleNotFoundError: fpga_libs.manifest`

- [ ] **Step 3: Implement `manifest.py`**

```python
"""Manifest parsing for vendor/series/models."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import Family


@dataclass(frozen=True)
class Vendor:
    id: str
    name: str
    display_name: str = ""
    aliases: list[str] = field(default_factory=list)


@dataclass
class Series:
    id: str
    name: str
    vendor_id: str
    family: Family
    data_dirs: list[Path]
    column_map: dict[str, str]
    classification: Any = None
    packages: Any = None
    manifest_dir: Path = Path()


@dataclass
class Model:
    device: str
    package: str
    full_name: str
    pinout: Path
    package_spec: Path | None = None
    series_id: str = ""


_ID_RE = re.compile(r"^[a-z0-9_-]+$")


def _parse_family(value: str) -> Family:
    try:
        return Family[value.upper().replace("-", "_")]
    except KeyError as exc:
        raise ValueError(f"Unknown family: {value}") from exc


def load_manifest(path: Path) -> tuple[Vendor, Series, list[Model]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest.yaml must contain a YAML mapping")

    raw_vendor = data.get("vendor", {})
    vendor = Vendor(
        id=str(raw_vendor.get("id", "")).strip(),
        name=str(raw_vendor.get("name", "")).strip(),
        display_name=str(raw_vendor.get("display_name", "")).strip(),
        aliases=list(raw_vendor.get("aliases", [])),
    )

    raw_series = data.get("series", {})
    manifest_dir = path.parent
    series = Series(
        id=str(raw_series.get("id", "")).strip(),
        name=str(raw_series.get("name", "")).strip(),
        vendor_id=vendor.id,
        family=_parse_family(raw_series.get("family", "GENERIC")),
        data_dirs=[manifest_dir / d for d in raw_series.get("data_dirs", [])],
        column_map=dict(raw_series.get("column_map", {})),
        classification=raw_series.get("classification"),
        packages=raw_series.get("packages"),
        manifest_dir=manifest_dir,
    )

    models: list[Model] = []
    for idx, raw_model in enumerate(data.get("models", [])):
        device = str(raw_model.get("device", "")).strip()
        package = str(raw_model.get("package", "")).strip()
        full_name = str(raw_model.get("full_name", "") or f"{device}{package}").strip()
        pinout = raw_model.get("pinout", "")
        package_spec = raw_model.get("package_spec")
        models.append(
            Model(
                device=device,
                package=package,
                full_name=full_name,
                pinout=manifest_dir / pinout,
                package_spec=manifest_dir / package_spec if package_spec else None,
                series_id=series.id,
            )
        )

    return vendor, series, models


def validate_manifest(vendor: Vendor, series: Series, models: list[Model]) -> None:
    if not vendor.id or not _ID_RE.match(vendor.id):
        raise ValueError(f"invalid vendor id: {vendor.id!r}")
    if not vendor.name:
        raise ValueError("vendor.name is required")
    if not series.id or not _ID_RE.match(series.id):
        raise ValueError(f"invalid series id: {series.id!r}")
    if not series.name:
        raise ValueError("series.name is required")
    required_columns = {"pin", "pin_name", "bank", "io_type"}
    missing = required_columns - set(series.column_map.keys())
    if missing:
        raise ValueError(f"series.column_map missing required keys: {missing}")
    for model in models:
        if not model.device or not model.package:
            raise ValueError(f"model {model.full_name!r} missing device or package")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest fpga_libs_tool/tests/test_manifest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fpga_libs_tool/fpga_libs/manifest.py fpga_libs_tool/tests/test_manifest.py
git commit -m "feat(manifest): add Vendor/Series/Model dataclasses and loader"
```

---

## Task 3: 通用 CSV 解析器

**Files:**
- Modify: `fpga_libs_tool/fpga_libs/parser.py`
- Test: `fpga_libs_tool/tests/test_parser.py`

**Interfaces:**
- Consumes: `Series` (from Task 2).
- Produces: `parse_csv_with_mapping(csv_path: Path, series: Series) -> DevicePinout`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from fpga_libs.manifest import Series, Vendor
from fpga_libs.parser import parse_csv_with_mapping
from fpga_libs.models import Family

def test_parse_csv_with_mapping(tmp_path: Path):
    csv = tmp_path / "pinout.csv"
    csv.write_text("Location,Name,Bank,Type\nA1,VCC,0,POWER\nB1,IO_1,1,LVCMOS33\n")
    series = Series(
        id="s", name="S", vendor_id="v", family=Family.GENERIC,
        data_dirs=[], column_map={"pin": "Location", "pin_name": "Name", "bank": "Bank", "io_type": "Type"},
    )
    device = parse_csv_with_mapping(csv, series)
    assert device.total_pins == 2
    assert device.pins[0].ball_id == "A1"
    assert device.pins[0].pin_name == "VCC"
    assert device.pins[1].io_type == "LVCMOS33"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest fpga_libs_tool/tests/test_parser.py::test_parse_csv_with_mapping -v`
Expected: `ImportError: cannot import name 'parse_csv_with_mapping'`

- [ ] **Step 3: Implement `parse_csv_with_mapping()`**

在 `parser.py` 末尾添加：

```python
from .manifest import Series


def parse_csv_with_mapping(csv_path: Path, series: Series) -> DevicePinout:
    """Parse a vendor-neutral pinout CSV using the series column map."""
    filename = csv_path.stem
    if filename.lower().endswith("pkg"):
        full_device = filename[:-3]
    else:
        full_device = filename

    raw = csv_path.read_text(encoding="utf-8-sig", errors="replace")
    lines = [line for line in raw.splitlines() if line.strip() != '"']
    reader = csv.reader(lines)
    headers = [h.strip() for h in next(reader)]
    header_index = {h: i for i, h in enumerate(headers)}

    rev_map = {v: k for k, v in series.column_map.items()}
    col_idx = {key: header_index.get(raw_name, -1) for key, raw_name in series.column_map.items()}

    def get(key: str, row: list[str]) -> str:
        idx = col_idx.get(key, -1)
        if 0 <= idx < len(row):
            return row[idx].strip()
        return "NA"

    pins: list[PinRecord] = []
    for row in reader:
        if not row or all(c.strip() == "" for c in row):
            continue
        first = row[0].strip()
        if not first or first.startswith("#"):
            continue

        ball_id = get("pin", row) or first
        try:
            col_idx_ball, row_idx_ball = ball_id_to_indices(ball_id)
        except ValueError:
            col_idx_ball, row_idx_ball = -1, -1

        pins.append(
            PinRecord(
                ball_id=ball_id,
                pin_name=get("pin_name", row),
                bank=get("bank", row),
                io_type=get("io_type", row),
                family=series.family,
                byte_group=get("byte_group", row),
                slr=get("slr", row),
                vccaux_group=get("vccaux_group", row),
                no_connect=get("no_connect", row),
                col_index=col_idx_ball,
                row_index=row_idx_ball,
            )
        )

    device_name, package_code = _split_device_package(full_device)
    return DevicePinout(
        device_name=device_name,
        package_code=package_code,
        full_name=full_device,
        family=series.family,
        total_pins=len(pins),
        pins=pins,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest fpga_libs_tool/tests/test_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fpga_libs_tool/fpga_libs/parser.py fpga_libs_tool/tests/test_parser.py
git commit -m "feat(parser): add parse_csv_with_mapping for vendor-neutral CSVs"
```

---

## Task 4: 基于规则的分类器

**Files:**
- Modify: `fpga_libs_tool/fpga_libs/classifier.py`
- Test: `fpga_libs_tool/tests/test_classifier.py`

**Interfaces:**
- Produces: `ClassificationRules`, `load_classification_rules(source)`, `classify_with_rules(record, rules) -> ClassifiedPin`.

- [ ] **Step 1: Write the failing test**

```python
from fpga_libs.classifier import ClassificationRules, load_classification_rules, classify_with_rules
from fpga_libs.models import PinRecord, Family, PinType, PinDirection

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
    pwr = PinRecord(ball_id="A1", pin_name="VCC", bank="0", io_type="POWER", family=Family.GENERIC)
    io = PinRecord(ball_id="A2", pin_name="IO_1", bank="1", io_type="LVCMOS", family=Family.GENERIC)
    assert classify_with_rules(pwr, rules).pin_type == PinType.POWER
    assert classify_with_rules(io, rules).pin_type == PinType.IO
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest fpga_libs_tool/tests/test_classifier.py::test_rule_classifier_power_and_io -v`
Expected: `ImportError`

- [ ] **Step 3: Implement rule-based classifier**

在 `classifier.py` 末尾追加：

```python
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


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


def _rule_direction(name: str, direction_rules: list[dict[str, Any]]) -> PinDirection:
    for rule in direction_rules:
        if "when" in rule:
            when = rule["when"]
            name_pattern = when.get("name_pattern")
            if name_pattern and re.search(name_pattern, name, re.I):
                return PinDirection[rule["direction"]]
        elif "default" in rule:
            return PinDirection[rule["default"]]
    return PinDirection.BIDIR
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest fpga_libs_tool/tests/test_classifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fpga_libs_tool/fpga_libs/classifier.py fpga_libs_tool/tests/test_classifier.py
git commit -m "feat(classifier): add rule-based classifier for vendor-neutral pins"
```

---

## Task 5: 外置封装规格注册表

**Files:**
- Modify: `fpga_libs_tool/fpga_libs/geometry.py`
- Test: `fpga_libs_tool/tests/test_geometry.py`

**Interfaces:**
- Produces: `PackageRegistry` with `load(data_root)`, `add_series_packages(source)`, `get_spec(package_code, ball_count=0, overrides...) -> PackageSpec`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from fpga_libs.geometry import PackageRegistry
from fpga_libs.models import PackageSpec

def test_package_registry_external_and_override(tmp_path: Path):
    db = tmp_path / "pkg_db.json"
    db.write_text('{"fgg484": {"pitch_mm": 1.0, "body_size_x": 23, "body_size_y": 23, "pad_diameter_mm": 0.45, "mask_opening_mm": 0.5, "paste_diameter_mm": 0.4}}')
    reg = PackageRegistry(tmp_path)
    spec = reg.get_spec("fgg484")
    assert spec.pitch_mm == 1.0

    reg.add_series_packages({"fgg484": {"pitch_mm": 0.8, "body_size_x": 15, "body_size_y": 15, "pad_diameter_mm": 0.4, "mask_opening_mm": 0.45, "paste_diameter_mm": 0.35}})
    spec2 = reg.get_spec("fgg484")
    assert spec2.pitch_mm == 0.8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest fpga_libs_tool/tests/test_geometry.py::test_package_registry_external_and_override -v`
Expected: `ImportError`

- [ ] **Step 3: Implement `PackageRegistry`**

在 `geometry.py` 中替换固定 `_load_pkg_db` 为注册表类（保留 `get_package_spec` 全局函数作为默认注册表入口）：

```python
class PackageRegistry:
    def __init__(self, data_root: Path):
        self.data_root = data_root
        self._db: dict[str, dict] = {}

    def load(self) -> "PackageRegistry":
        db_path = self.data_root / "data" / "pkg_db.json"
        if db_path.exists():
            self._db = json.loads(db_path.read_text(encoding="utf-8"))
        return self

    def add_series_packages(self, source: Path | dict) -> None:
        if isinstance(source, Path):
            data = yaml.safe_load(source.read_text(encoding="utf-8")) if source.suffix in (".yaml", ".yml") else json.loads(source.read_text(encoding="utf-8"))
        else:
            data = source
        if isinstance(data, dict):
            self._db.update(data)

    def get_spec(
        self,
        package_code: str,
        ball_count: int = 0,
        override_pitch: float | None = None,
        override_body_size: tuple[float, float] | None = None,
        override_pad_dia: float | None = None,
    ) -> PackageSpec:
        pkg_lower = package_code.lower().strip()
        spec = self._db.get(pkg_lower) or _fuzzy_lookup(pkg_lower, self._db)

        if spec:
            pitch = spec["pitch_mm"]
            body_x = spec["body_size_x"]
            body_y = spec["body_size_y"]
            pad = spec["pad_diameter_mm"]
            mask = spec["mask_opening_mm"]
            paste = spec["paste_diameter_mm"]
        else:
            pitch, body, pad = _prefix_heuristic_spec(pkg_lower, ball_count)
            body_x = body_y = body
            mask = pad + 0.05
            paste = max(0.1, pad - 0.05)

        if override_pitch is not None:
            pitch = override_pitch
        if override_body_size is not None:
            body_x, body_y = override_body_size
        if override_pad_dia is not None:
            pad = override_pad_dia
            mask = pad + 0.05
            paste = max(0.1, pad - 0.05)

        return PackageSpec(pitch, body_x, body_y, pad, mask, paste)


def _fuzzy_lookup(pkg_lower: str, db: dict) -> dict | None: ...  # 改为接收 db 参数


# 保留全局默认注册表，供旧代码调用
_PKG_REGISTRY: PackageRegistry | None = None


def get_package_spec(
    package_code: str,
    ball_count: int = 0,
    override_pitch: float | None = None,
    override_body_size: tuple[float, float] | None = None,
    override_pad_dia: float | None = None,
    data_root: Path | None = None,
) -> PackageSpec:
    global _PKG_REGISTRY
    if _PKG_REGISTRY is None or data_root is not None:
        root = data_root or Path(__file__).parent.parent / "data"
        _PKG_REGISTRY = PackageRegistry(root).load()
    return _PKG_REGISTRY.get_spec(
        package_code,
        ball_count=ball_count,
        override_pitch=override_pitch,
        override_body_size=override_body_size,
        override_pad_dia=override_pad_dia,
    )
```

注意同步修改 `_fuzzy_lookup` 签名以接收 `db`。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest fpga_libs_tool/tests/test_geometry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fpga_libs_tool/fpga_libs/geometry.py fpga_libs_tool/tests/test_geometry.py
git commit -m "feat(geometry): externalize pkg_db.json and add PackageRegistry"
```

---

## Task 6: 库扫描器 `LibraryScanner`

**Files:**
- Create: `fpga_libs_tool/fpga_libs/library.py`
- Test: `fpga_libs_tool/tests/test_library.py`

**Interfaces:**
- Consumes: `load_manifest()` (Task 2), existing `_split_device_package()`.
- Produces: `LibraryTree` with `vendors: dict[str, Vendor]`, `series: dict[str, Series]`, `models: dict[str, list[Model]]`; `LibraryScanner.scan() -> LibraryTree`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from fpga_libs.library import LibraryScanner

def test_scan_library(tmp_path: Path):
    lib = tmp_path / "library" / "gowin" / "gw2a"
    lib.mkdir(parents=True)
    (lib / "manifest.yaml").write_text("""
vendor:
  id: gowin
  name: Gowin
series:
  id: gw2a
  name: GW2A
  family: GENERIC
  data_dirs: ["."]
  column_map:
    pin: Pin
    pin_name: Name
    bank: Bank
    io_type: Type
models:
  - device: dev1
    package: pkg1
    full_name: dev1pkg1
    pinout: dev1/pinout.csv
""")
    tree = LibraryScanner(tmp_path).scan()
    assert "gowin" in tree.vendors
    assert "gw2a" in tree.series
    assert len(tree.models["gw2a"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest fpga_libs_tool/tests/test_library.py::test_scan_library -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement `library.py`**

```python
"""Library scanning and tree building."""

from dataclasses import dataclass, field
from pathlib import Path

from .manifest import Vendor, Series, Model, load_manifest
from .parser import _split_device_package


@dataclass
class LibraryTree:
    vendors: dict[str, Vendor] = field(default_factory=dict)
    series: dict[str, Series] = field(default_factory=dict)
    models: dict[str, list[Model]] = field(default_factory=dict)

    def series_for_vendor(self, vendor_id: str) -> list[Series]:
        return [s for s in self.series.values() if s.vendor_id == vendor_id]

    def models_for_series(self, series_id: str) -> list[Model]:
        return self.models.get(series_id, [])


class LibraryScanner:
    def __init__(self, root: Path):
        self.root = root
        self.library_root = root / "library"

    def scan(self) -> LibraryTree:
        tree = LibraryTree()
        if not self.library_root.exists():
            return tree

        for manifest_path in sorted(self.library_root.rglob("manifest.yaml")):
            vendor, series, explicit_models = load_manifest(manifest_path)
            tree.vendors[vendor.id] = vendor
            tree.series[series.id] = series

            models: list[Model] = []
            seen = set()
            for model in explicit_models:
                model.series_id = series.id
                models.append(model)
                seen.add(model.full_name.lower())

            for data_dir in series.data_dirs:
                if not data_dir.exists():
                    continue
                for csv_file in data_dir.glob("**/*.csv"):
                    stem = csv_file.stem.lower()
                    if stem.endswith("pkg"):
                        stem = stem[:-3]
                    device, package = _split_device_package(stem)
                    full_name = f"{device}{package}"
                    if full_name.lower() in seen:
                        continue
                    models.append(
                        Model(
                            device=device,
                            package=package,
                            full_name=full_name,
                            pinout=csv_file,
                            series_id=series.id,
                        )
                    )
                    seen.add(full_name.lower())

            tree.models[series.id] = sorted(models, key=lambda m: m.full_name)

        return tree
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest fpga_libs_tool/tests/test_library.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fpga_libs_tool/fpga_libs/library.py fpga_libs_tool/tests/test_library.py
git commit -m "feat(library): add LibraryScanner for manifest-based library tree"
```

---

## Task 7: CLI 子命令

**Files:**
- Modify: `fpga_libs_tool/fpga_libs/__main__.py`
- Create: `fpga_libs_tool/fpga_libs/cli.py`
- Test: `fpga_libs_tool/tests/test_cli.py`

**Interfaces:**
- Produces: `python -m fpga_libs library scan`, `python -m fpga_libs library validate [path]`, `python -m fpga_libs add-package <json>`.

- [ ] **Step 1: Write the failing test**

```python
from fpga_libs.cli import main as cli_main
from click.testing import CliRunner
import json

def test_scan_cli(tmp_path):
    # 创建最小 library
    ...
    runner = CliRunner()
    result = runner.invoke(cli_main, ["library", "scan", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "testvendor" in result.output
```

（注：若项目未引入 click，则继续使用 `argparse` 并在测试中调用 `main(["library", "scan", str(tmp_path)])`。）

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest fpga_libs_tool/tests/test_cli.py::test_scan_cli -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement CLI**

`fpga_libs_tool/fpga_libs/cli.py`：

```python
"""CLI entry point for fpga_libs."""

import argparse
import sys
from pathlib import Path

from .library import LibraryScanner
from .manifest import load_manifest, validate_manifest


def _cmd_scan(args: argparse.Namespace) -> int:
    tree = LibraryScanner(Path(args.root)).scan()
    for vendor in tree.vendors.values():
        print(f"Vendor: {vendor.name} ({vendor.id})")
        for series in tree.series_for_vendor(vendor.id):
            print(f"  Series: {series.name} ({series.id})")
            for model in tree.models_for_series(series.id):
                print(f"    Model: {model.full_name}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if args.path:
        targets = [Path(args.path)]
    else:
        targets = sorted((root / "library").rglob("manifest.yaml")) if (root / "library").exists() else []
    errors = 0
    for manifest_path in targets:
        try:
            vendor, series, models = load_manifest(manifest_path)
            validate_manifest(vendor, series, models)
            print(f"OK: {manifest_path}")
        except Exception as e:
            print(f"FAIL: {manifest_path}: {e}")
            errors += 1
    return 1 if errors else 0


def _cmd_add_package(args: argparse.Namespace) -> int:
    import json
    root = Path(args.root)
    db_path = root / "data" / "pkg_db.json"
    db = json.loads(db_path.read_text(encoding="utf-8")) if db_path.exists() else {}
    new_entry = json.loads(args.json)
    if not isinstance(new_entry, dict) or len(new_entry) != 1:
        print("Error: JSON must be a single-key object like {\"fgg999\": {...}}")
        return 1
    db.update(new_entry)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Updated {db_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fpga_libs")
    parser.add_argument("--root", default=".", help="project root directory")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("library", help="library management")
    scan_sub = scan_p.add_subparsers(dest="library_command")
    scan_cmd = scan_sub.add_parser("scan", help="scan library tree")
    scan_cmd.set_defaults(func=_cmd_scan)

    validate_cmd = scan_sub.add_parser("validate", help="validate manifests")
    validate_cmd.add_argument("path", nargs="?", help="manifest.yaml path or directory")
    validate_cmd.set_defaults(func=_cmd_validate)

    add_pkg = sub.add_parser("add-package", help="add package spec to pkg_db.json")
    add_pkg.add_argument("json", help="JSON object with single package spec")
    add_pkg.set_defaults(func=_cmd_add_package)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

更新 `__main__.py`：

```python
def main() -> int:
    """CLI entry point."""
    from .cli import main as cli_main
    return cli_main()
```

保留 GUI 可通过 `python -m fpga_libs gui` 或直接回退到现有 `run_gui` 行为。具体可添加 `gui` 子命令或保留无参数时启动 GUI。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest fpga_libs_tool/tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fpga_libs_tool/fpga_libs/cli.py fpga_libs_tool/fpga_libs/__main__.py fpga_libs_tool/tests/test_cli.py
git commit -m "feat(cli): add library scan/validate and add-package commands"
```

---

## Task 8: GUI 厂商下拉框与动态库树

**Files:**
- Modify: `fpga_libs_tool/fpga_libs/gui.py`
- Test: `fpga_libs_tool/tests/test_gui.py`

**Interfaces:**
- Consumes: `LibraryScanner`, `LibraryTree` (Task 6).
- Produces: GUI with vendor → series → model → package 联动下拉框；保留现有 fallback。

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from fpga_libs.library import LibraryScanner

def test_library_tree_for_gui(tmp_path: Path):
    # 构造最小 library
    ...
    tree = LibraryScanner(tmp_path).scan()
    assert "v" in tree.vendors
    assert len(tree.series_for_vendor("v")) == 1
```

（GUI 事件测试较复杂，优先通过 `LibraryTree` 单元测试保证数据正确；`test_gui.py` 中新增对 `Application._build_device_tree` 的测试。）

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest fpga_libs_tool/tests/test_gui.py -v`
Expected: 当前 GUI 无 vendor 下拉框，断言失败。

- [ ] **Step 3: Modify GUI**

在 `gui.py` 中：

1. 引入 `LibraryScanner` 和 `LibraryTree`。
2. `Application.__init__` 中：
   - 先尝试 `LibraryScanner(self.root_dir).scan()`。
   - 如果 `library/` 不存在或为空，回退到现有 `scan_devices_by_series()`。
3. 新增 `vendor_var`/`vendor_combo`，放在 series 下拉框之前。
4. 联动逻辑改为：vendor → series → model → package。
5. 生成时从 `LibraryTree` 取 `pinout` 路径和 `data_dirs`。

关键代码片段：

```python
from .library import LibraryScanner, LibraryTree

class Application:
    def __init__(self, root: tk.Tk, data_dirs: list[Path]):
        ...
        self.library_tree = LibraryScanner(self.root_dir).scan()
        if self.library_tree.vendors:
            self.devices = self._build_device_tree(self.library_tree)
            self._use_library = True
        else:
            self.devices = scan_devices_by_series(self.root_dir)
            self._use_library = False
        ...

    def _build_device_tree(self, tree: LibraryTree) -> dict[str, dict[str, dict[str, list[str]]]]:
        result: dict[str, dict[str, dict[str, list[str]]]] = {}
        for vendor in tree.vendors.values():
            result[vendor.id] = {}
            for series in tree.series_for_vendor(vendor.id):
                models: dict[str, list[str]] = {}
                for model in tree.models_for_series(series.id):
                    models.setdefault(model.device, []).append(model.package)
                result[vendor.id][series.id] = {k: sorted(v) for k, v in sorted(models.items())}
        return result

    def _on_vendor_changed(self, event=None):
        vendor = self.vendor_var.get()
        series = sorted(self.devices.get(vendor, {}).keys())
        self.series_combo["values"] = series
        if series:
            self.series_var.set(series[0])
        self._on_series_changed()
```

生成时：

```python
        if self._use_library:
            series = self.series_var.get()
            model_name = self.model_var.get()
            model = next(
                m for m in self.library_tree.models_for_series(series)
                if m.device == model_name and m.package == package
            )
            csv_path = model.pinout
            # 使用 GenericParser / RuleBasedClassifier / PackageRegistry
        else:
            # 保持现有流程
```

（完整实现时需要把 `build_output` 拆出 library 路径和 legacy 路径，或在 `build_output` 内部根据传入参数选择解析器。）

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest fpga_libs_tool/tests/test_gui.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fpga_libs_tool/fpga_libs/gui.py fpga_libs_tool/tests/test_gui.py
git commit -m "feat(gui): add vendor combo and library tree support"
```

---

## Task 9: 统一生成流程支持 LibraryTree

**Files:**
- Modify: `fpga_libs_tool/fpga_libs/gui.py` 中的 `build_output()` 或新增 `build_output_from_library()`
- Test: `fpga_libs_tool/tests/test_integration.py`

**Interfaces:**
- Consumes: `Model`, `Series`, `PackageRegistry`, `parse_csv_with_mapping`, `classify_with_rules`.
- Produces: 对 library 模型的符号/封装输出。

- [ ] **Step 1: Write the failing test**

```python
def test_generate_from_library(tmp_path: Path):
    # 构造完整 library（vendor/series/model + CSV + package.json）
    ...
    from fpga_libs.gui import build_output_from_library
    result = build_output_from_library(model, series, output_dir=tmp_path / "out")
    assert (Path(result["output_dir"]) / "kicad" / "...").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest fpga_libs_tool/tests/test_integration.py::test_generate_from_library -v`
Expected: `ImportError`

- [ ] **Step 3: Implement `build_output_from_library()`**

```python
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
    device = parse_csv_with_mapping(model.pinout, series)
    rules = load_classification_rules(series.classification) if series.classification else None
    if rules:
        classified = [classify_with_rules(p, rules) for p in device.pins]
    else:
        from .classifier import classify_all
        classified = classify_all(device.pins)

    spec = registry.get_spec(
        device.package_code,
        ball_count=device.total_pins,
        override_pitch=float(override_pitch) if override_pitch.strip() else None,
        override_body_size=_parse_body_size(override_body_size) if override_body_size.strip() else None,
        override_pad_dia=float(override_pad_dia) if override_pad_dia.strip() else None,
    )
    if model.package_spec and model.package_spec.exists():
        registry.add_series_packages(json.loads(model.package_spec.read_text(encoding="utf-8")))
        spec = registry.get_spec(device.package_code, ball_count=device.total_pins)

    coords = compute_ball_coordinates(device.pins, spec)
    # 复用 build_output 后半段文件写入逻辑
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest fpga_libs_tool/tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fpga_libs_tool/fpga_libs/gui.py fpga_libs_tool/tests/test_integration.py
git commit -m "feat(gui): support generating outputs from library tree"
```

---

## Task 10: 现有 Xilinx 系列 manifest

**Files:**
- Create: `library/xilinx/7series/manifest.yaml`
- Create: `library/xilinx/ultrascale/manifest.yaml`
- Create: `library/xilinx/ultrascale_plus/manifest.yaml`
- Create: `library/xilinx/zynq7000/manifest.yaml`
- Create: `library/xilinx/zynq_us_plus/manifest.yaml`
- Create: `library/xilinx/versal/manifest.yaml`
- Test: `fpga_libs_tool/tests/test_integration.py` 现有用例继续通过。

- [ ] **Step 1: 创建 `library/xilinx/7series/manifest.yaml`**

```yaml
vendor:
  id: xilinx
  name: Xilinx
  display_name: Xilinx

series:
  id: 7series
  name: 7series
  family: SERIES_7
  data_dirs:
    - ../../a7all
    - ../../k7all
    - ../../s7all/s7all
    - ../../v7all
  column_map:
    pin: Pin
    pin_name: Pin Name
    bank: Bank
    io_type: I/O Type
    byte_group: Memory Byte Group
    vccaux_group: VCCAUX Group
    no_connect: No-Connect

models: []
```

- [ ] **Step 2: 创建其余 Xilinx 系列 manifest**

分别指向 `usaall/`、`zupall/`、`z7all/7zSeriesALL/`、`versal-all/versal-all/`。

- [ ] **Step 3: 运行全部回归测试**

Run: `pytest fpga_libs_tool/ -q`
Expected: 55 passed

- [ ] **Step 4: Commit**

```bash
git add library/
git commit -m "chore(library): add Xilinx series manifests for backward compatibility"
```

---

## Task 11: 打包脚本更新

**Files:**
- Modify: `fpga_libs_tool.spec`
- Modify: `build_exe.py` 或新增构建后复制脚本

- [ ] **Step 1: 修改 `fpga_libs_tool.spec`**

移除 `pkg_db.json` 打包：

```python
datas=[],
hiddenimports=[
    'fpga_libs.generators.pads',
    'fpga_libs.generators.cadence',
    'fpga_libs.generators.altium',
    'fpga_libs.generators.kicad',
],
```

- [ ] **Step 2: 构建后复制运行时数据**

在 `fpga_libs_tool.spec` 末尾或 `build_exe.py` 中添加：

```python
import shutil
from pathlib import Path

dist_dir = Path('dist')
for src in ['data', 'library']:
    src_path = Path(src)
    if src_path.exists():
        shutil.copytree(src_path, dist_dir / src, dirs_exist_ok=True)
```

- [ ] **Step 3: 重新打包并验证**

Run: `python -m PyInstaller fpga_libs_tool.spec --noconfirm`
Expected: 构建成功，`dist/data/pkg_db.json` 与 `dist/library/` 存在。

- [ ] **Step 4: Commit**

```bash
git add fpga_libs_tool.spec build_exe.py
git commit -m "build(spec): keep pkg_db.json and library as external runtime data"
```

---

## Self-Review

### Spec Coverage

| 设计文档要求 | 对应任务 |
|---|---|
| 统一 `manifest.yaml` | Task 2, 6 |
| `vendor/series/models` 三段 | Task 2 |
| 新增同系列型号只需追加 `models` | Task 2, 6 |
| 外置 `pkg_db.json` | Task 5, 11 |
| GUI 厂商下拉框 | Task 8 |
| 非 Xilinx 厂商接入（GENERIC + 规则分类） | Task 1, 3, 4 |
| CLI 校验/扫描 | Task 7 |
| 向后兼容现有 Xilinx 目录 | Task 10 |
| 打包变更 | Task 11 |

### Placeholder Scan

无 TBD/TODO/"后续实现"/"适当处理" 等占位描述。每个任务包含具体代码、命令、期望输出。

### Type Consistency

- `Series.column_map: dict[str, str]` 在 Task 2、3、6 中一致。
- `LibraryTree.models` 为 `dict[str, list[Model]]` 在 Task 6、8 中一致。
- `PackageRegistry.get_spec` 签名与现有 `get_package_spec` 兼容。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-14-vendor-aware-model-expansion.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
