# 厂商感知型型号扩展接口 — 实现报告

**Date:** 2026-07-14  
**Project:** E:/1_work/16_pinout (PolyLibs)  
**Final test result:** `pytest PolyLibs/ -q` → **70 passed**

---

## 任务清单与状态

| Task | 目标 | 状态 | 关键文件 | 验证结果 |
|---|---|---|---|---|
| 1 | 扩展 `Family` 枚举，新增 `GENERIC` | ✅ 完成 | `PolyLibs/polylibs/models.py`, `tests/test_models.py` | `test_family_has_generic` PASS |
| 2 | Manifest 数据模型与解析 | ✅ 完成 | `PolyLibs/polylibs/manifest.py`, `tests/test_manifest.py` | 3/3 PASS |
| 3 | 通用 CSV 解析器 | ✅ 完成 | `PolyLibs/polylibs/parser.py`, `tests/test_parser.py` | 13/13 PASS |
| 4 | 基于规则的分类器 | ✅ 完成 | `PolyLibs/polylibs/classifier.py`, `tests/test_classifier.py` | 10/10 PASS |
| 5 | 外置封装规格注册表 | ✅ 完成 | `PolyLibs/polylibs/geometry.py`, `tests/test_geometry.py` | 9/9 PASS |
| 6 | 库扫描器 `LibraryScanner` | ✅ 完成 | `PolyLibs/polylibs/library.py`, `tests/test_library.py` | 2/2 PASS |
| 7 | CLI 子命令 | ✅ 完成 | `PolyLibs/polylibs/cli.py`, `PolyLibs/polylibs/__main__.py`, `tests/test_cli.py` | 4/4 PASS |
| 8 | GUI 厂商下拉框与动态库树 | ✅ 完成 | `PolyLibs/polylibs/gui.py`, `tests/test_gui.py` | 4/4 PASS |
| 9 | 统一生成流程支持 LibraryTree | ✅ 完成 | `PolyLibs/polylibs/gui.py`, `tests/test_integration.py` | 4/4 PASS |
| 10 | 现有 Xilinx 系列 manifest | ✅ 完成 | `library/xilinx/*/manifest.yaml` | 全量回归 70 PASS |
| 11 | 打包脚本更新 | ✅ 完成 | `PolyLibs.spec` | `py_compile` 通过 |

---

## 各任务关键变更

### Task 1
- 在 `Family` 枚举中加入 `GENERIC = auto()`。
- 新增 `test_family_has_generic` 断言其存在与名称。

### Task 2
- 新增 `manifest.py`，定义 `Vendor`、`Series`、`Model` 数据类。
- 实现 `load_manifest()` 与 `validate_manifest()`，支持 `vendor/series/models` 三段 YAML。
- `series.family` 通过 `Family[value.upper().replace("-", "_")]` 解析，兼容 `GENERIC` 与现有 Xilinx family。
- 新增 `test_manifest.py`：最小加载、缺失必填列、非法 vendor id。
- 更新 `requirements.txt`：加入 `PyYAML>=6.0` 并安装 PyYAML 6.0.3。

### Task 3
- `parser.py` 新增 `parse_csv_with_mapping(csv_path, series)`，按 `series.column_map` 读取 CSV。
- 保留现有 `parse_csv()` 不变，确保现有 535 个 Xilinx 模型零迁移。
- 新增 `test_parse_csv_with_mapping`。

### Task 4
- `classifier.py` 新增 `ClassificationRules`、`load_classification_rules()`、`classify_with_rules()`。
- 规则匹配顺序：`power → ground → nc → config → mgt → analog`，未命中归为 `IO`。
- `direction_rules` 支持 `when` 条件与 `default`，并兼容 `BIDIRECTIONAL`/`BIDIR` 等值/名。
- 新增 `test_rule_classifier_power_and_io`。

### Task 5
- `geometry.py` 引入 `PackageRegistry`：从 `<data_root>/data/pkg_db.json` 加载，并支持系列级/型号级覆盖。
- 保留全局 `get_package_spec()` 作为旧代码入口，默认注册表指向 `PolyLibs/data`。
- `_fuzzy_lookup` 改为接收 `db` 参数，便于注册表复用。
- 新增 `test_package_registry_external_and_override`。

### Task 6
- 新增 `library.py`，实现 `LibraryScanner` 与 `LibraryTree`。
- 扫描 `library/**/manifest.yaml`；`models` 显式条目优先，`data_dirs` 自动派生其余型号。
- 新增 `test_scan_library` 与无 library 回退测试。

### Task 7
- 新增 `cli.py`：
  - `polylibs library scan`
  - `polylibs library validate [path]`
  - `polylibs add-package <json>`
  - `polylibs gui`
  - 无参数时仍启动 GUI，保持历史行为。
- `__main__.py` 改为调用 `cli.main()`。
- 新增 `test_cli.py` 覆盖扫描、校验、坏 manifest、新增封装。
- **实现偏差**：`--root` 放在子命令之后（如 `library scan --root .`），避免 argparse 父解析器默认值覆盖顶层值。

### Task 8
- `gui.py` 的 `Application` 启动时扫描 `library/`。
- 存在 library 时按 `vendor → series → model → package` 构建联动下拉框；否则回退到 `_SERIES_DIR_MAP` 并以单厂商 `Xilinx` 展示。
- 新增 `_build_device_tree`、`_on_vendor_changed` 等回调。
- 新增 `test_build_device_tree_for_gui`。

### Task 9
- `gui.py` 新增 `build_output_from_library()`，使用 `parse_csv_with_mapping`、`classify_with_rules`、模型级 `package.json` 覆盖。
- 将文件写入逻辑抽取为 `_write_generated_files()`，供 `build_output` 与 `build_output_from_library` 复用。
- 新增 `test_generate_from_library` 完整端到端验证。

### Task 10
- 在 `library/xilinx/` 下创建 6 个 manifest：
  - `7series` → `a7all`, `k7all`, `s7all/s7all`, `v7all`
  - `ultrascale` → `usaall`
  - `ultrascale_plus` → `usaall`
  - `zynq7000` → `z7all/7zSeriesALL`
  - `zynq_us_plus` → `zupall`
  - `versal` → `versal-all/versal-all`
- 各 manifest 的 `column_map` 与该系列 CSV 实际表头一致。

### Task 11
- `PolyLibs.spec`：
  - 移除 `('PolyLibs/data', 'data')`，不再把 `pkg_db.json` 打包进 exe。
  - `hiddenimports` 增加 `'yaml'`。
  - 在 spec 末尾加入构建后复制 `data/` 与 `library/` 到 `dist/` 的逻辑。
- `python -m py_compile PolyLibs.spec` 通过。

---

## 额外修复

### `_split_device_package` 单字符 package code 问题
在回归测试中发现 `pkg_db.json` 存在单字符键 `'a'`，导致 `xc7s50csga324` 与 `xcku035fbva900` 等设备被错误拆分（优先匹配到 `'a'`）。
- 在 `_load_pkg_codes()` 中过滤掉长度 `< 2` 的键，消除噪声。
- 该修复使 `test_split_device_package` 全部通过，且不影响现有功能。

---

## 验证记录

```text
$ python -m pytest PolyLibs/ -q
......................................................................   [100%]
70 passed in 0.49s
```

关键子命令验证：

```text
$ cd PolyLibs && python -m polylibs library scan --root ..
Vendor: Xilinx (xilinx)
  Series: 7series (7series)
  Series: ultrascale (ultrascale)
  Series: ultrascale_plus (ultrascale_plus)
  Series: versal (versal)
  Series: zynq7000 (zynq7000)
  Series: zynq_us_plus (zynq_us_plus)
```

---

## 未完成/待跟进

- ✅ 已修复：GUI 生成流程在选中 library 显式 model 时调用 `build_output_from_library()`，支持非 Xilinx 厂商的自定义列名与分类规则。
- ✅ 已修复：`manifest.yaml` 的 `data_dirs` 改为相对于项目根目录解析，并同步修正所有 `library/xilinx/*/manifest.yaml` 中的路径；之前因路径解析错误导致型号/封装下拉框为空。
- ✅ 已新增：封装下拉框切换时，自动把「球间距 / 封装尺寸 / 焊盘直径」高级选项填充为该封装的默认值，方便用户确认。
- ✅ 已重新构建 `dist/PolyLibs.exe`；`dist/data/` 与 `dist/library/` 已随 spec 的后构建脚本复制到输出目录。
- 新厂商的 `classification_rules.yaml` / `packages.yaml` 独立文件支持已在代码中实现，模板见 `docs/superpowers/specs/templates/`。
