# FPGA Libs — Xilinx FPGA 封装生成工具设计文档

**日期**: 2026-07-11  
**版本**: v1.0（MVP）  
**作者**: Kimi Code + 用户  

---

## 1. 项目目标

做一个桌面小工具：输入 Xilinx FPGA 型号，自动输出该器件的原理图符号和 PCB 封装文件，支持 **PADS**、**Cadence**、**Altium Designer** 三种 EDA 工具。所有输出均为文本/脚本格式，不依赖 EDA 软件安装。

---

## 2. 需求摘要

| 项目 | 说明 |
|------|------|
| 输入 | Xilinx FPGA 完整型号，如 `xc7a100tfgg484` |
| 输出 | 原理图符号 + PCB 封装，分别对应 PADS / Cadence / Altium |
| 界面 | 桌面 GUI（Tkinter），也保留后端模块可被 CLI/API 调用 |
| 支持系列 | 7-Series、UltraScale、UltraScale+（含 Zynq 衍生系列） |
| 原理图风格 | 按功能拆分子部件：I/O Bank、电源/地、配置、MGT、模拟 |
| 输出格式 | 文本/脚本格式，避免依赖 EDA 软件 |
| 运行环境 | Windows / Linux / macOS，Python 3.10+ |

---

## 3. 项目结构

```
fpga_libs_tool/                  # 新项目根目录
├── data/
│   ├── a7all/                  # 7-series pinout CSV（复用现有）
│   ├── usaall/                 # UltraScale pinout CSV
│   ├── zupall/                 # UltraScale+ pinout CSV
│   └── pkg_db.json             # 封装尺寸数据库
├── fpga_libs/                  # Python 包名
│   ├── __init__.py
│   ├── __main__.py             # python -m fpga_libs
│   ├── models.py               # 数据模型 dataclass
│   ├── parser.py               # CSV 发现、格式检测、解析
│   ├── classifier.py           # 引脚分类
│   ├── geometry.py             # BGA 坐标、封装尺寸
│   ├── gui.py                  # Tkinter GUI
│   └── generators/
│       ├── __init__.py
│       ├── base.py             # 生成器抽象接口
│       ├── pads.py             # PADS Part + Decal ASCII
│       ├── cadence.py          # OrCAD TCL + Allegro SKILL
│       └── altium.py           # Altium SchLib/PcbLib 文本格式
├── tests/
│   ├── test_parser.py
│   ├── test_classifier.py
│   ├── test_geometry.py
│   └── test_generators.py
├── README.md
└── requirements.txt            # 仅 pytest，生产零依赖
```

---

## 4. 数据流

```
用户输入型号 ──► parser.find_device_csv() ──► parse_csv()
                                               │
                                               ▼
                                    DevicePinout (pins + metadata)
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    ▼                          ▼                          ▼
            classifier.classify_all()   geometry.get_package_spec()  geometry.compute_ball_coordinates()
                    │                          │                          │
                    ▼                          ▼                          ▼
            list[ClassifiedPin]        PackageSpec               dict[ball_id, (x, y)]
                    │                          │                          │
                    └──────────────────────────┴──────────────────────────┘
                                               │
                                               ▼
                              按功能分组（IO Bank / 电源 / 配置 / MGT / 模拟）
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    ▼                          ▼                          ▼
              generators/pads.py        generators/cadence.py        generators/altium.py
                    │                          │                          │
                    ▼                          ▼                          ▼
           PADS Part + Decal ASCII    OrCAD TCL + Allegro SKILL    SchLib/PcbLib ASCII
```

---

## 5. 核心模块职责

### 5.1 `models.py`

定义所有数据类：

- `PinRecord`：单个引脚（ball_id, pin_name, bank, io_type, byte_group, slr, vccaux_group, no_connect, family, row_index, col_index）
- `DevicePinout`：完整器件（device_name, package_code, full_name, family, total_pins, pins）
- `PackageSpec`：pitch_mm, body_size_x, body_size_y, pad_diameter_mm, mask_opening_mm, paste_diameter_mm
- `ClassifiedPin`：record, pin_type, direction, rail_name, pin_group
- `SymbolSection`：name, pins, side（用于原理图子部件）

### 5.2 `parser.py`

- `find_device_csv(device_name, data_dirs)`：按型号模糊搜索 CSV
- `detect_format(lines)`：根据列数和列名识别 7-series / UltraScale / UltraScale+
- `parse_csv(path)`：解析为 `DevicePinout`
- `_split_device_package(full_name)`：将完整型号拆分为器件名和封装代码

改进点（相对于 `fpga2cad`）：
- 更严格的异常处理
- 更清晰的 device/package 拆分逻辑
- 对未知格式给出明确错误
- 对缺失列（如 UltraScale+ 无 No-Connect 列）自动填充默认值

### 5.3 `classifier.py`

- `classify_pin(record)` / `classify_all(pins)`：按名称正则分类
- 类型枚举：`POWER`, `GROUND`, `IO`, `CONFIG`, `MGT`, `ANALOG`, `NO_CONNECT`, `MISC`
- 方向枚举：`INPUT`, `OUTPUT`, `BIDIR`, `POWER`, `PASSIVE`, `NC`
- 分组函数：`group_for_symbol()` 返回按功能分区的 `SymbolSection` 列表

### 5.4 `geometry.py`

- `get_package_spec(package_code, ball_count, overrides)`：查 `pkg_db.json`，未命中时用球数启发式估算
- `compute_ball_coordinates(pins, spec)`：以封装中心为原点，按 pitch 计算每个 ball 的 (x, y)
- `get_grid_bounds(pins)`：返回 BGA 网格边界

### 5.5 `generators/`

统一接口：

```python
class Generator(ABC):
    @abstractmethod
    def generate_symbol(self, device, sections, spec) -> str: ...

    @abstractmethod
    def generate_footprint(self, device, spec, coords) -> str: ...

    @abstractmethod
    def file_extensions(self) -> dict: ...
```

| 文件 | 工具 | 输出 |
|------|------|------|
| `pads.py` | PADS | Part Type ASCII (`.txt`)、Decal ASCII (`.dec`) |
| `cadence.py` | Cadence | OrCAD Capture TCL (`.tcl`)、Allegro SKILL (`.il`) |
| `altium.py` | Altium | SchLib/PcbLib ASCII 文本格式 |

### 5.6 `gui.py`

Tkinter 桌面界面，包含：
- 型号输入框 + 下拉补全
- 输出格式勾选框（PADS/Cadence/Altium × 原理图/PCB）
- 输出目录选择
- 高级选项：pitch、body_size、pad_diameter 覆盖
- 生成按钮 + 进度日志
- 结果弹窗

生成过程在后台线程执行，避免 UI 卡死。

---

## 6. 输出格式详细说明

### 6.1 PADS

- **原理图**：Part Type ASCII（`.txt`），可被 PADS Logic 导入为 Part Type
- **PCB 封装**：Decal ASCII（`.dec`），可被 PADS Layout 导入为 Decal
- 内容包含：引脚号、引脚名、Decal 引脚坐标、封装尺寸、丝印框

### 6.2 Cadence

- **原理图**：OrCAD Capture TCL 脚本（`.tcl`），运行后生成 `.olb`
- **PCB 封装**：Allegro PCB Editor SKILL 脚本（`.il`），加载后创建 `.dra`
- 包含：按功能分区的子部件、所有引脚放置、封装轮廓、place-bound、Pin1 标识

### 6.3 Altium Designer

- **原理图**：优先输出可直接导入的 ASCII 格式（如 Pipe-delimited part import file）；若不可行，使用 SchLib ASCII 导出结构
- **PCB 封装**：PcbLib ASCII 导出格式 或 IPC-7351 Land Pattern ASCII
- 目标：无需安装 Altium 即可生成，且能被 Altium 导入/打开

### 6.4 输出目录结构示例

```
output/
└── xc7a100tfgg484/
    ├── pads/
    │   ├── xc7a100tfgg484_part.txt
    │   └── fgg484.decal
    ├── cadence/
    │   ├── xc7a100tfgg484_symbol.tcl
    │   └── fgg484.il
    ├── altium/
    │   ├── xc7a100tfgg484.SchLib
    │   └── fgg484.PcbLib
    └── report.txt
```

---

## 7. GUI 布局

```
┌─────────────────────────────────────────┐
│  Xilinx FPGA 封装生成工具                │
├─────────────────────────────────────────┤
│  器件型号: [xc7a100tfgg484    ] [刷新▼] │
├─────────────────────────────────────────┤
│  输出格式:                                │
│  [✓] PADS    原理图 [✓]  PCB 封装 [✓]   │
│  [✓] Cadence 原理图 [✓]  PCB 封装 [✓]   │
│  [✓] Altium  原理图 [✓]  PCB 封装 [✓]   │
├─────────────────────────────────────────┤
│  输出目录: [./output           ] [浏览]  │
├─────────────────────────────────────────┤
│  高级选项:                                │
│  球间距覆盖: [      ] mm                 │
│  封装尺寸覆盖: [ 23x23 ] mm             │
│  焊盘直径覆盖: [      ] mm               │
├─────────────────────────────────────────┤
│         [      生成      ]              │
├─────────────────────────────────────────┤
│  日志:                                    │
│  Found xc7a100tfgg484pkg.csv             │
│  Parsed 484 pins ...                     │
│  Generated PADS symbol ...               │
│  Done!                                   │
└─────────────────────────────────────────┘
```

---

## 8. 错误处理与边界情况

| 场景 | 处理方式 |
|------|----------|
| 找不到 CSV | 弹窗提示，建议检查型号或数据目录 |
| CSV 解析失败 | 显示具体行号和错误信息 |
| 未知封装代码 | 用球数启发式估算，日志警告 |
| 引脚分类失败 | 默认归为 `MISC`，不中断生成 |
| 输出目录无权限 | 生成前检查可写性，提前报错 |
| 生成过程异常 | 捕获异常，弹窗显示摘要，不崩溃 |
| 同名文件已存在 | 询问是否覆盖 |

---

## 9. 测试策略

### 9.1 单元测试

- `test_parser.py`：CSV 发现、格式检测、device/package 拆分、边界情况
- `test_classifier.py`：典型引脚分类、方向判断
- `test_geometry.py`：坐标计算、封装尺寸回退、网格边界
- `test_generators.py`：各 generator 输出包含关键标记和全部引脚

### 9.2 集成测试

- 用以下型号跑完整流程：
  - `xc7a100tfgg484`（7-series）
  - `xcku035fbva900`（UltraScale）
  - `xcau10pffvb676`（UltraScale+）
- 验证输出文件数量、report 内容、关键引脚存在

### 9.3 人工验证

- 将生成的文件导入对应 EDA 工具，确认能打开、符号/封装可见、引脚位置正确

---

## 10. 风险与 Fallback

| 风险 | Fallback |
|------|----------|
| Altium 纯文本格式无法直接生成可用库 | 改为输出 CSV 引脚表 + 导入脚本/说明 |
| PADS ASCII 格式版本差异 | 同时注明适用 PADS 版本，必要时提供旧版兼容选项 |
| 未知封装代码导致尺寸不准 | 日志警告，允许用户通过 GUI 覆盖参数 |
| 大型 FPGA 引脚数超多（>3000） | 生成过程放后台线程，GUI 显示进度；原理图拆分更多子部件 |

---

## 11. 技术约束

- Python 3.10+
- 生产环境仅使用标准库
- 测试环境使用 `pytest`
- 不调用任何 EDA 软件的 COM/API/外部进程
- 代码风格遵循项目 Black/PEP8 规范

---

## 12. 后续可扩展方向

- 增加 CLI 入口
- 支持 Intel/Altera FPGA
- 支持更多封装类型（QFN、QFP 等）
- 生成 3D Step 模型占位
- 云端数据更新（自动下载最新 pinout CSV）
