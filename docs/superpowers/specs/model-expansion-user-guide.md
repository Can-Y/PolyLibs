# PolyLibs 新增型号操作指南

本指南说明如何在**不重新编译/封装 exe** 的前提下，为 `PolyLibs` 添加新的 FPGA 型号。

> 本指南对应设计文档：`docs/superpowers/specs/2026-07-14-vendor-aware-model-expansion-design.md`  
> 模板文件：`docs/superpowers/specs/templates/manifest.yaml`

---

## 1. 快速流程概览

新增一个型号通常只需要 2 步：

1. **创建/编辑一个 `manifest.yaml`**（一个文件包含厂商、系列、型号三段）。
2. **放置对应的 `pinout.csv` 和 `package.json`**，然后重启 exe。

```text
library/<vendor>/<series>/
├── manifest.yaml          # vendor + series + models
├── classification_rules.yaml
├── packages.yaml
└── <device_package>/
    ├── pinout.csv
    └── package.json
```

后续新增**同一厂商/同一系列**的型号时，**只需要在 `manifest.yaml` 的 `models` 段追加一条**，并把新的 `pinout.csv`/`package.json` 放到对应目录即可。

---

## 2. `manifest.yaml` 结构

`manifest.yaml` 通过三个关键字识别不同段落：

| 段落 | 关键字 | 作用 |
|---|---|---|
| 厂商 | `vendor:` | 厂商 ID、显示名等。 |
| 系列 | `series:` | 家族、CSV 列名映射、分类规则、封装规格。 |
| 型号 | `models:` | 该系列下的型号列表，每条指向一个 `pinout.csv`。 |

### 2.1 完整示例

```yaml
vendor:
  id: gowin
  name: Gowin
  display_name: 高云半导体

series:
  id: gw2a
  name: GW2A
  family: GENERIC
  data_dirs:
    - .
  column_map:
    pin: Location
    pin_name: Pin Name
    bank: Bank
    io_type: I/O Type
    no_connect: No Connect
  classification: classification_rules.yaml
  packages: packages.yaml

models:
  - device: gw2a_lv55
    package: pg484c8
    full_name: gw2a_lv55pg484c8
    pinout: gw2a-lv55pg484/pinout.csv
    package_spec: gw2a-lv55pg484/package.json

  - device: gw2a_lv18
    package: pg256c8
    full_name: gw2a_lv18pg256c8
    pinout: gw2a-lv18pg256/pinout.csv
```

---

## 3. 新增一个厂商/系列

1. 在 `library/` 下新建目录，例如 `library/gowin/gw2a/`。
2. 把 `templates/manifest.yaml` 复制进去，按实际情况填写 `vendor` 和 `series` 段。
3. （可选）把 `classification_rules.yaml` 和 `packages.yaml` 放到系列目录。

### 3.1 `vendor` 段字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 厂商唯一标识，只含小写字母/数字/下划线/连字符。 |
| `name` | 是 | GUI 厂商下拉框显示名。 |
| `display_name` | 否 | 更友好的完整名称。 |
| `aliases` | 否 | 别名列表。 |

### 3.2 `series` 段字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 系列唯一标识（厂商内唯一）。 |
| `name` | 是 | GUI 系列下拉框显示名。 |
| `family` | 是 | 非 Xilinx 厂商填 `GENERIC`；Xilinx 可填 `SERIES_7`/`ULTRASCALE`/`ULTRASCALE_PLUS`。 |
| `data_dirs` | 是 | 扫描目录列表，路径相对项目根目录（exe 所在目录）。可指向现有目录，如 `a7all`、`k7all`。 |
| `column_map` | 是 | **key** 是内部 canonical 字段，`value` 是 CSV 实际列名。 |
| `classification` | 否 | 分类规则。可以是文件路径，也可以是内联规则字典。不填则回退到默认 Xilinx 规则。 |
| `packages` | 否 | 系列级封装规格。可以是文件路径，也可以是内联字典。不填则只使用顶层 `data/pkg_db.json`。 |

### 3.3 `column_map` 可用字段

- `pin`：BGA ball ID / 位置编号（如 `A1`、`AA16`）。
- `pin_name`：引脚功能名。
- `bank`：Bank 编号。
- `io_type`：I/O 类型/标准。
- `byte_group`：Memory byte group（可选）。
- `slr`：Super Logic Region（可选）。
- `vccaux_group`：VCCAUX group（可选）。
- `no_connect`：No-Connect 标记（可选）。

CSV 列名可以有空格或大小写差异，只要在 `column_map` 的 **value** 里写原始列名即可；**key** 必须保持不变。

---

## 4. 新增一个型号

在已有厂商/系列的 `manifest.yaml` 中，**只需要在 `models` 列表追加一条**：

```yaml
models:
  - device: gw2a_lv55
    package: pg484c8
    full_name: gw2a_lv55pg484c8
    pinout: gw2a-lv55pg484/pinout.csv
    package_spec: gw2a-lv55pg484/package.json
```

同时把引脚表和封装文件放到对应路径：

```text
library/gowin/gw2a/
├── manifest.yaml
├── gw2a-lv55pg484/
│   ├── pinout.csv
│   └── package.json
└── ...
```

### 4.1 `pinout.csv` 示例

```csv
Location,Pin Name,Bank,I/O Type,No Connect
A1,VCC,NA,POWER,NA
A2,IO_0_1,1,LVCMOS33,NA
A3,IO_1_1,1,LVCMOS33,NA
B1,GND,NA,GROUND,NA
B2,NC,NA,NA,YES
```

注意：

- 必须包含 `column_map` 中映射的所有列。
- 第一行为表头。
- BGA ball ID 必须符合字母+数字格式，如 `A1`、`AA16`。

### 4.2 `package.json` 示例

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

如果该封装已经在 `data/pkg_db.json` 或系列级 `packages.yaml` 中存在，可以不写 `package.json`。

---

## 5. 新增 Xilinx 型号（利用现有目录）

为现有 Xilinx 系列创建一个 `manifest.yaml`，例如 `library/xilinx/7series/manifest.yaml`：

```yaml
vendor:
  id: xilinx
  name: Xilinx

series:
  id: 7series
  name: 7series
  family: SERIES_7
  data_dirs:
    - a7all
    - k7all
    - s7all/s7all
    - v7all
  column_map:
    pin: Pin
    pin_name: Pin Name
    bank: Bank
    io_type: I/O Type
    byte_group: Memory Byte Group
    vccaux_group: VCCAUX Group
    no_connect: No-Connect
```

`models` 段可以省略，工具会自动从 `data_dirs` 扫描 CSV 派生型号。

如果是一个全新的 Xilinx 封装（package code 不在 `data/pkg_db.json` 中），则：

1. 把 CSV 放进对应系列目录。
2. 在 `data/pkg_db.json` 中新增一条该 package code 的几何参数；
   或者在 `manifest.yaml` 的 `series.packages` 中内联/引用该封装规格。

---

## 6. 校验

新增或修改配置后，运行校验命令：

```bash
# 校验整个库
python -m polylibs library validate

# 校验某个系列目录
python -m polylibs library validate library/gowin/gw2a
```

校验内容包括：

- `manifest.yaml` 三段 schema 与必填字段。
- `vendor.id` 全局唯一性、`series.id` 厂商内唯一性。
- `column_map` 列名是否在 CSV 中存在。
- BGA ball ID 是否合法。
- 封装参数是否完整且为正数。
- 分类规则正则是否可编译。
- 是否能成功解析出至少一个有效引脚。

---

## 7. 重启 exe 并使用

校验通过后，**不需要重新编译 exe**：

1. 关闭并重新打开 `PolyLibs.exe`。
2. 在 GUI 下拉框中依次选择：厂商 → 系列 → 型号 → 封装。
3. 点击生成。

---

## 8. 常见问题

### Q1：新增厂商/系列后下拉框没有出现？

- 检查 `manifest.yaml` 是否在 `library/<vendor>/<series>/` 目录下。
- 检查 `vendor.id` 是否全局唯一。
- 运行 `python -m polylibs library scan` 查看扫描结果。

### Q2：引脚分类不对（电源被识别成 IO）？

- 检查 `classification_rules.yaml`（或 `series.classification` 内联规则）中的正则是否匹配该厂商命名习惯。
- 新增或修改对应 pattern，然后重新校验。

### Q3：封装尺寸不对？

- 检查 `package.json` 或 `series.packages` 中的参数。
- 也可以直接在 GUI 里临时覆盖 pitch/body size/pad diameter。

### Q4：CSV 列名和模板不一样？

- 不需要改 CSV，只需在 `series.column_map` 的 **value** 里写原始列名即可。

---

## 9. 模板速查

模板位置：`docs/superpowers/specs/templates/manifest.yaml`

复制模板到 `library/<vendor>/<series>/manifest.yaml`，替换所有 `<...>` 占位符即可。
