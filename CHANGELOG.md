# 更新日志

所有对本插件的修改记录在此文件。

格式：`YYYY-MM-DD` — 改动描述（涉及文件）

---

## 2025-07-16 — 多轮功能修复与优化

### 按钮与导航
- 运行时「下一步」「上一步」变灰，退出按钮保持可用
- 去掉 `-topmost` 置顶，改为忙时 `lift()` + `focus_force()`，用户可自由切换应用
- 右上角 ✕ 捕获退出（`WM_DELETE_WINDOW`），运行时弹确认框
- 完成后「上一步」也可用（去掉 `_exec_done` 限制）
- 步骤切换改用 `tkraise()` 替代 `grid_remove()`/`grid()`，避免状态丢失

### 窗口行为
- 步骤帧缓存（回退保留用户选择，不重新分析）
- 重新选择块时 `_reselect_clear()` 彻底重置所有数据（含 `_exec_done`、`type_tag`、`selected_types`、`number_config`）
- 回到步骤0时 `_refresh_step0_buttons()` 恢复按钮状态
- 步骤1/2分析加 `try/except` 兜底，异常时仍可恢复

### 编号逻辑
- 多选类型改为统一序列编号（不再按类型独立编号）
- 编号写入后加 `blk.Update()` + `doc.Regen()`（修复写入CAD不生效）
- `_write_numbers` 加 `progress_cb`，每20块 `root.update()` 保持窗口响应
- `preview_numbering` 同步改为统一排序

### 步骤2（选择仪表类型）
- 排序改为纯字母序（`key=lambda x: x[0].upper()`）
- 修复 `ttk.Frame(canvas, bg=...)` 崩溃 → 改用 `tk.Frame`
- grid 行号连续（0→1→2→3，不再跳行）

### 步骤3（配置编号）
- 自动顺延勾选后禁用「起始编号」输入框
- 修复 `pack`/`grid` 混用导致空白

### 步骤4/5（执行编号）
- 操作汇总加「本次编号」行
- 修复完成后回退再前进不显示「开始编号」

### 步骤0（连接与选择）
- 新增「读取当前选择」按钮（读取 CAD 中预先选中的块）
- 新方法 `acad.get_active_selection()` 读取 `ActiveSelectionSet`
- 耗时统计仅记录成功操作（`_set_busy(False, success=True/False)`）

### 工程
- 初始化 Git 仓库
- `CHANGELOG.md` 创建
- `.gitignore` 加 `plugin.log`
- 创建 `git_here.bat` 快捷命令
