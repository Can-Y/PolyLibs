# 厂商感知型型号扩展接口设计

**Date:** 2026-07-14  
**Project:** E:/1_work/16_pinout (PolyLibs)  
**Status:** Design approved, pending implementation plan  

## 1. 背景与目标

当前 `PolyLibs` 已经能做到把器件引脚表（CSV）作为运行时数据扫描，但新增一个**新厂商/新封装/新系列**时，仍然会碰到以下需要重新编译 exe 的耦合点：

- `PolyLibs/data/pkg_db.json` 被 PyInstaller 打包进 exe。
- 系列/数据目录映射 `_SERIES_DIR_MAP` 在 `PolyLibs/polylibs/gui.py` 和 `PolyLibs_gui.py` 中写死。
- CSV 格式探测和引脚分类规则都是按 Xilinx 家族硬编码。

本设计的目标：

1. **新增型号不需要重新编译/封装 exe**：把封装规格、系列目录、列名映射、分类规则全部抽出为运行时配置文件。
2. **下拉框支持厂商品牌层级**：厂商 → 系列 → 型号 → 封装。
3. **非 Xilinx 厂商可接入**：Altera、Lattice、高云、紫光等同创等，只要按标准提供配置文件即可被识别。
4. **对现有 535 个 Xilinx 模型零迁移成本**：现有目录和 CSV 保持不动，通过新的 `library/` 配置指向它们。

## 2. 术语

| 术语 | 含义 |
|---|---|
| Vendor | 厂商品牌，如 `Xilinx`、`Altera`、`Gowin`。 |
| Series | 厂商下的产品系列，如 `7series`、`Cyclone V`、`GW2A`。 |
| Model | 一个器件型号，如 `xc7a100t`、`5cgxfc7d6f31c8`。 |
| Package | 封装代码，如 `fgg484`、`f484`。 |
| Full name | 器件 + 封装，如 `xc7a100tfgg484`。 |
| Library | 整个可扩展数据根的根目录 `library/`。 |

## 3. 现状

关键文件与耦合点：

- `PolyLibs.spec:8`：`datas=[('PolyLibs/data','data')]` 把 `pkg_db.json` 打进 exe。
- `PolyLibs/polylibs/gui.py:36`：`_SERIES_DIR_MAP` 写死系列目录。
- `PolyLibs/polylibs/parser.py:47`：`detect_format()` 按 Xilinx 三种家族探测 CSV 头。
- `PolyLibs/polylibs/classifier.py`：POWER/GROUND/CONFIG/MGT/ANALOG/NC 规则全部硬编码为 Xilinx 命名习惯。
- `PolyLibs/polylibs/__main__.py` 和 `PolyLibs_gui.py:19`：启动时构造的 `data_dirs` 列表写死。

## 4. 方案概述

采用**方案 C：分厂商清单 + 外置 `pkg_db.json`**。

核心思想：

- 在项目根目录新增 `library/`，每个厂商/系列目录下放一个**统一的 `manifest.yaml`**。
- `manifest.yaml` 内分三段：`vendor`、`series`、`models`，通过关键字识别。
- `series` 段声明：数据目录、列名映射、分类规则、封装规格文件。
- `models` 段是一个列表，每一项指向该系列下的一个型号：device、package、pinout.csv、package.json。
- 后续新增同一厂商/系列的型号，**只需在 `models` 段追加一条**，并把 `pinout.csv`/`package.json` 放到对应路径，无需重复写 vendor/series 段。
- 模型数据仍用 CSV，解析时按 `column_map`（key 为内部 canonical 字段，value 为 CSV 实际列名）映射；新增封装可直接在 `data/pkg_db.json`、系列级 `packages.yaml` 或型号级 `package.json` 中补充。
- GUI/CLI 启动时扫描 `library/**/manifest.yaml`，动态构建厂商 → 系列 → 型号 → 封装树。

## 5. 目录与文件结构

```text
E:/1_work/16_pinout/
├── a7all/                          # 现有数据不动
├── k7all/
├── s7all/s7all/
├── v7all/
├── usaall/
├── zupall/
├── z7all/7zSeriesALL/
├── versal-all/versal-all/
├── data/                           # 运行时数据根
│   ├── pkg_db.json                 # 外置封装几何数据库（不再打包进 exe）
│   └── library.yaml                # 可选：库根入口，可指向 library/
├── library/                        # 新的可扩展库根
│   ├── xilinx/
│   │   ├── 7series/
│   │   │   ├── manifest.yaml       # 包含 vendor + series + models
│   │   │   └── ...                 # 也可直接放 CSV
│   │   ├── ultrascale/
│   │   │   └── manifest.yaml
│   │   ├── ultrascale_plus/
│   │   │   └── manifest.yaml
│   │   ├── zynq7000/
│   │   │   └── manifest.yaml
│   │   ├── zynq_us_plus/
│   │   │   └── manifest.yaml
│   │   └── versal/
│   │       └── manifest.yaml
│   ├── altera/
│   │   └── cyclonev/
│   │       ├── manifest.yaml
│   │       └── 5cgxfc7d6f31c8/
│   │           ├── pinout.csv
│   │           └── package.json
│   ├── gowin/
│   │   └── gw2a/
│   │       ├── manifest.yaml
│   │       └── gw2a-lv55pg484/
│   │           ├── pinout.csv
│   │           └── package.json
│   └── unisoc/                     # 紫光同创示例
│       └── ...
├── docs/superpowers/specs/templates/  # 用户模板
└── PolyLibs/...
```

## 6. 配置文件标准

### 6.1 `manifest.yaml`（唯一必需的配置文件）

每个厂商/系列目录下放一个 `manifest.yaml`，内部通过 `vendor`、`series`、`models` 三个关键字识别。

```yaml
vendor:
  id: gowin
  name: Gowin
  display_name: 高云半导体
  aliases: [gowinsemi]

series:
  id: gw2a
  name: GW2A
  family: GENERIC         # 非 Xilinx 新厂商填 GENERIC；Xilinx 可填 SERIES_7/ULTRASCALE/ULTRASCALE_PLUS
  data_dirs:              # 相对 manifest.yaml 的路径；也可指向现有目录
    - .
  column_map:             # key = 内部 canonical 字段，value = CSV 实际列名
    pin: Location
    pin_name: Pin Name
    bank: Bank
    io_type: I/O Type
    byte_group: Byte Group      # 可选
    slr: SLR                    # 可选
    vccaux_group: VCCAUX Group  # 可选
    no_connect: No-Connect      # 可选
  classification: classification_rules.yaml   # 可以是文件路径，也可以是内联规则字典
  packages: packages.yaml                     # 可以是文件路径，也可以是内联规格字典

models:
  - device: gw2a_lv55
    package: pg484c8
    full_name: gw2a_lv55pg484c8
    pinout: gw2a-lv55pg484/pinout.csv
    package_spec: gw2a-lv55pg484/package.json   # 可选；缺失时按 package code 查注册表

  - device: gw2a_lv18
    package: pg256c8
    full_name: gw2a_lv18pg256c8
    pinout: gw2a-lv18pg256/pinout.csv
```

约束：
- `vendor.id` 全局唯一，只含小写字母、数字、下划线、连字符。
- `series.id` 在厂商内唯一；`models` 中的型号在系列内唯一。
- `column_map` 的 **key** 必须是内部 canonical 字段，`value` 是 CSV 实际列名。
- `family` 用于兼容现有分类器；非 Xilinx 新厂商统一用 `GENERIC`。
- `data_dirs` 支持多个目录，路径**相对于项目根目录**（即 `PolyLibs.exe` 所在目录），便于指向现有 `a7all/` 等目录。
- 新增同一厂商/系列的下一个型号，**只需要在 `models` 列表追加一项**。

### 6.2 `package.json`

```json
{
  "pitch_mm": 1.0,
  "body_size_x": 23.0,
  "body_size_y": 23.0,
  "pad_diameter_mm": 0.45,
  "mask_opening_mm": 0.5,
  "paste_diameter_mm": 0.4
}
```

### 6.3 `classification_rules.yaml`

```yaml
power_patterns:
  - pattern: '^VCC(?:INT|IO|AUX|PLL|_?\d+)?$'
    rail: VCCINT
  - pattern: '^VCCO_(\d+)$'
    rail: 'VCCO_{0}'      # {0} 表示第一个捕获组
  - pattern: '^VCC([A-Z0-9]+)$'
    rail: 'VCC{0}'

ground_patterns:
  - pattern: '^GND$'
  - pattern: '^GNDADC_?\d*$'

config_patterns:
  - pattern: '^(CCLK|TCK|TMS|TDI|TDO|DONE|PROGRAM|INIT|JTAG)_?\d*$'

mgt_patterns:
  - pattern: '^(GT|GTH|GTX|GTP|GTY|SerDes|Transceiver)'

analog_patterns:
  - pattern: '^(ADC|VN|VP|VREF|DXP|DXN)'

nc_patterns:
  - pattern: '^(NC|RSVD|Unused|RESERVED)'

direction_rules:
  - when: { pin_type: IO, name_pattern: '.*_IN$' }
    direction: INPUT
  - when: { pin_type: IO, name_pattern: '.*_OUT$' }
    direction: OUTPUT
  - default: BIDIRECTIONAL
```

规则语义：
- 按 `power → ground → nc → config → mgt → analog` 顺序匹配，最先命中者决定 `pin_type`。
- 未命中任何规则的落入 `IO`。
- `direction_rules` 仅对 `IO` 生效；电源/地/NC 等方向固定。

## 7. 组件设计

### 7.1 `LibraryScanner`

负责启动时扫描 `library/`，构建树形结构。

```python
class LibraryScanner:
    def __init__(self, root: Path):
        self.root = root / "library"

    def scan(self) -> LibraryTree:
        ...

class LibraryTree:
    vendors: dict[str, Vendor]
    series: dict[str, Series]
    models: dict[str, Model]
```

`scan()` 流程：

1. 递归查找 `library/**/manifest.yaml`。
2. 解析每个 manifest：
   - `vendor` 段 → 构造 `Vendor`（相同 `vendor.id` 合并）。
   - `series` 段 → 构造 `Series`，绑定到 Vendor。
   - `models` 段 → 为每个条目构造 `Model`，`pinout` 路径相对 manifest 目录。
3. 若 `series.data_dirs` 非空，同时扫描这些目录下的 CSV：
   - 已在 `models` 列表中显式声明的型号优先使用显式配置。
   - 未声明的 CSV 按现有 `_split_device_package()` 规则自动派生型号。
4. 返回 `LibraryTree`。

### 7.2 `GenericParser`

替代/扩展现有 `parse_csv()`。

- 输入：`csv_path`, `series: Series`。
- 读取 CSV 头，按 `series.column_map`（canonical key → CSV 列名）定位列，再映射到 canonical 字段。
- 生成 `DevicePinout`，其中 `family` 取 `series.family`。
- 对于现有 Xilinx 数据，`manifest.yaml` 中 `series.column_map` 与当前默认列名一致，可保持输出不变。

### 7.3 `RuleBasedClassifier`

替代/扩展现有 `classify_all()`。

- 输入：`PinRecord`, `series.classification_rules`。
- 按 6.5 规则匹配得到 `PinType`、`rail_name`、`direction`。
- 若 Series 未提供规则文件，则回退到现有 Xilinx 分类器（保持兼容）。

### 7.4 `PackageRegistry`

外置化封装几何数据库。

- 启动时从 `<data_root>/data/pkg_db.json` 加载。
- 同时加载各 `manifest.yaml` 中 `series.packages` 声明的封装规格（可以是文件路径或内联字典），合并到同一字典，系列级配置优先级更高。
- 提供 `get_package_spec(package_code, ...)`，与现有接口一致。
- 新增封装时，用户只需修改 `data/pkg_db.json`、`manifest.yaml` 的 `series.packages` 或型号级 `package.json`，无需重编 exe。

### 7.5 GUI/CLI 改动

**GUI**

- 在系列/型号/封装下拉框前增加**厂商下拉框**。
- 下拉框联动：厂商 → 系列 → 型号 → 封装。
- 用 `LibraryTree` 替代现有的 `scan_devices_by_series()` 结果。
- 若 `library/` 不存在，回退到现有 `_SERIES_DIR_MAP` 行为，保证未迁移时的兼容性。

**CLI**

新增子命令：

```bash
python -m polylibs library scan                # 扫描并打印库树
python -m polylibs library validate <path>     # 验证 vendor/series/model 配置
python -m polylibs library add-package <json>  # 合并封装规格到 pkg_db.json
python -m polylibs generate --vendor Altera --series "Cyclone V" --model ...
```

## 8. 数据流

```text
启动阶段
  ├─ 读取 data/pkg_db.json + 各 series packages → PackageRegistry
  ├─ 扫描 library/**/manifest.yaml → LibraryScanner
  │   └─ 按 models 列表 + data_dirs 扫描 CSV → LibraryTree
  └─ GUI/CLI 用 LibraryTree 填充下拉框

生成阶段（选中 model 后）
  ├─ GenericParser(column_map) 读取 pinout.csv → DevicePinout
  ├─ RuleBasedClassifier(rules) → [ClassifiedPin]
  ├─ PackageRegistry.get_package_spec() → PackageSpec
  ├─ compute_ball_coordinates() → coords
  └─ GeneratorRegistry → 符号/封装输出
```

## 9. 错误处理与校验

`validate` 子命令至少检查：

- `manifest.yaml` 的 `vendor` / `series` / `models` 三段 schema 与必填字段。
- `vendor.id` 全局唯一性、`series.id` 厂商内唯一性。
- `column_map` 的 key 必须是 canonical 字段。
- CSV 文件存在、可读、包含映射到的列。
- 所有 `Pin` / `Location` 值符合 BGA ball ID 格式。
- `package.json` / `pkg_db.json` 中 pitch、body size、pad 等数值为正。
- `classification_rules.yaml` 中的正则表达式可编译。
- 扫描到的模型至少有一个有效引脚。

GUI 启动时若发现配置错误，应在日志/状态栏提示，但不阻塞其他有效厂商的加载。

## 10. 向后兼容与迁移

- **第一阶段（本设计实现）**：新增 `library/` 和动态扫描逻辑；现有 `_SERIES_DIR_MAP` 作为 fallback。新增 `library/xilinx/7series/manifest.yaml` 等配置指向现有目录。
- **第二阶段（可选）**：把现有 `a7all/` 等逐步移入 `library/xilinx/7series/`，减少根目录混乱。保持 `series.data_dirs` 指向方式即可零风险迁移。
- 所有现有测试继续通过：通过为现有 Xilinx 系列提供等价的 `manifest.yaml`，保证 `GenericParser` + `RuleBasedClassifier` 输出与现有 `parse_csv` + `classify_all` 一致。

## 11. 测试策略

- **单元测试**：
  - `LibraryScanner`：能正确从示例 `library/` 构建树。
  - `GenericParser`：对现有 Xilinx CSV 和按模板构造的新厂商 CSV 都能正确解析。
  - `RuleBasedClassifier`：对规则文件中的每种模式给出预期 `PinType`。
  - `PackageRegistry`：支持外置 JSON 和系列级覆盖。
- **集成测试**：在临时目录中构造一个完整的新厂商库，运行 CLI generate，验证输出文件存在且 report.txt 正确。
- **回归测试**：现有 55 个 pytest 用例全部继续通过。

## 12. 打包变更

- `PolyLibs.spec`：移除 `datas=[('PolyLibs/data','data')]`，不再把 `pkg_db.json` 打包进 exe。
- 构建脚本 `build_exe.py`：在打包后把 `data/` 和 `library/` 复制到 `dist/` 目录，确保 exe  standalone 运行时能找到。
- 最终交付物：`.exe` + `data/pkg_db.json` + `library/`。新增型号只需修改这两个目录里的文件。

## 13. 待决定事项

1. 是否把 `library/` 也放进 `dist/` 一起打包？—— 不建议；应作为可替换数据。
2. 是否需要支持系列级 `packages.yaml`？—— 建议支持，方便厂商独立维护封装数据。
3. `family` 字段是否保留为枚举？—— 保留现有枚举并新增 `GENERIC`，新厂商用字符串式 generic 处理。
4. 是否支持 zip 模型包？—— 初版不支持；后续可扩展。

## 14. 参考文档

- 用户操作指南：`docs/superpowers/specs/model-expansion-user-guide.md`
- 模板与示例：`docs/superpowers/specs/templates/manifest.yaml`
- 现有相关代码：`PolyLibs/polylibs/parser.py`、`classifier.py`、`geometry.py`、`gui.py`、`__main__.py`、`models.py`
