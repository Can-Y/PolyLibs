# 新增型号模板

本目录包含 `fpga_libs_tool` 型号扩展接口的模板。

## 使用步骤

1. 复制 `manifest.yaml` 到目标系列目录：`library/<vendor_id>/<series_id>/manifest.yaml`。
2. 替换所有 `<...>` 占位符为实际值。
3. 按需要放置 `classification_rules.yaml`、`packages.yaml`、`pinout.csv`、`package.json`。
4. 按 `docs/superpowers/specs/model-expansion-user-guide.md` 进行校验。

## 文件清单

| 文件 | 用途 | 放置位置 |
|---|---|---|
| `manifest.yaml` | 统一清单（含 vendor + series + models） | `library/<vendor_id>/<series_id>/manifest.yaml` |
| `pinout.csv` | 引脚表格式示例 | `library/<vendor_id>/<series_id>/<model>/pinout.csv` |
| `package.json` | 封装几何参数 | `library/<vendor_id>/<series_id>/<model>/package.json`（可选） |
| `classification_rules.yaml` | 引脚分类规则 | `library/<vendor_id>/<series_id>/classification_rules.yaml`（可选，也可内联） |

## 示例：新增高云 GW2A 系列

```text
library/
└── gowin/
    └── gw2a/
        ├── manifest.yaml                 # 复制本模板，填 vendor/series/models
        ├── classification_rules.yaml     # 高云引脚分类规则
        ├── packages.yaml                 # 可选，系列级封装规格
        ├── gw2a-lv55pg484/
        │   ├── pinout.csv
        │   └── package.json
        └── gw2a-lv18pg256/
            ├── pinout.csv
            └── package.json
```

后续新增 GW2A 的其它型号，只需要在 `manifest.yaml` 的 `models` 段追加一条，并把 `pinout.csv`/`package.json` 放到新目录即可。
