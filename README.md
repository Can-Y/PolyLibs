# PolyLibs 使用说明

PolyLibs 是一个 Xilinx FPGA 原理图符号与 PCB 封装生成工具，支持 KiCad 输出格式。

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
