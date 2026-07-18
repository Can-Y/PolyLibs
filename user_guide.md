# PolyLibs 使用说明

PolyLibs 是一个 Xilinx FPGA 原理图符号与 PCB 封装生成工具，输出 KiCad / Cadence 格式。

## 为什么 KiCad 和 Cadence 双版本？

| | KiCad | Cadence |
|------|------|------|
| 授权 | 完全开源免费 | 商业 EDA（需 License） |
| 适用场景 | 个人项目、开源硬件、教学 | 企业级 PCB 设计、量产产品 |
| 输出格式 | `.kicad_sym` + `.kicad_mod` | OrCAD Library XML + Allegro SKILL |
| 上手难度 | 低，社区资源丰富 | 专业工具，学习曲线陡峭 |
| 设计验证 | kicad-cli 可做自动化验证 | 交互验收，无自动化 CLI 验证 |

> **Cadence License 免责声明：** PolyLibs **不提供** Cadence SPB / OrCAD / Allegro 的商业 License。
> 本工具生成的仅为中间格式文件（XML / SKILL 脚本），需在已合法授权的 Cadence 环境中使用。
> **商业用途请务必自行购买 Cadence License。** 未授权使用可能导致法律风险，开发者不承担任何责任。

KiCad 是推荐的默认输出格式——免费、开源、社区活跃。Cadence 版本面向已有 License 的专业用户，
帮助他们自动生成大型 BGA 封装（如 XCVU13P-FLGA2577），节省手动建库时间。

## 内置器件系列

当前内置以下厂商与系列，可直接在 GUI 中选择生成：

| 厂商 | 系列 |
|------|------|
| Xilinx | 7series |
| Xilinx | ultrascale |
| Xilinx | ultrascale_plus |
| Xilinx | versal |
| Xilinx | zynq7000 |
| Xilinx | zynq_us_plus |
| ExampleVendor | example_series（示例） |

如需添加新的厂商或系列，请参考第 2 节「如何新增器件」。

## 1. 如何运行

### 1.1 双击运行（推荐）

在项目根目录或 `PolyLibs-opensource/` 目录下双击：

```text
polylibs.bat
```

首次运行会自动完成：

1. 检测 `PolyLibs/.venv` 虚拟环境
2. 不存在则自动创建
3. 自动安装依赖 `PyYAML` 和 `Pillow`
4. 启动 GUI

### 1.2 通过 Python 运行

```bash
# 方式 1：从 PolyLibs 目录启动 GUI
cd PolyLibs
.venv/Scripts/python -m polylibs

# 方式 2：从根目录调用 start.py
cd E:/1_work/15_pinout
PolyLibs/.venv/Scripts/python start.py
```

### 1.3 仅检查依赖

```bash
polylibs.bat --check
# 或
PolyLibs/.venv/Scripts/python start.py --check
```

### 1.4 系统要求

- Windows 10/11
- Python 3.10 或更高版本
- 可选：`kicad-cli`（用于 KiCad 导出验证）

---

## 2. 如何新增器件

### 2.1 准备原始 pinout 数据

将原始 CSV 文件放入分层目录：

```text
pinout_file/<vendor>/<series>/<raw_data_dir>/*.csv
```

例如：

```text
pinout_file/xilinx/7series/a7all/xc7a100tfgg484.csv
```

### 2.2 创建 manifest 文件

在 `library/` 下创建对应的 manifest：

```text
library/<vendor>/<series>/manifest.yaml
```

示例：`library/example/example_series/manifest.yaml`

```yaml
vendor:
  id: example
  name: ExampleVendor

series:
  id: example_series
  name: ExampleSeries
  classification: classification_rules.yaml

# CSV 列映射
column_map:
  pin_name: Pin
  ball: Ball
  pin_function: "IO Type"

# 原始数据目录（相对于项目根目录）
data_dirs:
  - pinout_file/example/example_series/raw_data
```

可参考模板：`docs/superpowers/specs/templates/manifest.yaml`

### 2.3 添加封装规格（如需要新封装）

如果器件使用了 `data/pkg_db.json` 中不存在的封装代码，补充规格：

```json
"fgg484": {
  "body_size_x": 23.0,
  "body_size_y": 23.0,
  "pitch_mm": 1.0,
  "pad_diameter_mm": 0.45,
  "mask_opening_mm": 0.5,
  "paste_diameter_mm": 0.4
}
```

注意：`body_size_x` / `body_size_y` 必须按数据手册方向填写（球号数字方向为 x）。
长方形（非对称）封装必须提供精确条目——缺失时会退化为启发式估值，
pitch 按封装前缀猜、本体只猜正方形，长方形封装靠猜必然出错
（原理详见第 5 节）。

或使用脚本从已有数据推断：

```bash
PolyLibs/.venv/Scripts/python update_pkg_db.py
```

### 2.4 验证新增器件

```bash
cd PolyLibs
.venv/Scripts/python -m polylibs library validate --root ..
```

验证通过后即可在 GUI 中看到新增的厂商/系列/型号。

---

## 3. 如何生成库文件

### 3.1 通过 GUI 生成

1. 运行 `polylibs.bat` 启动 GUI
2. 选择厂商、系列、型号、封装
3. 勾选需要生成的 EDA 工具格式
4. 选择输出目录（默认 `output/`）
5. 点击生成

### 3.2 批量生成完整 KiCad 库

生成所有（系列 × 型号 × 封装）组合：

```bash
cd E:/1_work/15_pinout
PolyLibs/.venv/Scripts/python batch_generate.py
```

输出目录：`output/batch_kicad_all/`

### 3.3 批量生成 KiCad 封装

按（系列 × 封装）去重生成封装：

```bash
cd E:/1_work/15_pinout
PolyLibs/.venv/Scripts/python batch_footprints.py
```

输出目录：`output/batch_footprints_by_package/`

### 3.4 生成发布版 exe

```bash
cd E:/1_work/15_pinout
PolyLibs/.venv/Scripts/python -m PyInstaller PolyLibs.spec --noconfirm
```

输出：`dist/PolyLibs.exe`

---

## 4. 如何提交 bug 报告

### 4.1 使用模板

项目根目录提供了 `bug_report.md` 模板。提交问题时：

1. 复制 `bug_report.md` 并重命名，例如 `bug_report_20260715_xc7a100t.md`
2. 按照模板填写所有 `[ ]` 中的内容
3. 删除所有提示文字
4. 附上相关日志和生成文件
5. 提交

模板中需要填写的核心信息：

- **摘要：** 一句话描述问题
- **环境信息：** 操作系统、Python 版本、项目路径、使用入口
- **复现步骤：** 可重复的操作步骤
- **期望结果 vs 实际结果**
- **错误日志：** 完整的命令行输出
- **最小复现示例：** 具体的厂商/系列/型号/封装/操作
- **附件：** CSV、生成的库文件、截图等

### 4.2 最小复现示例格式

```text
厂商：xilinx
系列：7series
型号：xc7a100t
封装：fgg484
EDA 格式：KiCad
操作：生成符号
现象：焊盘数量与 CSV 不一致
```

### 4.3 收集错误日志

如果是双击 `polylibs.bat` 运行，请在命令行中重新执行以捕获完整输出：

```bash
cd E:/1_work/15_pinout
polylibs.bat
```

然后将命令行内容复制到 bug 报告中。

---

## 5. 设计原理：焊盘坐标与缺省焊盘

### 5.1 坐标来自球号解码，不做几何推测

每个焊盘的物理坐标由其球号（ball ID）直接解码：

- 数字部分 = 列（X 方向），字母部分 = 行（Y 方向）
- 行字母按跳过 I、O、Q、S、X、Z 的 20 进制计数（A..Y，然后 AA、AB…）
- 以阵列中心为原点：`x = (col - col_center) x pitch`，`y = (row_center - row) x pitch`

例如 UVBA494：29 列 x 18 行、0.5mm pitch，焊盘跨度 X 14.0mm、Y 8.5mm。

### 5.2 缺省焊盘（depopulation）由 CSV 承载

生成器只为 pinout CSV 中出现的球号放置焊盘；CSV 中没有的阵列位置自然留空。
不推测、不插值——缺省信息完全来自原始数据。

`data/pkg_db.json` 只提供几何参数（pitch、本体尺寸、焊盘/阻焊/钢网直径），
不包含阵列规模或缺省焊盘表。

例：UVBA494 阵列 522 个位置、494 个焊盘，缺的 28 个集中在第 5、25 两列，
与实物封装的 depopulation 一致。

### 5.3 长方形/非对称封装的输入要求

新增此类型号时，现有输入即可满足，但必须遵守：

1. pinout CSV 完整（球号决定坐标与缺省位置）
2. `data/pkg_db.json` 必须包含该封装代码的**精确**条目，且
   `body_size_x` / `body_size_y` 按数据手册方向填写（球号数字方向为 x）。
   缺失时退化为启发式估值，长方形封装靠猜必然出错
3. 生成后验证：

```bash
python verify_footprint.py <封装>.kicad_mod <body_x> <body_y>
```

   焊盘跨度应 <= 本体尺寸，且四边留白大致对称。

### 5.4 目前表达不了的边界情况

- 焊盘阵列中心相对本体中心有偏移（如最外圈整行/整列缺省时，
  按现有焊盘推断的中心会偏半个 pitch，本体丝印框随之错位）
- X/Y 方向不等 pitch（schema 仅支持单一 `pitch_mm`）
- 非矩形本体（开槽、切角、裸焊盘 EPAD 等）
- 非 BGA 编号（QFN/QFP 纯数字引脚暂不支持）

真遇到这类封装时需要扩展 pkg_db schema（如增加 offset 字段），届时再实现。

### 3.5 Cadence 输出使用说明（SPB 17.2）

生成 Cadence 格式后，输出目录的 `cadence/` 下有：

- `<PACKAGE>.il` — Allegro 封装构建脚本
- `<DEVICE>_library.xml` — OrCAD Capture 符号库

**Allegro 封装（.dra）：**

1. 打开 Allegro PCB Editor，`File > New > Package Symbol`，名称任意，进入编辑界面
2. 在下方 SKILL 命令行输入：`skill load("<完整路径>/<PACKAGE>.il")`
3. 脚本自动创建 padstack、全部焊盘、外形框与 A1 标记；`File > Save` 得 `.dra`
4. 若提示 padstack 已存在的 WARN，属正常（复用已有盘）

**OrCAD 符号（.olb）：**

1. 打开 Capture，`File > Import > Library XML`，选择 `<DEVICE>_library.xml`
2. 导入后得到 `.olb`，打开核对引脚数量与名称

适用版本：Cadence SPB 17.2（`D:\Cadence\SPB_17.2`）。

注意：请使用 Capture **交互界面**的 `File > Import > Library XML` 导入
（实测 494 引脚可正常导入）。不要用 `Capture.exe <script.tcl>` 无头方式
驱动——该路径回退 Lite 模式，单器件超过 100 引脚会被拒绝
（`ORDBDLL-1233`）。
