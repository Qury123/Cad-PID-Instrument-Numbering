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

    def _set_busy(self, busy: bool, msg: str = "运行中...", success: bool = True, no_focus: bool = False) -> None:
        """切换忙状态

        Args:
            no_focus: True 时不 lift/focus_force（用于即将与 CAD 交互的场景，避免抢焦点导致死锁）
        """
        self._busy = busy
        if busy:
            self._busy_start = datetime.now()
            if not no_focus:
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
        # 清除后续步骤的缓存（因为前面步骤的数据变了，需要重新生成）
        next_step = self._current_step + 1
        for i in range(next_step, self._total_steps):
            if self._step_frames[i] is not None:
                try:
                    self._step_frames[i].destroy()
                except Exception:
                    pass
                self._step_frames[i] = None
        self._show_step(next_step)

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
                self._connect_btn.config(text="🔌 连接 AutoCAD", state=tk.NORMAL)
                self._select_btn.config(state=tk.DISABLED)
                self._read_btn.config(state=tk.DISABLED)
                self._conn_status.config(text="🔴 未连接", fg="red")
            else:
                self._connect_btn.config(text="🔄 重新连接", state=tk.NORMAL)
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
        self._set_busy(True, "连接中...", no_focus=True)
        self.log("正在连接 AutoCAD...")
        self._conn_status.config(text="⏳ 连接中...", fg="#fa0")
        self.root.update()

        # 先检测 acad.exe 进程是否存在
        try:
            import subprocess
            proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq acad.exe", "/NH"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            if "acad.exe" not in proc.stdout.lower():
                self.log("未检测到 AutoCAD 进程", "ERROR")
                self._conn_status.config(text="🔴 AutoCAD 未运行", fg="red")
                write_log("AutoCAD 未运行", "ERROR")
                mb.showwarning("提示",
                    "未检测到正在运行的 AutoCAD。\n"
                    "请先启动 AutoCAD，然后点击「重新连接」。")
                self._set_busy(False, success=False)
                return
        except Exception:
            pass  # tasklist 不可用则跳过检测

        self.log("检测到 AutoCAD 进程，正在连接...")
        self.root.update()

        try:
            self.acad = AcadConnect()
        except AcadConnectError as e:
            err_msg = str(e)
            self.log(f"连接失败: {err_msg}", "ERROR")
            self._conn_status.config(text="🔴 连接失败", fg="red")
            write_log(f"连接失败: {err_msg}", "ERROR")
            mb.showerror("连接失败", err_msg)
            self._set_busy(False, success=False)
            return
        except Exception as e:
            err_msg = str(e)
            self.log(f"连接失败(未知错误): {err_msg}", "ERROR")
            self._conn_status.config(text="🔴 连接失败", fg="red")
            write_log(f"连接失败: {err_msg}", "ERROR")
            mb.showerror("连接失败", f"未知错误:\n{err_msg}")
            self._set_busy(False, success=False)
            return
        doc_name = self.acad.get_document_name()
        self.log(f"已连接到: {doc_name}", "SUCCESS")
        write_log(f"已连接到 AutoCAD: {doc_name}")
        self._conn_status.config(text="🟢 已连接", fg="green")
        self._conn_detail.config(text=f"文档: {doc_name}")
        self._connect_btn.config(text="🔄 重新连接", state=tk.NORMAL)
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

        # 按首字母分组（XV 单独列出，不归入 X 组）
        groups: Dict[str, list] = {}
        for code, count in sorted_items:
            upper = code.upper()
            if upper.startswith("XV"):
                prefix = "XV"
            else:
                prefix = code[:1].upper()
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append((code, count))

        for prefix in sorted(groups.keys()):
            items = groups[prefix]
            gf = tk.LabelFrame(sf, text=f"「{prefix}」开头 ({len(items)}种)",
                               font=("微软雅黑", 9, "bold"),
                               fg="#a52" if prefix in ("X", "XV") else "#25a",
                               padx=6, pady=4)
            gf.pack(fill=tk.X, padx=6, pady=4)
            # 组内全选/取消（X / XV 组只有取消，没有全选）
            gf_top = tk.Frame(gf)
            gf_top.pack(fill=tk.X)
            gf_body = tk.Frame(gf)
            gf_body.pack(fill=tk.X)
            if prefix not in ("X", "XV"):
                tk.Button(gf_top, text="☑全选", font=("微软雅黑", 7), width=4,
                          command=lambda grp=items: [
                              self._type_vars.get(c, tk.BooleanVar()).set(True)
                              for c, _ in grp if c in self._type_vars
                          ]).pack(side=tk.RIGHT, padx=(0, 2))
            tk.Button(gf_top, text="取消", font=("微软雅黑", 7), width=4,
                      command=lambda grp=items: [
                          self._type_vars.get(c, tk.BooleanVar()).set(False)
                          for c, _ in grp if c in self._type_vars
                      ]).pack(side=tk.RIGHT, padx=(0, 5))
            for code, count in items:
                v = tk.BooleanVar(value=(code in last_types))
                self._type_vars[code] = v
                row_f = ttk.Frame(gf_body)
                row_f.pack(fill=tk.X, pady=1)
                ttk.Checkbutton(row_f, text="", variable=v, width=2).pack(side=tk.LEFT)
                tk.Label(row_f, text=code, font=("微软雅黑", 10, "bold"), width=14
                         ).pack(side=tk.LEFT, padx=(0, 5))
                tk.Label(row_f, text=f"({count} 个)", fg="#999", font=("微软雅黑", 9)
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
        outer = self._step_frames[self._current_step]

        # 可滚动画布包裹（配置项太多，窗口高度不够）
        canvas = tk.Canvas(outer, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        f = tk.Frame(canvas)  # 内部容器 — 后续代码全部用 f
        f.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=f, anchor=tk.NW)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        # 鼠标滚轮
        def _mw(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _mw)

        types_str = ", ".join(self.selected_types)
        tk.Label(f, text=f"将对以下类型独立编号: {types_str}",
                 font=("微软雅黑", 9), fg="#555"
                 ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))

        lc = self.memory.get("last_number_config", {})
        self._cfg_entries = {}

        fields = [
            ("编号开头", "prefix", lc.get("prefix", ""), "如 2CH-、PT-，留空则无前缀"),
            ("起始数字", "start_number", lc.get("start_number", 1), "从几开始编（≥1）"),
            ("编号位数", "pad_width", lc.get("pad_width", 3), "3→001，0→1、2、3..."),
            ("行距范围", "y_tolerance", lc.get("y_tolerance", 50.0), "两个块差多少毫米以内算同一排"),
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

        off = len(fields) + 1

        tk.Label(f, text="编号预览：", font=("微软雅黑", 9, "bold")
                 ).grid(row=off, column=0, sticky=tk.W, pady=(8, 0))
        self._preview_var = tk.StringVar()
        tk.Label(f, textvariable=self._preview_var, fg="#2a7",
                 font=("微软雅黑", 11, "bold")
                 ).grid(row=off+1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))

        for e in self._cfg_entries.values():
            e.bind("<KeyRelease>", lambda ev: self._refresh_preview())
        self._refresh_preview()

        # ── 排序模式 ──
        sr = off + 5  # start row for new section
        ttk.Separator(f, orient=tk.HORIZONTAL).grid(
            row=sr, column=0, columnspan=3, sticky="ew", pady=(12, 8))

        tk.Label(f, text="排序模式：", font=("微软雅黑", 10, "bold")
                 ).grid(row=sr+1, column=0, sticky=tk.W)
        sort_mode_labels = ["行优先（默认）", "按选择顺序"]
        sort_mode_values = ["row_first", "selection_order"]
        self._sort_mode_var = tk.StringVar(
            value=lc.get("sort_mode", "row_first"))
        sort_combo = ttk.Combobox(f, textvariable=self._sort_mode_var,
                                  values=sort_mode_labels, state="readonly",
                                  width=22, font=("微软雅黑", 10))
        sort_combo.grid(row=sr+1, column=1, sticky=tk.W, padx=(10, 5))
        # 把显示值映射到存储值
        self._sort_display_map = dict(zip(sort_mode_labels, sort_mode_values))
        self._sort_value_map = dict(zip(sort_mode_values, sort_mode_labels))
        # 根据存储值设置显示
        stored = lc.get("sort_mode", "row_first")
        sort_combo.set(self._sort_value_map.get(stored, sort_mode_labels[0]))
        sort_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_preview())

        sort_hints = {
            "row_first": "从上到下分行，同行从左到右",
            "selection_order": "保持框选时点击的顺序",
        }
        self._sort_hint_label = tk.Label(
            f, text=sort_hints.get(stored, ""),
            fg="#888", font=("微软雅黑", 8))
        self._sort_hint_label.grid(row=sr+1, column=2, sticky=tk.W, padx=(5, 0))

        def _update_sort_hint(*_):
            display = self._sort_mode_var.get()
            stored_val = self._sort_display_map.get(display, "row_first")
            self._sort_hint_label.config(text=sort_hints.get(stored_val, ""))
        self._sort_mode_var.trace_add("write", _update_sort_hint)

        # ── 指定首个块 ──
        # ── 合并同位置块 ──
        self._merge_var = tk.BooleanVar(value=lc.get("merge_overlap", False))
        tk.Checkbutton(
            f, text="☐ 合并编号：靠近且类型首字母相同的块编同一个号",
            variable=self._merge_var, font=("微软雅黑", 9)
        ).grid(row=sr+2, column=0, columnspan=4, sticky=tk.W, pady=(8, 2))
        self._merge_dist_var = tk.StringVar(
            value=str(lc.get("merge_distance", 20)))
        tk.Label(f, text="   靠多近算靠近：", font=("微软雅黑", 9)
                 ).grid(row=sr+3, column=0, sticky=tk.W)
        md_entry = ttk.Entry(f, textvariable=self._merge_dist_var,
                             width=10, font=("微软雅黑", 10))
        md_entry.grid(row=sr+3, column=1, sticky=tk.W, padx=(5, 5))
        tk.Label(f, text="两个块插入点差多少毫米以内算靠近",
                 fg="#888", font=("微软雅黑", 8)
                 ).grid(row=sr+3, column=2, columnspan=2, sticky=tk.W)
        self._cfg_entries["merge_distance"] = md_entry

        def _toggle_merge_entry(*_):
            state = tk.NORMAL if self._merge_var.get() else tk.DISABLED
            md_entry.config(state=state)
        self._merge_var.trace_add("write", _toggle_merge_entry)
        _toggle_merge_entry()

        # 让第3列存在（不能columnspan跨越不存在列）
        f.grid_columnconfigure(3, weight=0)



    def _get_cfg(self) -> dict:
        def gi(k, default, typ=int):
            try:
                return typ(self._cfg_entries[k].get())
            except (ValueError, KeyError):
                return default
        display = self._sort_mode_var.get() if hasattr(self, '_sort_mode_var') else ""
        sort_mode = self._sort_display_map.get(display, "row_first") if hasattr(self, '_sort_display_map') else "row_first"
        return {
            "prefix": self._cfg_entries["prefix"].get().strip(),
            "start_number": max(1, gi("start_number", 1, int)),
            "pad_width": max(0, gi("pad_width", 3, int)),
            "y_tolerance": max(1.0, gi("y_tolerance", 50.0, float)),
            "auto_continue": False,
            "sort_mode": sort_mode,
            "merge_overlap": self._merge_var.get() if hasattr(self, '_merge_var') else False,
            "merge_distance": max(1.0, gi("merge_distance", 20, float)),
        }

    def _fmt_preview(self, num: int, cfg: dict) -> str:
        s = str(num).zfill(cfg["pad_width"]) if cfg["pad_width"] > 0 else str(num)
        return f"{cfg['prefix']}{s}"

    def _refresh_preview(self) -> None:
        c = self._get_cfg()
        mode_names = {"row_first": "行优先", "selection_order": "选择顺序"}
        sort_tag = mode_names.get(c.get("sort_mode", "row_first"), "")
        start = c["start_number"]
        self._preview_var.set(
            f"[{sort_tag}] {', '.join(self._fmt_preview(i,c) for i in range(start,start+3))}...")

    # ── 保存配置 ──────────────────────────

    def _save_config_from_ui(self) -> bool:
        c = self._get_cfg()
        if c["start_number"] < 1:
            mb.showwarning("提示", "起始编号必须 ≥ 1"); return False
        if c["pad_width"] < 0:
            mb.showwarning("提示", "补零位数不能为负数"); return False
        if c["y_tolerance"] < 1.0:
            mb.showwarning("提示", "Y容差至少为 1.0"); return False
        # 排序模式中文名（日志用）
        mode_names = {"row_first": "行优先", "selection_order": "选择顺序"}
        sort_label = mode_names.get(c.get("sort_mode", "row_first"), "行优先")
        self.number_config = c
        merge_txt = " 合并=开" if c.get("merge_overlap") else ""
        self.log(f"编号配置: 前缀=「{c['prefix']}」 起始={c['start_number']} "
                 f"补零={c['pad_width']}位 容差={c['y_tolerance']}"
                 f" 排序={sort_label}{merge_txt}", "SUCCESS")
        write_log(f"编号配置: {c}")
        self.config_mgr.save_number_config(c)
        return True

    # ══════════════════════════════════════
    #  步骤 4 — 调整顺序 + 执行编号
    # ══════════════════════════════════════

    def _step4_execute(self) -> None:
        f = self._step_frames[self._current_step]

        # ── 预计算排序后列表 ──
        self._reorder_blocks = self._compute_sorted_blocks()
        self._reorder_rows = self._compute_row_ranges(self._reorder_blocks)
        # 重置分组状态（必须先于 _compute_preview，否则预览用了旧分组）
        self._selected_indices = set()
        self._group_map = {}
        self._next_group_id = 0
        # 计算编号预览
        self._compute_preview()
        # 缓存块坐标（避免每次重绘都调 COM）
        self._cache_block_positions()

        # ── 检查重叠并显示提示 ──
        if self.number_config.get("merge_overlap"):
            overlap_groups = self._check_overlaps(self._reorder_blocks)
            if overlap_groups:
                for grp in overlap_groups:
                    names = []
                    for i in grp:
                        tv = (AcadConnect.get_attribute_value(
                            self._reorder_blocks[i], self.type_tag)
                              or "?")
                        names.append(tv)
                    self.log(f"✅ {' 与 '.join(names)} 将合并为同一编号", "WARN")
        else:
            overlap_groups = self._check_overlaps(self._reorder_blocks)
            if overlap_groups:
                group_descs = []
                for grp in overlap_groups:
                    names = []
                    for i in grp:
                        tv = (AcadConnect.get_attribute_value(
                            self._reorder_blocks[i], self.type_tag)
                              or "?")
                        names.append(tv)
                    group_descs.append("+".join(names))
                warn_lbl = tk.Label(
                    f, text=f"⚠️ 检测到以下块组位置靠近：\n"
                            f"{'、'.join(group_descs)}\n"
                            f"建议勾选「合并编号」使每组编同一个号",
                    fg="#d90", font=("微软雅黑", 9, "bold"), justify=tk.LEFT)
                warn_lbl.pack(anchor=tk.W, pady=(0, 5))
                for desc in group_descs:
                    self.log(f"⚠️ 检测到 {desc} 位置靠近，建议勾选合并编号", "WARN")

        # ── 坐标系示意图（含交互调序）──
        minimap_frame = tk.LabelFrame(
            f, text="🗺️ 编号顺序示意图（点击圆圈选中，下方按钮调序）",
            padx=6, pady=4, font=("微软雅黑", 9, "bold"), fg="#25a")
        minimap_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self._minimap_canvas = tk.Canvas(
            minimap_frame, bg="#fefefe",
            highlightthickness=1, highlightbackground="#ddd")
        self._minimap_canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._minimap_canvas.bind("<Button-1>", self._on_minimap_click)
        # 缩放/重绘用防抖 — 持续拖动时不反复画，停止后才画
        self._minimap_canvas.bind("<Configure>",
            lambda e: self._schedule_minimap_redraw())
        self.root.bind("<Configure>",
            lambda e: self._schedule_minimap_redraw()
            if hasattr(self, '_minimap_canvas') and self._current_step == 4
            else None,
            add="+")

        # ── 操作说明 ──
        hint_frame = ttk.Frame(minimap_frame)
        hint_frame.pack(fill=tk.X, pady=(2, 0))
        tk.Label(hint_frame,
            text="操作：单击选中 | Ctrl+单击多选 | 选中2+个点「编为同组」同号+ABCD | 调序控制A/B/C顺序",
            font=("微软雅黑", 8), fg="#999", anchor=tk.W).pack(side=tk.LEFT)

        # ── 调序控制栏 ──
        ctrl_frame = ttk.Frame(minimap_frame)
        ctrl_frame.pack(fill=tk.X, pady=(2, 0))

        self._sel_label = tk.Label(
            ctrl_frame, text="💡 点击圆圈选择",
            font=("微软雅黑", 9), fg="#888")
        self._sel_label.pack(side=tk.LEFT, padx=(2, 10))

        self._move_up_btn = ttk.Button(
            ctrl_frame, text="↑ 上移",
            command=self._move_selected_up, width=7, state=tk.DISABLED)
        self._move_up_btn.pack(side=tk.LEFT, padx=(0, 3))

        self._move_down_btn = ttk.Button(
            ctrl_frame, text="↓ 下移",
            command=self._move_selected_down, width=7, state=tk.DISABLED)
        self._move_down_btn.pack(side=tk.LEFT, padx=(0, 3))

        self._group_btn = ttk.Button(
            ctrl_frame, text="📦编为同组",
            command=self._group_selected, width=10, state=tk.DISABLED)
        self._group_btn.pack(side=tk.LEFT, padx=(0, 3))

        self._ungroup_btn = ttk.Button(
            ctrl_frame, text="↩移出组",
            command=self._ungroup_selected, width=8, state=tk.DISABLED)
        self._ungroup_btn.pack(side=tk.LEFT, padx=(0, 3))

        self._reset_btn = ttk.Button(
            ctrl_frame, text="↺ 恢复排序",
            command=self._reset_reorder, width=10)
        self._reset_btn.pack(side=tk.LEFT)

        self.root.update()
        self._render_minimap()
        self._update_controls()

        # ── 操作汇总 ──
        to_number = sum(self.type_counts.get(t, 0) for t in self.selected_types)
        info_frame = tk.LabelFrame(f, text="📋 操作汇总", padx=12, pady=8,
                                   font=("微软雅黑", 9, "bold"), fg="#2a7")
        info_frame.pack(fill=tk.X)

        mode_names = {"row_first": "行优先", "selection_order": "选择顺序"}
        sm = mode_names.get(self.number_config.get("sort_mode", "row_first"), "")
        merge_txt = " | 合并同位置" if self.number_config.get("merge_overlap") else ""
        lines = [
            f"框选块数:      {len(self.blocks)} 个",
            f"本次编号:      {to_number} 个",
            f"排序模式:      {sm}{merge_txt}",
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

    def _compute_sorted_blocks(self) -> List[Any]:
        """计算排序后的块列表（过滤+排序）"""
        selected_upper = {t.upper() for t in self.selected_types}
        filtered = []
        for blk in self.blocks:
            type_val = AcadConnect.get_attribute_value(blk, self.type_tag)
            if type_val and type_val.strip().upper() in selected_upper:
                filtered.append(blk)
        if not filtered:
            return filtered
        # 用引擎排序
        engine = NumberingEngine.__new__(NumberingEngine)
        engine.acad = self.acad
        return engine._sort_blocks(
            filtered,
            sort_mode=self.number_config.get("sort_mode", "row_first"),
            y_tolerance=self.number_config.get("y_tolerance", 50.0),
            first_handle=self.number_config.get("first_block_handle", None),
        )

    def _check_overlaps(self, blocks) -> List[List[int]]:
        """检查块之间是否有位置靠近的重叠组

        Returns:
            包含 2+ 个块的组列表，空列表表示无重叠
        """
        if not blocks or len(blocks) < 2:
            return []
        md = self.number_config.get("merge_distance", 20.0)
        engine = NumberingEngine.__new__(NumberingEngine)
        engine.acad = self.acad
        groups = engine._group_by_proximity(
            blocks, merge_distance=md, type_tag=self.type_tag)
        return [g for g in groups if len(g) > 1]

    def _compute_row_ranges(self, blocks) -> List[Tuple[int, int]]:
        """计算行范围 [(start, end), ...]"""
        if not blocks or self.number_config.get("sort_mode") == NumberingEngine.SORT_MODE_SELECTION:
            return [(0, len(blocks) - 1)] if blocks else []
        y_tol = self.number_config.get("y_tolerance", 50.0)
        # 用引擎的行分组逻辑
        engine = NumberingEngine.__new__(NumberingEngine)
        rows = engine._group_rows(blocks, y_tol)
        ranges = []
        idx = 0
        for row in rows:
            ranges.append((idx, idx + len(row) - 1))
            idx += len(row)
        return ranges

    # ── 编号预览计算 ──────────────────────────

    def _compute_preview(self) -> None:
        """计算编号预览（合并编号 + 手动分组绑定，紧凑无跳号）"""
        self._reorder_preview = {}
        if not hasattr(self, '_reorder_blocks') or not self._reorder_blocks:
            return
        try:
            # 从第四步配置读取起始参数
            cfg = self.number_config if hasattr(self, 'number_config') and self.number_config else {}
            start_num = cfg.get("start_number", 1)
            if start_num < 1:
                start_num = 1
            prefix = cfg.get("prefix", "")
            pad_width = cfg.get("pad_width", 3)
            n = len(self._reorder_blocks)
            gm = getattr(self, '_group_map', {})
            write_log(f"预览编号: start_num={start_num} prefix=「{prefix}」 pad={pad_width} n={n} group_map={gm}")

            # ── 合并编号 ──
            merge_map: Optional[Dict[int, int]] = None
            if cfg.get("merge_overlap", False):
                engine = NumberingEngine.__new__(NumberingEngine)
                mm = engine._build_overlap_number_map(
                    self._reorder_blocks, merge_distance=cfg.get("merge_distance", 20.0),
                    type_tag=self.type_tag)
                if mm:
                    merge_map = mm

            # ── 手动分组 ──
            mgroups: Dict[int, List[int]] = {}
            for i, gid in gm.items():
                mgroups.setdefault(gid, []).append(i)
            valid_mg = {gid: sorted(m) for gid, m in mgroups.items() if len(m) >= 2}
            in_mg: set = set()
            for m in valid_mg.values():
                in_mg.update(m)

            # ── 合并绑定：合并组接触手动分组 → 整组跟随 ──
            expanded = set(in_mg)
            inherit: Dict[int, str] = {}
            if merge_map:
                attach: Dict[int, str] = {}  # {merge_group_id: suffix}
                for gid, mems in valid_mg.items():
                    for m in mems:
                        if m in merge_map:
                            attach[merge_map[m]] = chr(ord('A') + mems.index(m))
                for i in range(n):
                    if i in merge_map and i not in in_mg and merge_map[i] in attach:
                        expanded.add(i)
                        inherit[i] = attach[merge_map[i]]

            # ── 构建有效分组（每组占 1 个排名位）──
            assigned: set = set()
            eff_groups: List[List[int]] = []  # 每个子列表共享一个排名

            # ① 手动分组（含扩展成员）
            for gid, mems in valid_mg.items():
                group = list(mems)
                for j in range(n):
                    if j in expanded and j not in group:
                        for m in mems:
                            if (merge_map and m in merge_map and j in merge_map
                                and merge_map[m] == merge_map[j]):
                                group.append(j)
                                break
                for m in group:
                    assigned.add(m)
                eff_groups.append(group)

            # ② 未触及手动分组的合并组
            if merge_map:
                for i in range(n):
                    if i not in assigned and i in merge_map:
                        mg = merge_map[i]
                        group = [j for j in range(n) if merge_map.get(j) == mg and j not in assigned]
                        for m in group:
                            assigned.add(m)
                        eff_groups.append(group)

            # ③ 独立块
            for i in range(n):
                if i not in assigned:
                    eff_groups.append([i])

            # ── 分配排名 → 生成编号 ──
            for pos, group in enumerate(eff_groups):
                for m in group:
                    num = start_num + pos
                    num_str = str(num).zfill(pad_width) if pad_width > 0 else str(num)
                    if m in in_mg:
                        for mems in valid_mg.values():
                            if m in mems:
                                suffix = chr(ord('A') + mems.index(m)) if mems.index(m) < 26 else f"_{mems.index(m)}"
                                self._reorder_preview[m] = f"{prefix}{num_str}{suffix}"
                                break
                    elif m in inherit:
                        self._reorder_preview[m] = f"{prefix}{num_str}{inherit[m]}"
                    else:
                        self._reorder_preview[m] = f"{prefix}{num_str}"
        except Exception:
            self._reorder_preview = {}

    # ── 坐标系示意图 ──────────────────────────

    def _cache_block_positions(self) -> None:
        """一次性缓存所有块坐标（避免每次重绘调 COM）"""
        self._minimap_points = []
        for blk in self._reorder_blocks:
            try:
                pt = AcadConnect.get_insertion_point(blk)
                self._minimap_points.append((pt[0], pt[1]))
            except Exception:
                self._minimap_points.append((0, 0))

    def _schedule_minimap_redraw(self) -> None:
        """防抖重绘：窗口持续缩放时不重复绘制，停止 150ms 后才画一次"""
        if hasattr(self, '_minimap_after_id') and self._minimap_after_id:
            self.root.after_cancel(self._minimap_after_id)
        self._minimap_after_id = self.root.after(150, self._render_minimap)

    def _render_minimap(self) -> None:
        """在 Canvas 上绘制块的相对位置坐标系"""
        canvas = self._minimap_canvas
        canvas.delete("all")
        # 确保布局已刷新，拿到正确的画布尺寸
        self.root.update_idletasks()
        blocks = self._reorder_blocks
        if not blocks:
            canvas.create_text(150, 40, text="（无数据）", fill="#999")
            return
        # 使用缓存坐标（不再调 COM）
        points = getattr(self, '_minimap_points', [])
        if not points or len(points) != len(blocks):
            return
        if not points:
            return
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if max_x == min_x:
            max_x = min_x + 1
        if max_y == min_y:
            max_y = min_y + 1
        cw = max(canvas.winfo_width(), 300)
        ch = max(canvas.winfo_height(), 120)
        margin = 30
        dw = cw - margin * 2
        dh = ch - margin * 2

        def tc(px, py):
            cx = margin + (px - min_x) / (max_x - min_x) * dw
            cy = margin + (max_y - py) / (max_y - min_y) * dh  # Y 翻转
            return cx, cy

        row_colors = ["#4a90d9", "#e67e22", "#2ecc71", "#e74c3c", "#9b59b6",
                      "#1abc9c", "#f39c12", "#3498db", "#e91e63", "#00bcd4"]
        rows = self._reorder_rows if hasattr(self, '_reorder_rows') else [(0, len(blocks) - 1)]

        # 画连接线
        for i in range(len(blocks) - 1):
            x1, y1 = tc(*points[i])
            x2, y2 = tc(*points[i + 1])
            cross = not any(rs <= i < i + 1 <= re for rs, re in rows)
            canvas.create_line(x1, y1, x2, y2,
                               fill="#bbb", width=1 if not cross else 0.5,
                               dash=(4, 3) if cross else ())
            dx, dy = x2 - x1, y2 - y1
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > 5:
                nx, ny = dx / dist, dy / dist
                ax1 = x2 - nx * 8 - ny * 4
                ay1 = y2 - ny * 8 + nx * 4
                ax2 = x2 - nx * 8 + ny * 4
                ay2 = y2 - ny * 8 - nx * 4
                canvas.create_polygon(x2, y2, ax1, ay1, ax2, ay2,
                                      fill="#bbb", outline="")

        # 画块
        self._minimap_items = {}
        sel_set = getattr(self, '_selected_indices', set())
        for i, (blk, pt) in enumerate(zip(blocks, points)):
            cx, cy = tc(*pt)
            ri = 0
            for rii, (rs, re) in enumerate(rows):
                if rs <= i <= re:
                    ri = rii
                    break
            color = row_colors[ri % len(row_colors)]
            r = 10
            is_sel = i in sel_set
            outline = "#fa0" if is_sel else "#555"
            ow = 3 if is_sel else 1
            oid = canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                     fill=color, outline=outline, width=ow,
                                     tags=(f"blk_{i}",))
            num_label = self._reorder_preview.get(i, f"#{i + 1}")
            pfx = self.number_config.get("prefix", "")
            short = num_label[len(pfx):] if num_label.startswith(pfx) else num_label
            canvas.create_text(cx, cy, text=short, fill="white",
                               font=("Arial", 9, "bold"),
                               tags=(f"blk_{i}",))
            try:
                tv = AcadConnect.get_attribute_value(blk, self.type_tag) or "?"
            except Exception:
                tv = "?"
            canvas.create_text(cx, cy + r + 10, text=tv, fill="#555",
                               font=("Arial", 8),
                               tags=(f"blk_{i}",))
            # 选中时在外围加一个虚线光环
            gid_glow = None
            if is_sel:
                gid_glow = canvas.create_oval(
                    cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
                    outline="#fa0", width=2, dash=(3, 2))
            self._minimap_items[i] = {"oval": oid, "glow": gid_glow,
                                       "cx": cx, "cy": cy, "r": r}

        # 画组框（同组块用虚线框圈在一起）
        gm = getattr(self, '_group_map', {})
        if gm:
            groups: Dict[int, List[int]] = {}
            for gi, gid in gm.items():
                groups.setdefault(gid, []).append(gi)
            group_colors = ["#4a9", "#e80", "#d4a", "#3ac", "#e5a", "#7bc", "#c83"]
            for gi, (gid, members) in enumerate(groups.items()):
                if len(members) < 2:
                    continue
                pts = [tc(*points[m]) for m in members]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                pad_b = 8
                x0 = min(xs) - r - pad_b
                y0 = min(ys) - r - pad_b - 8
                x1 = max(xs) + r + pad_b
                y1 = max(ys) + r + pad_b + 8
                gc = group_colors[gi % len(group_colors)]
                canvas.create_rectangle(x0, y0, x1, y1,
                    outline=gc, width=1.5, dash=(6, 3), fill="")
                # 组标签
                first_member = min(members)
                base_label = self._reorder_preview.get(first_member, "")
                # 去掉后缀取基础号
                if base_label and base_label[-1] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    base_label = base_label[:-1]
                canvas.create_text(x0 + 4, y0 + 4, text=f"组{gid} {base_label}*",
                    fill=gc, font=("Arial", 7, "bold"), anchor=tk.NW)

        # 坐标轴标注
        canvas.create_text(margin, ch - 4, text=f"← X({min_x:.0f}~{max_x:.0f})",
                           fill="#aaa", font=("Arial", 7), anchor=tk.SW)
        canvas.create_text(margin, margin - 8, text=f"Y({max_y:.0f})↑",
                           fill="#aaa", font=("Arial", 7), anchor=tk.SW)

    def _refresh_minimap_selection(self) -> None:
        """轻量更新选中高亮（只改边框，不删重建，不用 bbox）"""
        canvas = self._minimap_canvas
        items = getattr(self, '_minimap_items', {})
        sel_set = getattr(self, '_selected_indices', set())
        for i, ids in items.items():
            is_sel = i in sel_set
            if not ids.get("oval"):
                continue
            try:
                # 只改圆框的边框颜色和粗细（这是最轻量的操作）
                canvas.itemconfig(ids["oval"],
                    outline="#fa0" if is_sel else "#555",
                    width=3 if is_sel else 1)
                # 光晕用缓存坐标直接创建/删除
                if is_sel and not ids.get("glow"):
                    cx, cy, r = ids["cx"], ids["cy"], ids["r"]
                    ids["glow"] = canvas.create_oval(
                        cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
                        outline="#fa0", width=2, dash=(3, 2))
                elif not is_sel and ids.get("glow"):
                    canvas.delete(ids["glow"])
                    ids["glow"] = None
            except Exception:
                pass

    def _render_reorder_panel(self) -> None:
        """渲染调序面板（清空重绘）"""
        for w in self._reorder_inner.winfo_children():
            w.destroy()

        blocks = self._reorder_blocks
        if not blocks:
            tk.Label(self._reorder_inner, text="（无匹配的块）",
                     fg="#999", bg="#fafafa").pack()
            return

        rows = self._reorder_rows
        row_idx = 0
        for r_start, r_end in rows:
            # 判断本行排列方向：首尾块 X 坐标对比
            if r_end > r_start and r_start < len(blocks) and r_end < len(blocks):
                _, x_start, _ = AcadConnect.get_insertion_point(blocks[r_start])
                _, x_end, _ = AcadConnect.get_insertion_point(blocks[r_end])
                if x_start <= x_end:
                    dir_text = "从左到右 →"
                else:
                    dir_text = "从右到左 ←"
            else:
                dir_text = ""

            # 行标题（显示方向）
            if len(rows) > 1:
                row_header = tk.Label(
                    self._reorder_inner,
                    text=f"── 第{row_idx+1}行 {dir_text} ──",
                    fg="#888", bg="#fafafa", font=("微软雅黑", 8))
                row_header.pack(fill=tk.X, pady=(4, 0))

            for i in range(r_start, r_end + 1):
                blk = blocks[i]
                try:
                    tv = AcadConnect.get_attribute_value(blk, self.type_tag) or "?"
                except Exception:
                    tv = "?"
                # 编号预览
                preview_num = self._reorder_preview.get(i, "?")
                # 方向指示
                dir_mark = ""
                if i < r_end:
                    try:
                        x, _, _ = AcadConnect.get_insertion_point(blk)
                        nx, _, _ = AcadConnect.get_insertion_point(blocks[i + 1])
                        if nx >= x:
                            dir_mark = "→"
                        else:
                            dir_mark = "←"
                    except Exception:
                        dir_mark = ""

                item_f = tk.Frame(self._reorder_inner, bg="#fafafa")
                item_f.pack(fill=tk.X, padx=(12, 4), pady=1)
                # ↑
                up_btn = tk.Button(item_f, text="↑", width=2,
                                   font=("微软雅黑", 8),
                                   command=lambda idx=i: self._reorder_up(idx))
                if i == r_start:
                    up_btn.config(state=tk.DISABLED, fg="#ccc")
                up_btn.pack(side=tk.LEFT)
                # ↓
                down_btn = tk.Button(item_f, text="↓", width=2,
                                     font=("微软雅黑", 8),
                                     command=lambda idx=i: self._reorder_down(idx))
                if i == r_end:
                    down_btn.config(state=tk.DISABLED, fg="#ccc")
                down_btn.pack(side=tk.LEFT)
                # 块信息：序号 + 类型 → 编号预览
                tk.Label(item_f, text=f"  #{i+1}  {tv}  →  {preview_num}",
                         font=("微软雅黑", 9), fg="#333",
                         bg="#fafafa", anchor=tk.W).pack(
                             side=tk.LEFT, fill=tk.X, expand=True)
                # 方向箭头
                if dir_mark:
                    tk.Label(item_f, text=dir_mark,
                             font=("微软雅黑", 11, "bold"), fg="#25a",
                             bg="#fafafa").pack(side=tk.RIGHT, padx=(0, 5))

            row_idx += 1

        # 更新 canvas 滚动区域
        self._reorder_inner.update_idletasks()
        self._reorder_canvas.configure(
            scrollregion=self._reorder_canvas.bbox("all"))

    def _reorder_up(self, idx: int) -> None:
        """将索引 idx 的块上移一位（同行内）"""
        for r_start, r_end in self._reorder_rows:
            if r_start <= idx <= r_end:
                if idx > r_start:
                    self._reorder_blocks[idx], self._reorder_blocks[idx - 1] = \
                        self._reorder_blocks[idx - 1], self._reorder_blocks[idx]
                    self._minimap_points[idx], self._minimap_points[idx - 1] = \
                        self._minimap_points[idx - 1], self._minimap_points[idx]
                break
        self._compute_preview()

    def _reorder_down(self, idx: int) -> None:
        """将索引 idx 的块下移一位（同行内）"""
        for r_start, r_end in self._reorder_rows:
            if r_start <= idx <= r_end:
                if idx < r_end:
                    self._reorder_blocks[idx], self._reorder_blocks[idx + 1] = \
                        self._reorder_blocks[idx + 1], self._reorder_blocks[idx]
                    self._minimap_points[idx], self._minimap_points[idx + 1] = \
                        self._minimap_points[idx + 1], self._minimap_points[idx]
                break
        self._compute_preview()

    # ── 示意图交互 ──────────────────────────

    def _on_minimap_click(self, event):
        """点击示意图选中/切换选中
        Ctrl+单击 = 切换（追加/移除），普通单击 = 单选
        """
        canvas = self._minimap_canvas
        ctrl = (event.state & 0x4) != 0  # Ctrl 键按下
        item = canvas.find_closest(event.x, event.y)
        idx = -1
        if item:
            tags = canvas.gettags(item)
            for tag in tags:
                if tag.startswith("blk_"):
                    idx = int(tag[4:])
                    break
        if idx >= 0:
            if ctrl:
                # Ctrl+click: 切换选中
                if idx in self._selected_indices:
                    self._selected_indices.discard(idx)
                else:
                    self._selected_indices.add(idx)
            else:
                # 普通单击: 单选
                self._selected_indices = {idx}
        else:
            # 点空白: 清空选中
            self._selected_indices.clear()
        self._refresh_minimap_selection()
        self._update_controls()

    def _select_block(self, idx: int) -> None:
        """选中/取消选中某块（保留给外部调用）"""
        self._selected_indices = {idx} if idx >= 0 else set()
        self._render_minimap()
        self._update_controls()

    def _update_controls(self) -> None:
        """更新控制栏状态"""
        sel = self._selected_indices
        if sel:
            idx = next(iter(sel))
            n = len(sel)
            blk = self._reorder_blocks[idx]
            try:
                tv = AcadConnect.get_attribute_value(blk, self.type_tag) or "?"
            except Exception:
                tv = "?"
            preview = self._reorder_preview.get(idx, "?")
            if n == 1:
                txt = f"🎯 已选: #{idx+1}  {tv}  →  {preview}"
            else:
                others = ", ".join(str(i+1) for i in sorted(sel)[:3])
                txt = f"🎯 已选 {n} 个: #{others}..."
            self._sel_label.config(text=txt, fg="#25a")
            enabled = tk.NORMAL
            # 编组按钮：选中 ≥2 个且不在同一组时可编组
            grp_ids = {self._group_map.get(i, -1) for i in sel}
            can_group = n >= 2 and (-1 in grp_ids or len(grp_ids) > 1)
            self._group_btn.config(state=tk.NORMAL if can_group else tk.DISABLED)
            # 移出组：至少有一个在组内
            in_group = any(i in self._group_map for i in sel)
            self._ungroup_btn.config(state=tk.NORMAL if in_group else tk.DISABLED)
        else:
            self._sel_label.config(text="💡 点击 / Ctrl+点击 圆圈选择位号", fg="#888")
            enabled = tk.DISABLED
            self._group_btn.config(state=tk.DISABLED)
            self._ungroup_btn.config(state=tk.DISABLED)
        self._move_up_btn.config(state=enabled)
        self._move_down_btn.config(state=enabled)

    def _move_selected_up(self) -> None:
        """将选中的块上移（取第一个选中）"""
        if not self._selected_indices:
            return
        idx = min(self._selected_indices)
        old_idx = idx
        self._reorder_up(idx)
        # 更新选中索引
        self._selected_indices = {max(0, i-1) if i == old_idx else i
                                   for i in self._selected_indices}
        self._render_minimap()
        self._update_controls()

    def _move_selected_down(self) -> None:
        """将选中的块下移（取第一个选中）"""
        if not self._selected_indices:
            return
        idx = min(self._selected_indices)
        old_idx = idx
        self._reorder_down(idx)
        self._selected_indices = {min(len(self._reorder_blocks)-1, i+1) if i == old_idx else i
                                   for i in self._selected_indices}
        self._render_minimap()
        self._update_controls()

    def _group_selected(self) -> None:
        """将选中的块编为同组（同号 + A/B/C 后缀）"""
        if len(self._selected_indices) < 2:
            return
        gid = self._next_group_id
        self._next_group_id += 1
        for i in self._selected_indices:
            self._group_map[i] = gid
        self._compute_preview()
        self._render_minimap()
        self._update_controls()
        self.log(f"📦 编组 {gid}: {len(self._selected_indices)} 个块将编为同号", "SUCCESS")

    def _ungroup_selected(self) -> None:
        """将选中的块从所在组移出"""
        for i in list(self._selected_indices):
            self._group_map.pop(i, None)
        self._compute_preview()
        self._render_minimap()
        self._update_controls()
        self.log("↩ 已从组中移出", "INFO")

    def _reset_reorder(self) -> None:
        """恢复排序到初始状态"""
        self._reorder_blocks = self._compute_sorted_blocks()
        self._reorder_rows = self._compute_row_ranges(self._reorder_blocks)
        self._cache_block_positions()
        self._compute_preview()
        self._selected_indices.clear()
        self._group_map.clear()
        self._next_group_id = 0
        self._render_minimap()
        self._update_controls()

    def _execute_numbering(self) -> None:
        if not all([self.acad, self.blocks, self.type_tag, self.number_tag,
                    self.selected_types, self.number_config]):
            mb.showwarning("提示", "请先完成前面的所有步骤。")
            return

        self._set_busy(True, "编号中...")
        self.log("=" * 40)
        self.log("开始执行编号...")

        try:
            # 使用调整后的顺序（如果用户没有调序，_reorder_blocks 就是排序后结果）
            use_blocks = self._reorder_blocks if hasattr(self, '_reorder_blocks') else None
            if use_blocks:
                exec_config = dict(self.number_config)
                exec_config["_skip_sort"] = True  # 引擎跳过排序
            else:
                use_blocks = self.blocks
                exec_config = self.number_config

            # 构建编号覆盖映射传给引擎（所有块都用预览编号，保证紧凑无跳号）
            tag_override = {}
            for i in range(len(use_blocks)):
                if i in self._reorder_preview:
                    tag_override[i] = self._reorder_preview[i]
            exec_config["_tag_override"] = tag_override

            engine = NumberingEngine(self.acad)
            self.log("正在写入 AutoCAD...")
            self.root.update()
            results = engine.number_instruments(
                block_refs=use_blocks, type_tag=self.type_tag,
                number_tag=self.number_tag, selected_types=self.selected_types,
                config=exec_config, progress_cb=self.root.update)

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
