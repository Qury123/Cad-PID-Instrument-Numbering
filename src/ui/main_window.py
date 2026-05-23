#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主窗口 — 单窗口向导

所有操作集成在一个窗口内完成，分为 5 个步骤页面。
日志记录到文件 plugin.log，追加不覆盖。
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox as mb
import traceback
from datetime import datetime

from src.acad_com import AcadConnect, AcadConnectError
from src.block_analyzer import BlockAnalyzer
from src.numbering import NumberingEngine
from src.config import ConfigManager
from src.version import get_version

logger = logging.getLogger(__name__)

LOG_FILE = "plugin.log"


def write_log(message: str, level: str = "INFO") -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {level}: {message}\n")
    except Exception:
        pass


class MainWindow:
    """主窗口 — 单窗口向导"""

    def __init__(self) -> None:
        write_log("=" * 60)
        write_log("插件启动")
        try:
            self.root = tk.Tk()
            self.root.title(f"仪表自动编号插件 v{get_version()}")
            self.root.geometry("680x580")
            self.root.minsize(600, 520)
            # 关闭按钮可点击
            self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

            self.acad = None
            self.config_mgr = ConfigManager()
            self.memory = self.config_mgr.load()
            self.analyzer = None
            self.blocks = None
            self.all_tags = []
            self.tags_with_samples = {}
            self.type_counts = {}
            self.unique_values = []

            self.type_tag = ""
            self.number_tag = ""
            self.selected_types = []
            self.number_config = {}

            self._current_step = 0
            self._total_steps = 5
            self._exec_done = False
            self._busy = False
            # 缓存各步骤的 frame，用于回退时保留内容
            self._step_frames: list[ttk.Frame | None] = [None] * self._total_steps

            self._build_ui()
        except Exception as e:
            write_log(f"初始化失败: {e}\n{traceback.format_exc()}", "ERROR")
            raise

    def _on_closing(self) -> None:
        """关闭窗口"""
        if self._busy:
            if mb.askyesno("确认", "程序正在运行中，确定要退出吗？"):
                self.root.destroy()
        else:
            self.root.destroy()

    # ══════════════════════════════════════
    #  界面构建
    # ══════════════════════════════════════

    def _build_ui(self) -> None:
        """构建主界面"""
        # 样式
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")

        # 全局布局
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=0)
        self.root.grid_columnconfigure(0, weight=1)

        # ── ① 主容器 ──
        main = ttk.Frame(self.root, padding=(12, 12, 12, 0))
        main.grid(row=0, column=0, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # 步骤标题
        self._step_label = tk.Label(main, text="", font=("微软雅黑", 14, "bold"))
        self._step_label.grid(row=0, column=0, sticky="w", pady=(0, 10))

        # 步骤内容容器
        self._step_content = ttk.Frame(main)
        self._step_content.grid(row=1, column=0, sticky="nsew")
        self._step_content.grid_rowconfigure(0, weight=1)
        self._step_content.grid_columnconfigure(0, weight=1)

        # ── ③ 日志区 ──
        lf = ttk.Frame(self.root)
        lf.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 0))
        lf.grid_columnconfigure(0, weight=1)

        hdr = ttk.Frame(lf)
        hdr.grid(row=0, column=0, sticky="w")
        ttk.Label(hdr, text="运行日志：", font=("微软雅黑", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(hdr, text=f"({LOG_FILE})", foreground="#aaa",
                  font=("微软雅黑", 8)).pack(side=tk.LEFT, padx=(10, 0))

        tf = ttk.Frame(lf)
        tf.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        tf.grid_columnconfigure(0, weight=1)

        self._log_text = tk.Text(tf, height=5, font=("微软雅黑", 9),
                                 wrap=tk.WORD, state=tk.DISABLED,
                                 bg="#f8f8f8", relief=tk.SUNKEN, borderwidth=1)
        log_sb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_sb.set)
        self._log_text.tag_configure("error", foreground="red")
        self._log_text.tag_configure("warn", foreground="#d90")
        self._log_text.tag_configure("success", foreground="green")
        self._log_text.grid(row=0, column=0, sticky="ew")
        log_sb.grid(row=0, column=1, sticky="ns")

        # ── ④ 底部按钮栏 ──
        bf = ttk.Frame(self.root)
        bf.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 12))
        bf.grid_columnconfigure(0, weight=1)

        self._cancel_btn = ttk.Button(bf, text="退出", command=self._on_closing, width=10)
        self._cancel_btn.grid(row=0, column=0, sticky="w")

        self._back_btn = ttk.Button(bf, text="← 上一步", command=self._go_back,
                                    width=12, state=tk.DISABLED)
        self._back_btn.grid(row=0, column=1, sticky="e", padx=(0, 5))

        self._next_btn = ttk.Button(bf, text="下一步 →", command=self._go_next, width=14)
        self._next_btn.grid(row=0, column=2, sticky="e")

        self._show_step(0)

    # ══════════════════════════════════════
    #  步骤管理（缓存 frame，不销毁重建）
    # ══════════════════════════════════════

    def _show_step(self, step: int) -> None:
        """显示指定步骤（缓存 frame，不重复创建）"""
        self._current_step = step

        steps = [
            (self._step0_connect, "① 连接 AutoCAD 并框选块"),
            (self._step1_select_tags, "② 选择属性标签"),
            (self._step2_select_types, "③ 选择仪表类型"),
            (self._step3_config_number, "④ 配置编号格式"),
            (self._step4_execute, "⑤ 执行编号"),
        ]

        func, title = steps[step]
        self._step_label.config(text=title)

        # 首次访问则创建 frame
        if self._step_frames[step] is None:
            f = ttk.Frame(self._step_content)
            f.grid(row=0, column=0, sticky="nsew")
            self._step_frames[step] = f
            func()

        # 回到步骤0时恢复按钮状态（允许重新连接/选择）
        if step == 0:
            self._refresh_step0_buttons()

        # 把目标 frame 提到最前（所有 frame 在同一个 grid 单元格）
        self._step_frames[step].tkraise()

        self._update_buttons()

    def _update_buttons(self) -> None:
        # 上一步：不在第0步即可（完成后也能回退查看）
        can_back = self._current_step > 0
        self._back_btn.configure(state=tk.NORMAL if can_back else tk.DISABLED)

        # 下一步：已完成时只在最后一步显示「完成」
        if self._exec_done and self._current_step >= self._total_steps - 1:
            self._next_btn.config(text="✅ 完成", command=self.root.destroy,
                                  state=tk.NORMAL)
        elif self._current_step >= self._total_steps - 1:
            self._next_btn.config(text="🚀 开始编号", command=self._execute_numbering)
        else:
            self._next_btn.config(text="下一步 →", command=self._go_next,
                                  state=tk.NORMAL)

    def _set_busy(self, busy: bool, msg: str = "运行中...", success: bool = True) -> None:
        """切换忙状态"""
        self._busy = busy
        if busy:
            self._busy_start = datetime.now()
            self.root.lift()
            self.root.focus_force()
            self.root.update()
        elif success:
            elapsed = datetime.now() - self._busy_start
            secs = elapsed.total_seconds()
            if secs >= 1.0:
                self.log(f"完成 (用时 {secs:.1f} 秒)", "SUCCESS")

        state = tk.DISABLED if busy else tk.NORMAL
        self._next_btn.config(state=state)
        self._back_btn.config(state=state)
        self._cancel_btn.config(text=msg if busy else "退出")
        self.root.update()

    # ══════════════════════════════════════
    #  导航
    # ══════════════════════════════════════

    def _go_next(self) -> None:
        if self._current_step == 0:
            if self.acad is None or self.blocks is None:
                self.log("请先连接 AutoCAD 并框选块！", "WARN")
                return
        elif self._current_step == 1:
            if not self._save_tags_from_ui():
                return
        elif self._current_step == 2:
            if not self._save_types_from_ui():
                return
        elif self._current_step == 3:
            if not self._save_config_from_ui():
                return
        self._show_step(self._current_step + 1)

    def _go_back(self) -> None:
        if self._current_step > 0:
            # 从完成页退回去改参数时，重置完成状态（允许重新开始编号）
            if self._current_step >= self._total_steps - 1 and self._exec_done:
                self._exec_done = False
                self.log("已重置编号状态，可以再次调整参数后重新编号", "INFO")
            self._show_step(self._current_step - 1)

    # ══════════════════════════════════════
    #  步骤 0
    # ══════════════════════════════════════

    def _step0_connect(self) -> None:
        f = self._step_frames[self._current_step]

        ttk.Label(f, text="在 AutoCAD 中框选或选中带属性的仪表块，然后点击下方按钮读取。\n"
                   "方式一：框选块 → CAD 中框选（右键结束）\n"
                   "方式二：先手动在 CAD 选中，再点「读取当前选择」",
                   font=("微软雅黑", 9), foreground="#555",
                   ).pack(anchor=tk.W, pady=(0, 12))

        self._conn_status = tk.Label(f, text="🔴 未连接", font=("微软雅黑", 10))
        self._conn_status.pack(anchor=tk.W)
        self._conn_detail = tk.Label(f, text="", font=("微软雅黑", 9), fg="#888")
        self._conn_detail.pack(anchor=tk.W, pady=(3, 10))

        bf = ttk.Frame(f)
        bf.pack(fill=tk.X)
        self._connect_btn = ttk.Button(bf, text="🔌 连接 AutoCAD",
                                       command=self._do_connect, width=18)
        self._connect_btn.pack(side=tk.LEFT, padx=(0, 10))
        self._select_btn = ttk.Button(bf, text="📦 框选块",
                                      command=self._do_select, width=14,
                                      state=tk.DISABLED)
        self._select_btn.pack(side=tk.LEFT, padx=(0, 8))
        self._read_btn = ttk.Button(bf, text="📋 读取当前选择",
                                    command=self._do_read, width=16,
                                    state=tk.DISABLED)
        self._read_btn.pack(side=tk.LEFT)

        self._sel_result = tk.Label(f, text="", font=("微软雅黑", 9), fg="#888")
        self._sel_result.pack(anchor=tk.W, pady=(8, 0))

    def _refresh_step0_buttons(self) -> None:
        """回到步骤0时恢复按钮状态"""
        if hasattr(self, '_connect_btn'):
            if self.acad is None:
                self._connect_btn.config(state=tk.NORMAL)
                self._select_btn.config(state=tk.DISABLED)
                self._read_btn.config(state=tk.DISABLED)
            else:
                self._connect_btn.config(state=tk.DISABLED)
                self._select_btn.config(state=tk.NORMAL)
                self._read_btn.config(state=tk.NORMAL)
                if self.blocks is not None:
                    self._sel_result.config(
                        text=f"✅ 已选中 {len(self.blocks)} 个带属性块", fg="green")

    def _reselect_clear(self) -> None:
        """重新选择块时清除旧的分析数据和步骤缓存"""
        # 清除分析数据
        self.all_tags = []
        self.tags_with_samples = {}
        self.unique_values = []
        self.type_counts = {}
        # 清除用户选择
        self.type_tag = ""
        self.number_tag = ""
        self.selected_types = []
        self.number_config = {}
        # 清除状态
        self._exec_done = False
        # 销毁旧 frame（避免残留遮挡新 frame）
        for i in range(1, self._total_steps):
            if self._step_frames[i] is not None:
                try:
                    self._step_frames[i].destroy()
                except Exception:
                    pass
                self._step_frames[i] = None

    def _do_read(self) -> None:
        """读取 CAD 当前选中对象"""
        if self.acad is None:
            return
        self._set_busy(True, "读取中...")
        self.log("正在读取 CAD 当前选择...")
        self.root.update()

        try:
            self.analyzer = BlockAnalyzer(self.acad)
            self.blocks = self.analyzer.read_active_blocks()
        except Exception as e:
            self.log(f"读取失败: {e}", "ERROR")
            self._sel_result.config(text=f"❌ 读取失败: {e}", fg="red")
            write_log(f"读取失败: {e}\n{traceback.format_exc()}", "ERROR")
            self._set_busy(False, success=False)
            return

        if not self.blocks:
            self.log("当前选中中没有带属性的块", "WARN")
            self._sel_result.config(text="⚠️ 无选中块，请先在 CAD 中选中再点击", fg="#d90")
            mb.showwarning("提示", "当前选中中没有带属性的仪表块。\n请在 AutoCAD 中先选中块，再重试。")
            self._set_busy(False, success=False)
            return

        self._reselect_clear()
        self.log(f"读取到 {len(self.blocks)} 个带属性块", "SUCCESS")
        write_log(f"读取选择: {len(self.blocks)} 个带属性块")
        self._sel_result.config(text=f"✅ 已读取 {len(self.blocks)} 个带属性块", fg="green")
        self._set_busy(False)

    def _do_connect(self) -> None:
        self._set_busy(True, "连接中...")
        self.log("正在连接 AutoCAD...")
        self._conn_status.config(text="⏳ 连接中...", fg="#fa0")
        self.root.update()

        try:
            self.acad = AcadConnect()
        except AcadConnectError as e:
            self.log(f"连接失败: {e}", "ERROR")
            self._conn_status.config(text="🔴 连接失败", fg="red")
            write_log(f"连接失败: {e}", "ERROR")
            mb.showerror("连接失败", str(e))
            self._set_busy(False, success=False)
            return

        doc_name = self.acad.get_document_name()
        self.log(f"已连接到: {doc_name}", "SUCCESS")
        write_log(f"已连接到 AutoCAD: {doc_name}")
        self._conn_status.config(text="🟢 已连接", fg="green")
        self._conn_detail.config(text=f"文档: {doc_name}")
        self._connect_btn.config(state=tk.DISABLED)
        self._select_btn.config(state=tk.NORMAL)
        self._read_btn.config(state=tk.NORMAL)
        self._set_busy(False)

    def _do_select(self) -> None:
        if self.acad is None:
            return
        self._set_busy(True, "等待AutoCAD选择...")
        self.log("请在 AutoCAD 中框选仪表块（右键结束选择）...")
        self._sel_result.config(text="⏳ 请切换到 AutoCAD 进行框选...", fg="#fa0")
        self.root.update()

        try:
            self.analyzer = BlockAnalyzer(self.acad)
            self.blocks = self.analyzer.select_blocks(
                prompt_text="\n请框选要编号的仪表块（右键结束选择）..."
            )
        except AcadConnectError as e:
            self.log(f"选择失败: {e}", "ERROR")
            self._sel_result.config(text=f"❌ 选择失败: {e}", fg="red")
            write_log(f"选择失败: {e}", "ERROR")
            self._set_busy(False, success=False)
            return

        if not self.blocks:
            self.log("未选中任何带属性的块", "WARN")
            self._sel_result.config(text="⚠️ 未选中带属性的块，请重试", fg="#d90")
            mb.showwarning("提示", "未选中任何带属性的块。")
            self._set_busy(False, success=False)
            return

        # 清除旧的分析数据（新块不完全一样）
        self.all_tags = []
        self.tags_with_samples = {}
        self.unique_values = []
        self.type_counts = {}
        self._step_frames[1] = None  # 清除步骤1~4的缓存，下次进入重新分析
        self._step_frames[2] = None
        self._step_frames[3] = None
        self._step_frames[4] = None

        self._reselect_clear()
        self.log(f"选中 {len(self.blocks)} 个带属性块", "SUCCESS")
        write_log(f"框选成功: {len(self.blocks)} 个带属性块")
        self._sel_result.config(text=f"✅ 已选中 {len(self.blocks)} 个带属性块", fg="green")
        self._select_btn.config(state=tk.DISABLED)
        self._set_busy(False)

    # ══════════════════════════════════════
    #  步骤 1（缓存数据，回退不重新分析）
    # ══════════════════════════════════════

    def _step1_select_tags(self) -> None:
        f = self._step_frames[self._current_step]

        ttk.Label(f, text="选择「仪表类型」和「编号」分别对应哪个标签。\n"
                   "选好后直接点「下一步」。",
                   font=("微软雅黑", 9), foreground="#555",
                   ).pack(anchor=tk.W, pady=(0, 10))

        # 仅首次进入时分析标签
        if not self.all_tags:
            self._set_busy(True, "正在分析...")
            self.log("正在分析属性标签...")
            self.root.update()
            try:
                self.all_tags = self.analyzer.get_all_tags(self.blocks)
                self.tags_with_samples = {}
                for tag in self.all_tags:
                    self.tags_with_samples[tag] = self.analyzer.get_tag_sample_values(
                        self.blocks, tag, 5)
                self.log(f"发现 {len(self.all_tags)} 个属性标签", "SUCCESS")
                self._set_busy(False)
            except Exception as e:
                self.log(f"分析标签失败: {e}", "ERROR")
                write_log(f"分析标签失败: {e}\n{traceback.format_exc()}", "ERROR")
                self._set_busy(False, success=False)
                mb.showerror("分析错误", f"读取属性标签失败:\n{e}")

        tk.Label(f, text="① 仪表类型标签：", font=("微软雅黑", 10, "bold")).pack(anchor=tk.W)
        self._type_var = tk.StringVar()
        self._type_combo = ttk.Combobox(f, textvariable=self._type_var,
                                        values=self.all_tags, state="readonly",
                                        width=60, font=("微软雅黑", 9))
        self._type_combo.pack(fill=tk.X, pady=(0, 2))
        self._type_preview = tk.Label(f, text="", fg="#888", font=("微软雅黑", 9))
        self._type_preview.pack(anchor=tk.W, pady=(0, 8))

        tk.Label(f, text="② 编号标签：", font=("微软雅黑", 10, "bold")).pack(anchor=tk.W)
        self._num_var = tk.StringVar()
        self._num_combo = ttk.Combobox(f, textvariable=self._num_var,
                                       values=self.all_tags, state="readonly",
                                       width=60, font=("微软雅黑", 9))
        self._num_combo.pack(fill=tk.X, pady=(0, 2))
        self._num_preview = tk.Label(f, text="", fg="#888", font=("微软雅黑", 9))
        self._num_preview.pack(anchor=tk.W, pady=(0, 8))

        # 记忆值
        lt = self.memory.get("last_type_tag", "")
        ln = self.memory.get("last_number_tag", "")
        if lt in self.all_tags:
            self._type_var.set(lt)
        elif self.all_tags:
            self._type_var.set(self.all_tags[0])
        if ln in self.all_tags:
            self._num_var.set(ln)
        elif len(self.all_tags) > 1:
            self._num_var.set(self.all_tags[1])

        # 提示文本（必须在 _update_tp 前创建）
        self._tag_hint = tk.Label(f, text="", font=("微软雅黑", 9))
        self._tag_hint.pack(anchor=tk.W, pady=(5, 0))

        self._type_combo.bind("<<ComboboxSelected>>",
            lambda e: self._update_tp(self._type_var.get(), self._type_preview))
        self._num_combo.bind("<<ComboboxSelected>>",
            lambda e: self._update_tp(self._num_var.get(), self._num_preview))
        self._update_tp(self._type_var.get(), self._type_preview)
        self._update_tp(self._num_var.get(), self._num_preview)

    def _update_tp(self, tag: str, label: tk.Label) -> None:
        s = self.tags_with_samples.get(tag, [])
        label.config(text=f"示例值: {', '.join(s[:5])}" if s else "（暂无示例值）")
        self._update_tag_hint()

    def _update_tag_hint(self) -> None:
        t, n = self._type_var.get(), self._num_var.get()
        if t and n and t != n:
            self._tag_hint.config(text=f"⏩ 将用「{t}」识别类型，写入编号到「{n}」", fg="#2a7")
        elif t and n and t == n:
            self._tag_hint.config(text="⚠️ 两个标签不能相同", fg="#d90")
        else:
            self._tag_hint.config(text="请选择两个不同的属性标签", fg="#888")

    def _save_tags_from_ui(self) -> bool:
        t = self._type_var.get().strip()
        n = self._num_var.get().strip()
        if not t or not n:
            mb.showwarning("提示", "请分别选择「仪表类型标签」和「编号标签」。")
            return False
        if t == n:
            mb.showwarning("提示", "两个标签不能相同。")
            return False
        self.type_tag = t
        self.number_tag = n
        self.log(f"已选择: 类型=【{t}】, 编号=【{n}】", "SUCCESS")
        write_log(f"标签选择: 类型={t}, 编号={n}")
        self.config_mgr.save_tags(t, n)
        return True

    # ══════════════════════════════════════
    #  步骤 2（缓存数据，回退不重新分析）
    # ══════════════════════════════════════

    def _step2_select_types(self) -> None:
        f = self._step_frames[self._current_step]

        ttk.Label(f, text=f"属性标签「{self.type_tag}」检测到以下类型值。\n"
                   "勾选需要编号的类型。选好直接点「下一步」。",
                   font=("微软雅黑", 9), foreground="#555",
                   ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        # 仅首次进入时分析
        if not self.unique_values:
            self._set_busy(True, "正在分析...")
            self.log("正在提取类型值...")
            self.root.update()
            try:
                self.unique_values = self.analyzer.get_unique_values(self.blocks, self.type_tag)
                self.type_counts = {}
                for blk in self.blocks:
                    val = self.acad.get_attribute_value(blk, self.type_tag)
                    if val and val.strip():
                        self.type_counts[val.strip()] = self.type_counts.get(val.strip(), 0) + 1
                    # 每20个块处理一下窗口事件（保持窗口响应）
                    if len(self.type_counts) % 20 == 0:
                        self.root.update()
                self.log(f"共 {len(self.unique_values)} 种类型", "SUCCESS")
                self._set_busy(False)
            except Exception as e:
                self.log(f"提取类型值失败: {e}", "ERROR")
                write_log(f"提取类型值失败: {e}\n{traceback.format_exc()}", "ERROR")
                self._set_busy(False, success=False)
                mb.showerror("分析错误", f"读取类型值失败:\n{e}")

        if not self.unique_values:
            self.log(f"标签「{self.type_tag}」没有非空值", "ERROR")
            mb.showwarning("提示", f"标签「{self.type_tag}」在所有块中都没有非空值。")
            return

        # 可滚动复选框列表
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure(0, weight=1)

        cf = ttk.Frame(f)
        cf.grid(row=1, column=0, sticky="nsew", pady=(5, 5))
        cf.grid_rowconfigure(0, weight=1)
        cf.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(cf, highlightthickness=0, relief=tk.SUNKEN, borderwidth=1)
        sb = ttk.Scrollbar(cf, orient=tk.VERTICAL, command=canvas.yview)
        sf = tk.Frame(canvas)

        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor=tk.NW)
        canvas.configure(yscrollcommand=sb.set)

        def _mw(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind("<MouseWheel>", _mw)
        sf.bind("<MouseWheel>", _mw)

        sorted_items = sorted(self.type_counts.items(), key=lambda x: x[0].upper())
        self._type_vars = {}
        last_types = set(self.memory.get("last_selected_types", []))

        for code, count in sorted_items:
            v = tk.BooleanVar(value=(code in last_types))
            self._type_vars[code] = v
            row_f = ttk.Frame(sf)
            row_f.pack(fill=tk.X, padx=8, pady=1)
            ttk.Checkbutton(row_f, text="", variable=v, width=2).pack(side=tk.LEFT)
            tk.Label(row_f, text=code, font=("微软雅黑", 10, "bold"), width=12
                     ).pack(side=tk.LEFT, padx=(0, 5))
            tk.Label(row_f, text=f"({count} 个块)", fg="#999", font=("微软雅黑", 9)
                     ).pack(side=tk.LEFT)

        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        # 全选/取消
        bf = ttk.Frame(f)
        bf.grid(row=2, column=0, sticky="w", pady=(3, 0))
        ttk.Button(bf, text="☑ 全选", command=lambda: self._toggle_types(True), width=10
                   ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(bf, text="☐ 取消全选", command=lambda: self._toggle_types(False), width=10
                   ).pack(side=tk.LEFT)

        self._type_hint = tk.Label(f, text="", font=("微软雅黑", 9))
        self._type_hint.grid(row=3, column=0, sticky="w", pady=(3, 0))
        self._update_type_hint()

    def _toggle_types(self, val: bool) -> None:
        for v in self._type_vars.values():
            v.set(val)
        self._update_type_hint()

    def _update_type_hint(self) -> None:
        sel = [c for c, v in self._type_vars.items() if v.get()]
        if sel:
            total = sum(self.type_counts[t] for t in sel)
            self._type_hint.config(text=f"已选 {len(sel)} 种，共 {total} 个块 → 点「下一步」继续", fg="#2a7")
        else:
            self._type_hint.config(text="请勾选需要编号的类型", fg="#888")

    def _save_types_from_ui(self) -> bool:
        sel = [c for c, v in self._type_vars.items() if v.get()]
        if not sel:
            mb.showwarning("提示", "请至少选择一种需要编号的仪表类型。")
            return False
        self.selected_types = sel
        self.log(f"选择了 {len(sel)} 种: {', '.join(sel)}", "SUCCESS")
        write_log(f"类型选择: {sel}")
        self.config_mgr.save_types(sel)
        return True

    # ══════════════════════════════════════
    #  步骤 3
    # ══════════════════════════════════════

    def _step3_config_number(self) -> None:
        f = self._step_frames[self._current_step]

        types_str = ", ".join(self.selected_types)
        tk.Label(f, text=f"将对以下类型独立编号: {types_str}",
                 font=("微软雅黑", 9), fg="#555"
                 ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))

        lc = self.memory.get("last_number_config", {})
        self._cfg_entries = {}

        fields = [
            ("编号前缀", "prefix", lc.get("prefix", ""), "如 PT-、TE-，留空不加"),
            ("起始编号", "start_number", lc.get("start_number", 1), "从几开始（≥1）"),
            ("补零位数", "pad_width", lc.get("pad_width", 3), "如 3→001，0=不补零"),
            ("Y 容差", "y_tolerance", lc.get("y_tolerance", 50.0), "Y差在此范围内视为同行(mm)"),
        ]

        for i, (label, key, default, hint) in enumerate(fields):
            row = i + 1
            tk.Label(f, text=label, font=("微软雅黑", 10)
                     ).grid(row=row, column=0, sticky=tk.W, pady=(0, 8))
            e = ttk.Entry(f, width=22, font=("微软雅黑", 10))
            e.insert(0, str(default))
            e.grid(row=row, column=1, sticky=tk.W, padx=(10, 5), pady=(0, 8))
            tk.Label(f, text=hint, fg="#888", font=("微软雅黑", 8)
                     ).grid(row=row, column=2, sticky=tk.W, padx=(5, 0), pady=(0, 8))
            self._cfg_entries[key] = e

        off = len(fields) + 1  # 表单占用了 row 1~4，后续从 row 5 开始
        self._auto_var = tk.BooleanVar(value=lc.get("auto_continue", True))
        self._auto_var.trace_add("write", lambda *_: self._toggle_auto())
        tk.Checkbutton(f, text="自动顺延：从现有编号最大值+1开始",
                       variable=self._auto_var, font=("微软雅黑", 9)
                       ).grid(row=off, column=0, columnspan=3, sticky=tk.W, pady=(8, 2))
        tk.Label(f, text="勾选后「起始编号」字段将被忽略",
                 fg="#999", font=("微软雅黑", 8)
                 ).grid(row=off+1, column=0, columnspan=3, sticky=tk.W, padx=(20, 0))

        tk.Label(f, text="编号预览：", font=("微软雅黑", 9, "bold")
                 ).grid(row=off+2, column=0, sticky=tk.W, pady=(8, 0))
        self._preview_var = tk.StringVar()
        tk.Label(f, textvariable=self._preview_var, fg="#2a7",
                 font=("微软雅黑", 11, "bold")
                 ).grid(row=off+3, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))

        for e in self._cfg_entries.values():
            e.bind("<KeyRelease>", lambda ev: self._refresh_preview())
        self._auto_var.trace_add("write", lambda *_: self._refresh_preview())
        self._refresh_preview()
        self._toggle_auto()  # 应用初始状态（此时 _preview_var 已创建）

        tk.Label(f, text="配置好后点「下一步」", font=("微软雅黑", 9), fg="#888"
                 ).grid(row=off+4, column=0, sticky=tk.W, pady=(5, 0))

    def _toggle_auto(self) -> None:
        """自动顺延勾选后禁用起始编号输入框"""
        disabled = self._auto_var.get()
        state = tk.DISABLED if disabled else tk.NORMAL
        if "start_number" in self._cfg_entries:
            self._cfg_entries["start_number"].config(state=state)
        self._refresh_preview()

    def _get_cfg(self) -> dict:
        def gi(k, default, typ=int):
            try:
                return typ(self._cfg_entries[k].get())
            except (ValueError, KeyError):
                return default
        return {
            "prefix": self._cfg_entries["prefix"].get().strip(),
            "start_number": max(1, gi("start_number", 1, int)),
            "pad_width": max(0, gi("pad_width", 3, int)),
            "y_tolerance": max(1.0, gi("y_tolerance", 50.0, float)),
            "auto_continue": self._auto_var.get(),
        }

    def _fmt_preview(self, num: int, cfg: dict) -> str:
        s = str(num).zfill(cfg["pad_width"]) if cfg["pad_width"] > 0 else str(num)
        return f"{cfg['prefix']}{s}"

    def _refresh_preview(self) -> None:
        c = self._get_cfg()
        if c["auto_continue"]:
            self._preview_var.set(
                f"自动顺延 → {', '.join(self._fmt_preview(i,c) for i in range(1,4))}...")
        else:
            start = c["start_number"]
            self._preview_var.set(
                f"{', '.join(self._fmt_preview(i,c) for i in range(start,start+3))}...")

    def _save_config_from_ui(self) -> bool:
        c = self._get_cfg()
        if c["start_number"] < 1:
            mb.showwarning("提示", "起始编号必须 ≥ 1"); return False
        if c["pad_width"] < 0:
            mb.showwarning("提示", "补零位数不能为负数"); return False
        if c["y_tolerance"] < 1.0:
            mb.showwarning("提示", "Y容差至少为 1.0"); return False
        self.number_config = c
        self.log(f"编号配置: 前缀=「{c['prefix']}」 起始={c['start_number']} "
                 f"补零={c['pad_width']}位 容差={c['y_tolerance']}", "SUCCESS")
        write_log(f"编号配置: {c}")
        self.config_mgr.save_number_config(c)
        return True

    # ══════════════════════════════════════
    #  步骤 4
    # ══════════════════════════════════════

    def _step4_execute(self) -> None:
        f = self._step_frames[self._current_step]

        tk.Label(f, text="最终确认后点击「开始编号」",
                 font=("微软雅黑", 9), fg="#555").pack(anchor=tk.W, pady=(0, 10))

        to_number = sum(self.type_counts.get(t, 0) for t in self.selected_types)
        info_frame = tk.LabelFrame(f, text="📋 操作汇总", padx=12, pady=8,
                                   font=("微软雅黑", 9, "bold"), fg="#2a7")
        info_frame.pack(fill=tk.X)

        lines = [
            f"框选块数:      {len(self.blocks)} 个",
            f"本次编号:      {to_number} 个",
            f"仪表类型标签:  {self.type_tag}",
            f"编号标签:      {self.number_tag}",
            f"需编号类型:    {', '.join(self.selected_types)}",
            f"编号格式:      前缀=「{self.number_config.get('prefix','')}」"
            f" 起始={self.number_config.get('start_number',1)}"
            f" 补零={self.number_config.get('pad_width',3)}位",
        ]
        for line in lines:
            tk.Label(info_frame, text=line, font=("微软雅黑", 9), anchor=tk.W,
                     fg="#333").pack(fill=tk.X, padx=5, pady=2)

        self._exec_label = tk.Label(f, text="", font=("微软雅黑", 10))
        self._exec_label.pack(anchor=tk.W, pady=(15, 0))

    def _execute_numbering(self) -> None:
        if not all([self.acad, self.blocks, self.type_tag, self.number_tag,
                    self.selected_types, self.number_config]):
            mb.showwarning("提示", "请先完成前面的所有步骤。")
            return

        self._set_busy(True, "编号中...")
        self.log("=" * 40)
        self.log("开始执行编号...")

        try:
            engine = NumberingEngine(self.acad)
            self.log("正在生成编号...")
            self.root.update()
            preview = engine.preview_numbering(
                block_refs=self.blocks, type_tag=self.type_tag,
                number_tag=self.number_tag, selected_types=self.selected_types,
                config=self.number_config)
            for t, entries in preview.items():
                self.log(f"  {t}: {len(entries)} 个块 → {entries[0][1] if entries else '无'}...")

            self.log("正在写入 AutoCAD...")
            self.root.update()
            results = engine.number_instruments(
                block_refs=self.blocks, type_tag=self.type_tag,
                number_tag=self.number_tag, selected_types=self.selected_types,
                config=self.number_config, progress_cb=self.root.update)

            total = sum(results.values())
            self.log("=" * 40)
            self.log(f"🎉 编号完成！共 {total} 个块", "SUCCESS")
            write_log(f"编号完成: 共{total}个块, 详情={results}")
            for t, c in sorted(results.items()):
                self.log(f"   {t}: {c} 个块")
            self.log("=" * 40)

            self._exec_label.config(text=f"🎉 成功编号 {total} 个仪表块！", fg="green")
            self.acad.prompt(f"\n✅ 仪表编号完成！共 {total} 个块。")

            self._exec_done = True
            self._update_buttons()

            mb.showinfo("编号完成",
                f"✅ 成功编号 {total} 个仪表块！\n\n"
                + "\n".join(f"  {t}: {c} 个" for t, c in sorted(results.items())))

        except Exception as e:
            self.log(f"编号失败: {e}", "ERROR")
            self.log(traceback.format_exc(), "ERROR")
            write_log(f"编号失败: {e}\n{traceback.format_exc()}", "ERROR")
            self._exec_label.config(text=f"❌ 编号失败: {e}", fg="red")
            mb.showerror("编号错误", f"编号失败:\n{e}")
        finally:
            self._set_busy(False, success=False)

    # ══════════════════════════════════════
    #  工具方法
    # ══════════════════════════════════════

    def log(self, message: str, level: str = "INFO") -> None:
        write_log(message, level)
        try:
            self._log_text.configure(state=tk.NORMAL)
            icons = {"ERROR": "❌ ", "WARN": "⚠️ ", "SUCCESS": "✅ ", "INFO": "  "}
            self._log_text.insert(tk.END, f"{icons.get(level,'')}{message}\n", level.lower())
            self._log_text.see(tk.END)
            self._log_text.configure(state=tk.DISABLED)
            self.root.update()
        except Exception:
            pass

    def show(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    MainWindow().show()
