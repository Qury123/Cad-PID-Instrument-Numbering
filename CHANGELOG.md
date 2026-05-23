# 更新日志

所有修改按时间倒序排列。  
每项包含：`YYYY-MM-DD HH:MM` — 问题描述 → 处理方式

---

## 2025-07-16

### 16:30 — 初始化 Git 仓库 + 新建 CHANGELOG.md
- 问题：之前所有修改无版本记录，无法回退
- 处理：`git init`，`git_here.bat` 快捷命令，创建本文件
- `.gitignore` 补充 `plugin.log`

### 16:00 — 完成后退回再前进不显示「开始编号」
- 问题：编号完成后 `_exec_done=True`，退回去改参数再回到步骤4，按钮仍显示「✅ 完成」，无法重新编号
- 处理：`_go_back()` 中判断如果从步骤4后退且 `_exec_done=True`，自动重置为 `False`

### 15:40 — 重新选择块后数据未彻底清除
- 问题：回到步骤0重新框选后，`type_tag`、`selected_types`、`number_config` 残留旧值，步骤4仍显示旧汇总
- 处理：`_reselect_clear()` 补充清除 `type_tag`、`number_tag`、`selected_types`、`number_config`；销毁步骤1~4的旧 frame 避免遮挡

### 15:10 — 连上 CAD 后「读取当前选择」灰色
- 问题：`_do_connect` 只启用了「框选块」，漏了启用「读取当前选择」
- 处理：`_do_connect()` 加 `self._read_btn.config(state=tk.NORMAL)`

### 14:50 — 新增「读取当前选择」功能
- 问题：用户需要在 CAD 先选好块，插件直接读取，不能用 `SelectOnScreen` 强制框选
- 处理：`acad_com.py` 新增 `get_active_selection()` 读取 `ActiveSelectionSet`；`block_analyzer.py` 新增 `read_active_blocks()`；步骤0加「📋 读取当前选择」按钮

### 14:20 — 回到步骤0按钮全灰，无法重新选择
- 问题：`_do_select` 成功后禁用 `_select_btn`，回退到步骤0时按钮仍禁用
- 处理：`_show_step(0)` 时调用 `_refresh_step0_buttons()` 恢复按钮状态（未连接→连接可用/选择灰，已连接→连接灰/选择可用/读取可用）

### 13:50 — 编号写入 CAD 不生效
- 问题：`set_attribute_value` 后 CAD 中编号没变，但插件提示「编号完成」
- 处理：`_write_numbers()` 写入后加 `blk.Update()`；`number_instruments()` 末尾加 `doc.Regen()`

### 13:30 — 步骤3（配置编号）空白
- 问题：同一容器混用 `.pack()` 和 `.grid()`，tkinter 报错静默失败
- 处理：全部改为 `.grid()`，行号连续

### 13:10 — 步骤2（选择仪表类型）看不到列表
- 问题：`ttk.Frame(canvas, bg="#fff")` 不支持 `bg` 参数，报错静默
- 处理：改为 `tk.Frame(canvas)`；grid 行号从 0→2→3→4 改为 0→1→2→3

### 12:50 — 窗口激活（点击任务栏弹不回前台）
- 问题：tkinter 窗口被 AutoCAD 遮挡后，点击任务栏不会自动弹到前台
- 处理：`_set_busy(True)` 时 `lift()` + `focus_force()`；`WM_DELETE_WINDOW` 捕获右上角✕

### 12:40 — 上一步重新运行分析（不保留用户选择）
- 问题：点「上一步」→ 页面销毁 → 重新调 AutoCAD 读数据，耗时且丢失选择
- 处理：缓存各步骤 frame（`_step_frames`），首次创建后不再销毁；分析数据（`all_tags`、`type_counts`）判空跳过

### 12:30 — 运行时窗口卡死不能拖拽缩放
- 问题：COM 调用阻塞 tkinter 主循环，窗口无法操作
- 处理：步骤1/2循环加 `self.root.update()`；`_write_numbers` 加 `progress_cb` 每20块调一次

### 12:20 — 耗时统计误报
- 问题：失败操作也输出「完成 (用时 X 秒)」
- 处理：`_set_busy(False, success=False)` 不记录时间；所有错误路径都加了 `success=False`

### 12:00 — 步骤1分析标签报断连错误后按钮全灰
- 问题：分析过程中 COM 异常没 catch，`_set_busy(False)` 没执行到，按钮永久灰
- 处理：步骤1/2分析包 `try/except`，异常时 `_set_busy(False, success=False)` + 弹错误框

### 11:50 — 进度条无用
- 问题：COM 阻塞时 `ttk.Progressbar` 不动画，毫无意义
- 处理：删除进度条，改为操作完成后输出用时（`完成 (用时 2.3 秒)`）

### 11:30 — 上一步→下一步→上一步变灰
- 问题：`grid_remove()`/`grid()` 切换 frame 有状态残留
- 处理：改用 `tkraise()` 叠放 frame

### 11:10 — 自动顺延时应禁用起始编号
- 问题：勾选自动顺延后「起始编号」仍可编辑，但实际不生效，误导用户
- 处理：`_toggle_auto()` 根据 `_auto_var` 切换 `start_number` Entry 的 `state`

### 10:50 — 类型排序不直观
- 问题：按数量降序排（`(-x[1], x[0])`），用户要找的代码不在预期位置
- 处理：改为纯字母升序（`key=lambda x: x[0].upper()`）

### 10:30 — 编号完成后上一步灰色
- 问题：`_update_buttons` 中 `can_back` 加了 `and not self._exec_done`
- 处理：去掉 `_exec_done` 限制，完成后也能回退查看

### 10:10 — 多选类型编号逻辑错误
- 问题：选中 PISA、PT、PG 等类型时每种独立编号（PISA-001,PT-001,PG-001），用户要求混在一起编（PISA-001, PT-002, PG-003）
- 处理：`number_instruments()` 和 `preview_numbering()` 去掉按类型分组，改为统一过滤→统一排序→统一编号

### 09:50 — 步骤5操作汇总缺少编号数量
- 问题：汇总只显示框选总块数，没显示本次会编号多少个
- 处理：加「本次编号」行，统计勾选类型的块数之和

### 09:40 — 运行时窗口置顶影响其他应用
- 问题：`-topmost: True` 导致窗口一直在最前，用户无法切换到 AutoCAD
- 处理：改为忙时 `lift()` + `focus_force()`，不设 `-topmost`

### 09:30 — 窗口整体美化
- 问题：界面太素
- 处理：`ttk.Style` 设 Vista 主题；标题加粗；标签加绿色；操作汇总用 `LabelFrame`

### 09:10 — 按钮禁用样式不统一
- 问题：ttk 的 `DISABLED` 状态在某些主题下看不出灰色
- 处理：统一用 `ttk.Button` + `state=tk.DISABLED`，依赖系统主题渲染

### 08:50 — 运行时按钮不变灰
- 问题：连接、分析等操作没有调用 `_set_busy`，按钮可点
- 处理：步骤1/2分析前后加 `_set_busy(True/False)`
