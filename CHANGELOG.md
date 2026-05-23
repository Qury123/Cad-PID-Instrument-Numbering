# 更新日志

所有修改按时间倒序排列。  
每项包含：日期 — 问题描述 → 处理方式

---

## 2026-05-23 — 多轮功能修复与优化（完整会话记录）

### 16. 初始化 Git 仓库 + 新建 CHANGELOG.md
- 问题：之前所有修改无版本记录，无法回退
- 处理：`git init`，`git_here.bat` 快捷命令，创建本文件；`.gitignore` 补充 `plugin.log`

### 15. 完成后退回再前进不显示「开始编号」
- 问题：编号完成后 `_exec_done=True`，退回去改参数再回到步骤4，按钮仍显示「✅ 完成」，无法重新编号
- 处理：`_go_back()` 中判断如果从步骤4后退且 `_exec_done=True`，自动重置为 `False`

### 14. 重新选择块后数据未彻底清除
- 问题：回到步骤0重新框选后，`type_tag`、`selected_types`、`number_config` 残留旧值，步骤4仍显示旧汇总
- 处理：`_reselect_clear()` 补充清除 `type_tag`、`number_tag`、`selected_types`、`number_config`；销毁步骤1~4的旧 frame 避免残影遮挡

### 13. 连上 CAD 后「读取当前选择」灰色
- 问题：`_do_connect` 只启用了「框选块」，漏了启用「读取当前选择」
- 处理：`_do_connect()` 加 `self._read_btn.config(state=tk.NORMAL)`

### 12. 新增「读取当前选择」功能
- 问题：用户需要在 CAD 先选好块，插件直接读取，不能用 `SelectOnScreen` 强制框选
- 处理：`acad_com.py` 新增 `get_active_selection()` 读取 `ActiveSelectionSet`；`block_analyzer.py` 新增 `read_active_blocks()`；步骤0加「📋 读取当前选择」按钮

### 11. 回到步骤0按钮全灰，无法重新选择
- 问题：`_do_select` 成功后禁用 `_select_btn`，回退到步骤0时按钮仍禁用
- 处理：`_show_step(0)` 时调用 `_refresh_step0_buttons()` 恢复按钮状态（未连接→连接可用/选择灰，已连接→连接灰/选择可用/读取可用）

### 10. 编号写入 CAD 不生效
- 问题：`set_attribute_value` 后 CAD 中编号没变，但插件提示「编号完成」
- 处理：`_write_numbers()` 写入后加 `blk.Update()`；`number_instruments()` 末尾加 `doc.Regen()`

### 9. 步骤3（配置编号）空白
- 问题：同一容器混用 `.pack()` 和 `.grid()`，tkinter 报错静默失败
- 处理：全部改为 `.grid()`，行号连续

### 8. 步骤2（选择仪表类型）看不到列表
- 问题：`ttk.Frame(canvas, bg="#fff")` 不支持 `bg` 参数，报错静默
- 处理：改为 `tk.Frame(canvas)`；grid 行号连续化

### 7. 窗口激活 + 右上角关闭 + 步骤帧缓存
- 问题：点击任务栏弹不回前台；运行时不能退出；上一步重新运行分析
- 处理：`_set_busy(True)` 时 `lift()` + `focus_force()`；`WM_DELETE_WINDOW` 捕获✕；缓存各步骤 frame，分析数据判空跳过

### 6. 运行时窗口卡死不能拖拽缩放
- 问题：COM 调用阻塞 tkinter 主循环，窗口无法操作
- 处理：步骤1/2循环加 `self.root.update()`；`_write_numbers` 加 `progress_cb` 每20块调一次

### 5. 耗时统计误报 + 异常致按钮永灰 + 进度条无用
- 问题：失败也输出「用时」；COM 异常没 catch 按钮永灰；进度条不动画
- 处理：`_set_busy(False, success=False)` 不记时间；步骤1/2分析包 `try/except`；删除进度条

### 4. 步骤帧切换用 tkraise 替代 grid_remove
- 问题：`grid_remove()`/`grid()` 切换 frame 状态丢失，上一步/下一步按钮异常
- 处理：改用 `tkraise()` 叠放 frame，所有 frame 在同一 grid 单元格

### 3. 自动顺延禁用起始编号 + 类型纯字母排序 + 编号完成后可退
- 问题：勾选自动顺延后起始编号仍可编辑；类型按数量排不直观；完成后不能回退
- 处理：`_toggle_auto()` 切换 Entry state；排序改为 `key=lambda x: x[0].upper()`；去掉 `_exec_done` 对 back 的限制

### 2. 多选类型改为统一序列编号
- 问题：选中 PISA、PT、PG 时每种独立编号（PISA-001,PT-001,PG-001），用户要求混在一起
- 处理：`number_instruments()` 和 `preview_numbering()` 去掉按类型分组，统一过滤→统一排序→统一编号

### 1. 初始问题修复（按钮禁用、滚动条范围、窗口置顶、美化等）
- 按钮禁用样式不统一；运行时按钮不变灰；滚动条包了整个区域而不是仅复选框列表；`-topmost` 影响其他应用；步骤5缺编号数量
- 处理：统一 `state=tk.DISABLED`；各操作前后加 `_set_busy`；复选框单独滚动条；去掉 `-topmost`；加「本次编号」行；Vista 主题美化
