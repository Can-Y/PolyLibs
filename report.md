# PolyLibs 测试与整理报告

**日期：** 2026-07-15  
**项目路径：** `E:/1_work/15_pinout`  
**Python 版本：** 3.14.5

## 1. 本次整理内容

### 1.1 目录结构统一

将 `PolyLibs-opensource/` 重构为与项目根目录一致的布局：

```text
E:/1_work/15_pinout/
├── PolyLibs/                  # 主开发包（含 polylibs/、tests/、scripts/、data/）
├── PolyLibs-opensource/       # 开源备份，结构与根目录一致
├── data/                      # pkg_db.json 运行时数据
├── dist/                      # PyInstaller 发布的 exe
├── docs/                      # 文档（plans / specs / templates）
├── library/                   # 厂商/系列 manifest.yaml
├── output/                    # 生成输出目录（已清空）
├── pinout_file/               # 分层原始 pinout CSV
├── FPGAer_Zone_258.jpg        # exe 打包用的二维码图片
├── PolyLibs.spec              # PyInstaller 配置
├── polylibs.bat               # 一键启动批处理
├── polylibs_gui.py            # GUI 入口
├── start.py                   # 依赖检查与启动
├── update_pkg_db.py           # 更新封装数据库
├── extract_pkg_specs.py       # 从文本提取封装规格
├── extract_all_pkg_specs.py   # 从 PDF 批量提取封装规格
├── batch_generate.py          # 批量生成完整库
├── batch_footprints.py        # 批量生成封装
├── verify_batch.py            # 批量验证生成结果
├── verify_footprint.py        # 验证单个封装
├── build_minimal.py           # 最小构建脚本
└── handoff.md                 # 交接记录
```

### 1.2 无用文件清理

已删除不影响执行的文件：

- 所有 `__pycache__` 和 `.pytest_cache` 目录（含 venv 内部缓存）
- 旧 batch 崩溃残留的损坏 venv 文件：
  - `PolyLibs-opensource/Lib/`
  - `PolyLibs-opensource/Scripts/`
  - `PolyLibs-opensource/pyvenv.cfg`
  - `PolyLibs-opensource/Include/`
- 多余的 `.gitkeep` 占位文件
- `archive/` 整个旧项目备份目录
- `docs/references/` 整个 160 MB 的 PDF/txt 参考目录
- `output/` 目录内的历史生成文件
- `PolyLibs-opensource/docs/` 下重复的文档和多余的 `docs/templates/`
- 空日志文件 `archive/dist_output_backup/.../allegro.jrl`

> **注意：** 清理过程中误删了根目录和 `PolyLibs-opensource/` 下的 7 个业务脚本（`update_pkg_db.py`、`batch_generate.py`、`batch_footprints.py`、`extract_pkg_specs.py`、`extract_all_pkg_specs.py`、`verify_batch.py`、`verify_footprint.py`），已从回收站恢复并重新验证。

### 1.3 `polylibs.bat` 修复

修复了删除 venv 后无法重建的问题：

- **原因：** batch 在 `if` 块内设置 `VENV_DIR` 后又在同一块内用 `%VENV_DIR%` 创建 venv，变量扩展为空字符串，导致 venv 创建到错误位置。
- **修复：** 将 venv 路径计算和 venv 创建拆成两步，先在一个块里确定路径，退出块后再读取变量并创建环境。
- 已同步更新根目录和 `PolyLibs-opensource/` 下的 `polylibs.bat`。

## 2. 测试环境与结果

### 2.1 依赖

- Python 3.14.5
- PyYAML 6.0.3
- Pillow 12.3.0
- pytest 9.1.1

### 2.2 测试执行

```bash
cd PolyLibs
.venv/Scripts/python -m pytest -q
```

```text
72 passed in 0.34s
```

```bash
cd PolyLibs-opensource/PolyLibs
.venv/Scripts/python -m pytest -q
```

```text
72 passed in 0.50s
```

### 2.3 测试覆盖

| 测试文件 | 用例数 | 说明 |
|----------|--------|------|
| `test_classifier.py` | 11 | 引脚分类规则（电源、地、IO、MGT 等） |
| `test_cli.py` | 4 | CLI 扫描、验证、添加封装 |
| `test_generators.py` | 5 | PADS/Cadence/Altium/KiCad 生成器输出 |
| `test_geometry.py` | 9 | 封装几何计算与数据库查询 |
| `test_gui.py` | 4 | GUI 构建输出、设备树、生成器注册表 |
| `test_integration.py` | 4 | 端到端生成（7series / UltraScale / UltraScale+） |
| `test_library.py` | 3 | 库扫描与 CSV 发现 |
| `test_manifest.py` | 3 | manifest 加载与校验 |
| `test_models.py` | 6 | 数据模型（Family、PinRecord、PackageSpec 等） |
| `test_new_vendor.py` | 1 | 新厂商发现 |
| `test_parser.py` | 9 | 设备/封装名拆分、CSV 解析 |
| `test_scaffold.py` | 7 | 项目结构、必需文件存在性 |
| **合计** | **72** | 全部通过 |

### 2.4 Manifest 验证

```bash
cd PolyLibs
.venv/Scripts/python -m polylibs library validate --root ..
```

```text
OK: ..\library\example\example_series\manifest.yaml
OK: ..\library\xilinx\7series\manifest.yaml
OK: ..\library\xilinx\ultrascale\manifest.yaml
OK: ..\library\xilinx\ultrascale_plus\manifest.yaml
OK: ..\library\xilinx\versal\manifest.yaml
OK: ..\library\xilinx\zynq7000\manifest.yaml
OK: ..\library\xilinx\zynq_us_plus\manifest.yaml
```

### 2.5 启动脚本验证

| 入口 | 结果 |
|------|------|
| 双击/执行 `polylibs.bat` | 正常：自动检测/创建 venv，安装依赖，启动 GUI |
| `polylibs.bat --check` | 正常：`All dependencies are already installed.` |
| `python start.py --check` | 正常：依赖检查通过 |

## 3. 当前体积

| 目录/文件 | 大小 |
|-----------|------|
| `PolyLibs-opensource/`（含 venv） | ~49 MB |
| `PolyLibs/`（含 venv） | ~24 MB |
| `pinout_file/` | ~26 MB |
| `dist/PolyLibs.exe` | ~18 MB |
| `docs/` | ~214 KB |
| `data/` | ~68 KB |

## 4. 保留的潜在可清理项

以下文件/目录未被删除，如确认不再需要可手动清理：

- `dist/PolyLibs.exe`（18 MB）：PyInstaller 发布的可执行文件，文档中列为交付物。
- `docs/superpowers/specs/templates/`：新厂商/系列模板示例。

## 5. 结论

- `PolyLibs-opensource/` 与项目根目录结构已统一。
- 所有缓存、残留备份、参考文档已清理。
- 全部 72 个测试用例通过，manifest 验证通过。
- `polylibs.bat` 在有无 venv 的情况下均可正常工作。
