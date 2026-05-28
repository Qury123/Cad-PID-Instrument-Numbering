# 更新日志

按时间倒序排列。时间是 `echo %DATE% %TIME%` 查的实际系统时间。  
`~HH:MM` 表示按会话顺序估算，误差 ±15 分钟内。

---

## 2026-05-28

### 18:50 — 步骤5新增预览编号功能
- 问题：用户希望确认编号结果后再写入CAD，而非直接执行
- 处理：
  - 步骤5（执行编号）新增独立预览区域
  - 点击「🔍 预览编号」生成位号列表（不写入CAD）
  - 确认无误后点击「🚀 自动编号」正式写入
  - 底部按钮改名「开始编号」→「自动编号」

### 18:00 — 统一编号逻辑：同号分组 + 关闭自动顺延
- 问题：自动顺延默认开启导致起始号=max+1，用户需要从头开始重新编
- 处理：
  - `_write_numbers` 按连续同号分组，同号组共享一个编号
  - 空号块每个单独分配
  - `auto_continue` 默认改为 `False`（但保留该功能，用户可手动开启）
- 问题：自动顺延时全部块被覆盖重编，跳号；同号块未共享编号
- 处理：`_write_numbers` 改为先按连续同号分组 → 空号块逐个分配，有号组共享一个编号

## 2026-05-23

### 12:40 — 编写 USAGE.md 用户操作手册 + 更新 README.md
- 问题：新用户面对插件不知道如何操作
- 处理：编写完整 `USAGE.md`（4 章：快速开始、详细步骤、配置详解、常见问题）
- 同步更新 `README.md` 为项目概览文档，指向 USAGE.md 获取详细操作

### 12:27 — 项目目录结构整理
- 问题：根目录杂乱，备份、脚本、EXE 混在一起
- 处理：
  - `scripts/` — 构建和运行脚本（`build.bat`、`git_here.bat`）
  - `config/` — 打包配置（`version_info.txt`）
  - `releases/v1.0.0/` — 按版本归档 EXE
  - `archive/` — 旧备份文件（历史 LSP、旧版 Python 源码）
  - 根目录保持干净：只留 `src/`、`VERSION`、`pyproject.toml`、`README.md`、`CHANGELOG.md`、`requirements.txt`、`.gitignore`、`run.py`、`run.bat`

### 12:01 — 打包发布 v1.0.0 正式版 EXE
- 问题：项目只有 Python 源码，用户无法直接双击运行（需装 Python 和依赖）
- 处理：用 PyInstaller 打包为单文件 EXE（28.8 MB），嵌入版本信息
- 新增文件：`pyproject.toml`（PEP 621 元数据）、`VERSION`（版本号）、`src/version.py`（版本读取）、`version_info.txt`（EXE 属性）、`build.bat`（一键构建）
- 输出：`dist\仪表自动编号.exe` + `仪表自动编号_v1.0.0.exe`
- 版本方案：语义化 `MAJOR.MINOR.PATCH`，VERSION 文件管理，窗口标题自动读取

### ~11:55 — 初始化 Git 仓库 + 新建 CHANGELOG.md
- 问题：之前所有修改无版本记录，无法回退
- 处理：`git init`，`git_here.bat` 快捷命令；创建本文件；`.gitignore` 补充 `plugin.log`

### ~11:50 — 完成后退回再前进不显示「开始编号」
- 问题：编号完成后 `_exec_done=True`，退回去改参数再回到步骤4，按钮仍显示「✅ 完成」
- 处理：`_go_back()` 中从步骤4后退且 `_exec_done=True` 时重置为 `False`

### ~11:45 — 重新选择块后数据未彻底清除
- 问题：回到步骤0重新框选后，`type_tag`、`selected_types` 等残留旧值
- 处理：`_reselect_clear()` 补充清除所有字段 + 销毁旧 frame

### ~11:40 — 连上 CAD 后「读取当前选择」灰色
- 问题：`_do_connect` 漏了启用读取按钮
- 处理：加 `self._read_btn.config(state=tk.NORMAL)`

### ~11:35 — 新增「读取当前选择」功能
- 问题：用户需先在 CAD 选好块，插件直接读取，不能用 SelectOnScreen
- 处理：`acad_com.py` 加 `get_active_selection()`；`block_analyzer.py` 加 `read_active_blocks()`；步骤0加按钮

### ~11:25 — 回到步骤0按钮全灰
- 问题：`_do_select` 禁用 `_select_btn` 后回退到步骤0仍禁用
- 处理：`_refresh_step0_buttons()` 恢复按钮状态

### ~11:15 — 编号写入 CAD 不生效
- 问题：`set_attribute_value` 后 CAD 中编号没变
- 处理：`_write_numbers()` 加 `blk.Update()`；`number_instruments()` 加 `doc.Regen()`

### ~11:05 — 步骤2/3 空白
- 问题：步骤2 `ttk.Frame(canvas, bg=...)` 崩溃；步骤3 `pack`/`grid` 混用
- 处理：`tk.Frame` 替代；统一 `grid`

### ~10:55 — 窗口卡死、激活、关闭、缓存
- 问题：COM 阻塞 UI；点击任务栏不回前台；不能退出；上一步重新分析
- 处理：`root.update()` 松 UI；`lift()`+`focus_force()` 激活；`WM_DELETE_WINDOW`；frame 缓存

### ~10:35 — 进度条/耗时/异常兜底
- 问题：进度条不动；失败也报用时；异常导致按钮永灰
- 处理：删进度条；`success=False` 不记时间；`try/except` 包分析

### ~10:25 — tkraise 替代 grid_remove
- 问题：`grid_remove`/`grid` 切换 frame 状态丢失
- 处理：`tkraise()` 叠放

### ~10:10 — 自动顺延/排序/后退
- 问题：自动顺延时起始编号可编辑；类型不按字母排；完成后不能回退
- 处理：`_toggle_auto()`；排序改 `x[0].upper()`；去 `_exec_done` 后退限制

### ~09:50 — 多选类型统一编号
- 问题：选多种类型时每种独立编号，要求混在一起编
- 处理：`number_instruments()` 去掉按类型分组

### ~09:20 — 初始修复（按钮、滚动条、置顶、美化）
- 问题：按钮不变灰；滚动条包整个区域；`-topmost`；缺编号数量
- 处理：`_set_busy`；复选框单独滚动条；去 `-topmost`；加编号行；Vista 主题
