# 更新日志

按时间倒序排列。时间是 `echo %DATE% %TIME%` 查的实际系统时间。  
`~HH:MM` 表示按会话顺序估算，误差 ±15 分钟内。

---

## 2026-05-29

### 10:56 — v1.2.0 发布：编组逻辑重构 + UI 优化
- 新增：「同位置编组」「顺号编组」双按钮，区分自动合并与手动编组
- 新增：↑↓ 互换整个编组编号，不改块顺序
- 新增：渲染图圆圈调大（r=14），编号颜色区分（合并=金，手动=浅蓝）
- 新增：左键拖拽平移渲染图（带边界限制）
- 新增：`_merge_map` 独立存储合并对，不再混入 `_group_map`
- 修复：合并对的块进手动组后共享同一后缀（如 106A/106A 而非 106A/106B）
- 修复：编组后上移/下移导致组归属丢失
- 修复：merge_overlap 与手动编组冲突导致编号错乱
- 修复：渲染图高度不随窗口缩放
- 修复：点击选中卡顿（缓存类型值，避免每次调 COM）
- 修复：编号修改后右下角按钮未重置为「开始编号」
- 优化：操作汇总压缩为单行
- 优化：底部 log 区布局，minimap 占满可用空间
- 移除：`pack`/`grid` 混用导致的布局崩溃

## 2026-05-28

### 19:07 — 修复：第五步编组后编号错乱（手动组抢占最前编号位）
- 修复：在第五步预览中选中块「编为同组」后，同组块被放到 `eff_groups` 最前面，导致整列编号起始位被抢占
- 原因：构建有效分组时先遍历 `valid_mg.items()`（手动组），再处理独立块，未按索引顺序
- 修复：改为 `for i in range(n)` 按索引顺序遍历，遇到手动组则整组加入，独立块紧随其后
- 效果：编组后序列保持原有顺序，如 `103,104,105,106A,106B,107` 而非 `103A,103B,104,105,106,107`

## 2026-05-26

### 14:25 — 项目重组：插件独立文件夹 + 消除跨依赖
- 重构：将原根目录的仪表自动编号插件整体移入 `auto_numbering/` 独立文件夹
- 移动：`src/`、`run.py`、`scripts/`、`config/`、`releases/`、`VERSION`、`pyproject.toml` 等 20+ 文件
- 修复：`run.bat` 加 `cd /d "%~dp0"` 确保从自身目录运行
- 修复：`build.bat` 加 `cd /d "%~dp0\.."` 适配目录层级变化
- 修复：`batch_attr_color` 原运行期导入主项目 `BlockAnalyzer`，改为 `AcadConnect` 内置方法，彻底独立
- 清理：删除根目录旧源码残留（src/、run.py、config/、scripts/、releases/ 等）
- 新建：根目录 `README.md` 作为项目顶层索引

### 14:08 — 新增独立插件「批量修改块属性文字颜色」
- 新建 `batch_attr_color/` 独立文件夹，完整 4 步向导插件
- 功能：框选/读取 → 选属性标签 → 选颜色 → 批量修改块属性文字颜色
- 支持 ACI 颜色索引（20 种预设）、真彩色 RGB 自定义、ByLayer、ByBlock
- 代码架构完全复用主项目模式：COM 连接层、配置持久化、日志记录
- 色板含色块按钮实时预览，RGB 自定义输入带即时色块反馈
- 内置标签分析方法（无需依赖主项目 BlockAnalyzer）
- 支持「仅修改非空值」选项
- 界面风格与主项目一致：tkinter 向导、步骤缓存、回退保留

## 2026-05-23

### 16:27 — 排序模式 + 手动调序 + 同位置块合并编号
- 问题：只能按行优先排序，缺乏灵活性和可控性；同位置不同可见性的块需要同号
- 处理：
  - 重构排序引擎：`_sort_blocks_row_first` 拆分为 `_group_rows`（Y分组）+ `_sort_rows`（行内排序）
  - 新增 `sort_mode` 配置：`row_first`（行优先）、`selection_order`（选择顺序）
  - 新增 `first_block_handle` 配置：在 CAD 中点选块作为编号第一个
  - 新增 `merge_overlap` 配置：同位置不同可见性的块编相同号
  - 步骤④新增「调整块顺序」面板：分行动态 ↑↓ 调序，存储在 `_reorder_blocks`
  - 新增 `_skip_sort` 内参：手动调序后传已排序列表跳过引擎重排序
  - 新增 `_get_visibility_state`、`_group_by_position`、`_build_overlap_number_map`
  - 新增 `_sort_by_selection_order`、`_move_to_front`、`_sort_blocks` 方法
  - 修改 `_write_numbers` 支持 `number_map` 跳号
  - `_sort_blocks_row_first` 保留向下兼容包装，`SORT_MODE_SNAKE` 常量保留
  - 新增 6 项无 AutoCAD 单元测试验证排序逻辑
  - UI 步骤③下拉框改为「行优先 / 按选择顺序」，移除蛇形
  - UI 步骤③新增「☐ 合并同位置块」复选框 + 说明
  - UI 步骤④调序面板显示按行分组，↑↓按钮只能在同行内互换
  - 操作汇总显示排序模式 + 合并状态
  - 修复：连接 AutoCAD 后按钮改为「🔄 重新连接」，CAD 关闭后可随时重连
  - 修复：步骤③配置表单加滚动画布，避免底部控件被窗口高度截断

---

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
