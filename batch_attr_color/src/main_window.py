#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主窗口 — 单窗口向导

所有操作集成在一个窗口内完成，分为 4 个步骤页面：
① 连接 AutoCAD 并框选块
② 选择要修改颜色的属性标签
③ 选择颜色
④ 执行批量修改

日志记录到文件 plugin.log，追加不覆盖。
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox as mb
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.acad_com import AcadConnect, AcadConnectError, ACI_COLORS, QUICK_COLORS
from src.config import ConfigManager

logger = logging.getLogger(__name__)

LOG_FILE = "plugin.log"

VERSION = "1.0.0"


def write_log(message: str, level: str = "INFO") -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {level}: {message}\n")
    except Exception:
        pass


# ── 16 进制颜色 → Tk 可用的字符串 ─────────
def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


# ── 预设颜色板 ──────────────────────────
PRESET_COLORS = [
    # (显示名, ACI 索引, 红, 绿, 蓝, 说明)
    ("🔴 红",       1,   255, 0,   0,   "ACI 1"),
    ("🟠 橙",       11,  255, 128, 0,   "ACI 11"),
    ("🟡 黄",       2,   255, 255, 0,   "ACI 2"),
    ("🟢 绿",       3,   0,   255, 0,   "ACI 3"),
    ("🔵 蓝",       5,   0,   0,   255, "ACI 5"),
    ("🟣 紫",       50,  128, 0,   255, "ACI 50"),
    ("⚪ 白",       7,   255, 255, 255, "ACI 7"),
    ("⬜ 浅灰",     9,   192, 192, 192, "ACI 9"),
    ("⬛ 深灰",     8,   128, 128, 128, "ACI 8"),
    ("⚫ 黑",       250, 0,   0,   0,   "ACI 250"),
    ("🩷 粉红",     40,  255, 128, 128, "ACI 40"),
    ("🩵 天蓝",     4,   0,   255, 255, "ACI 4"),
    ("💚 青绿",     14,  0,   255, 128, "ACI 14"),
    ("🧡 红橙",     10,  255, 80,  0,   "ACI 10"),
    ("🤎 褐",       20,  128, 64,  0,   "ACI 20"),
    ("💙 深蓝",     250, 0,   0,   128, "ACI 250"),
    ("💚 深绿",     230, 0,   128, 0,   "ACI 230"),
    ("🖤 深红",     200, 200, 0,   0,   "ACI 200"),
    ("📋 ByLayer",  256, None,None,None,"随层"),
    ("📦 ByBlock",  0,   None,None,None,"随块"),
]


class MainWindow:
    """主窗口 — 单窗口向导（批量修改属性文字颜色）"""

    def __init__(self) -> None:
        write_log("=" * 60)
        write_log("颜色修改插件启动")
        try:
            self.root = tk.Tk()
            self.root.title(f"批量修改块属性文字颜色 v{VERSION}")
            self.root.geometry("680x580")
            self.root.minsize(600, 520)
            self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

            # ── 状态变量 ──
            self.acad: Optional[AcadConnect] = None
            self.config_mgr = ConfigManager()
            self.memory = self.config_mgr.load()

            self.blocks: Optional[List[Any]] = None
            self.all_tags: List[str] = []
            self.tags_with_samples: Dict[str, List[str]] = {}

            # 用户选择
            self.selected_tag: str = ""
            self.selected_color_index: int = 3     # 默认绿
            self.selected_rgb: Tuple[int, int, int] = (0, 255, 0)
            self.color_mode: str = "aci"           # "aci" | "true_color" | "bylayer" | "byblock"
            self.non_empty_only: bool = True

            # 统计
            self._modified_count: int = 0
            self._skipped_count: int = 0

            # 步骤
            self._current_step = 0
            self._total_steps = 4
            self._exec_done = False
            self._busy = False
            self._step_frames: List[Optional[ttk.Frame]] = [None] * self._total_steps

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
    #  步骤管理
    # ══════════════════════════════════════

    def _show_step(self, step: int) -> None:
        """显示指定步骤（缓存 frame，不重复创建）"""
        self._current_step = step

        steps = [
            (self._step0_connect, "① 连接 AutoCAD 并框选块"),
            (self._step1_select_tag, "② 选择要修改颜色的属性标签"),
            (self._step2_pick_color, "③ 选择颜色"),
            (self._step3_execute, "④ 执行批量修改"),
        ]

        func, title = steps[step]
        self._step_label.config(text=title)

        # 首次访问则创建 frame
        if self._step_frames[step] is None:
            f = ttk.Frame(self._step_content)
            f.grid(row=0, column=0, sticky="nsew")
            self._step_frames[step] = f
            func()

        # 回到步骤0时恢复按钮状态
        if step == 0:
            self._refresh_step0_buttons()

        # 把目标 frame 提到最前
        self._step_frames[step].tkraise()
        self._update_buttons()

    def _update_buttons(self) -> None:
        # 上一步
        can_back = self._current_step > 0
        self._back_btn.configure(state=tk.NORMAL if can_back else tk.DISABLED)

        # 下一步/完成
        if self._exec_done and self._current_step >= self._total_steps - 1:
            self._next_btn.config(text="✅ 完成", command=self.root.destroy,
                                  state=tk.NORMAL)
        elif self._current_step >= self._total_steps - 1:
            self._next_btn.config(text="🚀 开始修改", command=self._execute_color_change)
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
            if not self._save_tag_from_ui():
                return
        elif self._current_step == 2:
            if not self._save_color_from_ui():
                return
        self._show_step(self._current_step + 1)

    def _go_back(self) -> None:
        if self._current_step > 0:
            if self._current_step >= self._total_steps - 1 and self._exec_done:
                self._exec_done = False
                self.log("已重置执行状态，可以调整参数后重新修改", "INFO")
            self._show_step(self._current_step - 1)

    # ══════════════════════════════════════
    #  步骤 0：连接 + 选块
    # ══════════════════════════════════════

    def _step0_connect(self) -> None:
        f = self._step_frames[self._current_step]

        ttk.Label(f, text="在 AutoCAD 中框选或选中带属性的块，然后点击下方按钮读取。\n"
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
        self.all_tags = []
        self.tags_with_samples = {}
        self.selected_tag = ""
        self.selected_color_index = 3
        self.selected_rgb = (0, 255, 0)
        self.color_mode = "aci"
        self._exec_done = False
        # 销毁旧 frame
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
            all_entities = self.acad.get_active_selection()
            self.blocks = []
            for ent in all_entities:
                try:
                    if ent.EntityName == "AcDbBlockReference":
                        atts = ent.GetAttributes()
                        if len(atts) > 0:
                            self.blocks.append(ent)
                except Exception:
                    pass
        except Exception as e:
            self.log(f"读取失败: {e}", "ERROR")
            self._sel_result.config(text=f"❌ 读取失败: {e}", fg="red")
            write_log(f"读取失败: {e}\n{traceback.format_exc()}", "ERROR")
            self._set_busy(False, success=False)
            return

        if not self.blocks:
            self.log("当前选中中没有带属性的块", "WARN")
            self._sel_result.config(text="⚠️ 无选中块，请先在 CAD 中选中再点击", fg="#d90")
            mb.showwarning("提示", "当前选中中没有带属性的块。\n请在 AutoCAD 中先选中块，再重试。")
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
            self.blocks = self.acad.select_blocks_with_attributes(
                prompt_text="\n请框选要修改颜色的块（右键结束选择）..."
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

        self._reselect_clear()
        self.log(f"选中 {len(self.blocks)} 个带属性块", "SUCCESS")
        write_log(f"框选成功: {len(self.blocks)} 个带属性块")
        self._sel_result.config(text=f"✅ 已选中 {len(self.blocks)} 个带属性块", fg="green")
        self._select_btn.config(state=tk.DISABLED)
        self._set_busy(False)

    # ══════════════════════════════════════
    #  步骤 1：选择属性标签
    # ══════════════════════════════════════

    def _step1_select_tag(self) -> None:
        f = self._step_frames[self._current_step]

        ttk.Label(f, text="选择要修改文字颜色的属性标签。\n"
                   "插件将把选中的属性标签的文字颜色批量改为指定颜色。",
                   font=("微软雅黑", 9), foreground="#555",
                   ).pack(anchor=tk.W, pady=(0, 10))

        # 仅首次进入时分析标签
        if not self.all_tags:
            self._set_busy(True, "正在分析...")
            self.log("正在分析属性标签...")
            self.root.update()
            try:
                self.all_tags = self.acad.get_all_tags(self.blocks)
                self.tags_with_samples = {}
                for tag in self.all_tags:
                    self.tags_with_samples[tag] = self.acad.get_tag_sample_values(
                        self.blocks, tag, 5)
                self.log(f"发现 {len(self.all_tags)} 个属性标签", "SUCCESS")
                self._set_busy(False)
            except Exception as e:
                self.log(f"分析标签失败: {e}", "ERROR")
                write_log(f"分析标签失败: {e}\n{traceback.format_exc()}", "ERROR")
                self._set_busy(False, success=False)
                mb.showerror("分析错误", f"读取属性标签失败:\n{e}")

        # 标签选择
        tk.Label(f, text="选择要修改颜色的属性标签：", font=("微软雅黑", 10, "bold")
                 ).pack(anchor=tk.W)
        self._tag_var = tk.StringVar()
        self._tag_combo = ttk.Combobox(f, textvariable=self._tag_var,
                                       values=self.all_tags, state="readonly",
                                       width=60, font=("微软雅黑", 9))
        self._tag_combo.pack(fill=tk.X, pady=(0, 2))
        self._tag_preview = tk.Label(f, text="", fg="#888", font=("微软雅黑", 9))
        self._tag_preview.pack(anchor=tk.W, pady=(0, 8))

        # 记忆值
        lt = self.memory.get("last_tag", "")
        if lt in self.all_tags:
            self._tag_var.set(lt)
        elif self.all_tags:
            self._tag_var.set(self.all_tags[0])

        self._tag_combo.bind("<<ComboboxSelected>>",
            lambda e: self._update_tag_preview(self._tag_var.get()))

        # 选项
        opt_frame = ttk.Frame(f)
        opt_frame.pack(fill=tk.X, pady=(8, 0))

        self._non_empty_var = tk.BooleanVar(
            value=self.memory.get("color_non_empty_only", True)
        )
        ttk.Checkbutton(opt_frame,
                        text="仅修改非空值的属性（跳过空值属性）",
                        variable=self._non_empty_var,
                        font=("微软雅黑", 9)).pack(anchor=tk.W)
        ttk.Label(opt_frame,
                  text="勾选后，只有该标签有文字内容的属性才会被改色",
                  foreground="#999", font=("微软雅黑", 8)).pack(anchor=tk.W, padx=(20, 0))

        # 提示
        self._tag_hint = tk.Label(f, text="", font=("微软雅黑", 9))
        self._tag_hint.pack(anchor=tk.W, pady=(5, 0))

        self._update_tag_preview(self._tag_var.get())

    def _update_tag_preview(self, tag: str) -> None:
        samples = self.tags_with_samples.get(tag, [])
        self._tag_preview.config(
            text=f"示例值: {', '.join(samples[:5])}" if samples else "（暂无示例值）")

        # 统计
        if self.blocks and tag:
            total = len(self.blocks)
            non_empty = 0
            for blk in self.blocks:
                val = self.acad.get_attribute_value(blk, tag)
                if val and val.strip():
                    non_empty += 1
            self._tag_hint.config(
                text=f"📊 {total} 个块中，该标签非空值的有 {non_empty} 个" if non_empty < total
                else f"📊 {total} 个块全部非空",
                fg="#2a7")

    def _save_tag_from_ui(self) -> bool:
        tag = self._tag_var.get().strip()
        if not tag:
            mb.showwarning("提示", "请选择一个属性标签。")
            return False
        self.selected_tag = tag
        self.non_empty_only = self._non_empty_var.get()
        self.log(f"已选择标签: 【{tag}】", "SUCCESS")
        write_log(f"标签选择: {tag}, 仅非空={self.non_empty_only}")
        self.config_mgr.save_tag(tag)
        self.config_mgr.save_options(self.non_empty_only)
        return True

    # ══════════════════════════════════════
    #  步骤 2：选择颜色
    # ══════════════════════════════════════

    def _step2_pick_color(self) -> None:
        f = self._step_frames[self._current_step]

        ttk.Label(f, text=f"选择要应用到「{self.selected_tag}」标签文字的颜色。\n"
                   "可以从预设颜色中选择，或自定义 RGB 颜色。",
                   font=("微软雅黑", 9), foreground="#555",
                   ).pack(anchor=tk.W, pady=(0, 10))

        # ── 左侧：预设颜色 ──
        main_area = ttk.Frame(f)
        main_area.pack(fill=tk.BOTH, expand=True)
        main_area.grid_columnconfigure(0, weight=1)
        main_area.grid_columnconfigure(1, weight=0)

        # 预设颜色区域
        preset_frame = ttk.LabelFrame(main_area, text="🎨 预设颜色", padding=6)
        preset_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # 颜色按钮网格
        self._color_buttons: List[ttk.Button] = []
        self._color_var = tk.IntVar(value=self.memory.get("last_color_index", 3))
        self._color_mode_var = tk.StringVar(value=self.memory.get("last_color_mode", "aci"))

        cols = 5
        for i, (name, aci_idx, r, g, b, desc) in enumerate(PRESET_COLORS):
            row = i // cols
            col = i % cols

            btn_frame = ttk.Frame(preset_frame)
            btn_frame.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")

            if r is not None:
                # 颜色按钮（含色块）
                hex_color = rgb_to_hex(r, g, b)
                btn = tk.Button(btn_frame, text="  " * 6,
                                bg=hex_color, relief=tk.RAISED, borderwidth=2,
                                command=lambda idx=aci_idx, mode="aci":
                                    self._select_preset(idx, mode))
                btn.pack()
            else:
                # ByLayer / ByBlock
                if aci_idx == 256:
                    btn = tk.Button(btn_frame, text="ByLayer",
                                    font=("微软雅黑", 7), width=8,
                                    relief=tk.RAISED, borderwidth=2,
                                    command=lambda: self._select_bylayer())
                    btn.pack()
                else:
                    btn = tk.Button(btn_frame, text="ByBlock",
                                    font=("微软雅黑", 7), width=8,
                                    relief=tk.RAISED, borderwidth=2,
                                    command=lambda: self._select_byblock())
                    btn.pack()

            # 颜色名称标签
            ttk.Label(btn_frame, text=name, font=("微软雅黑", 8),
                      anchor=tk.CENTER).pack()

        # ── 右侧：自定义 RGB ──
        custom_frame = ttk.LabelFrame(main_area, text="✏️ 自定义 RGB 颜色", padding=8)
        custom_frame.grid(row=0, column=1, sticky="ns", padx=(8, 0))

        # 色块预览
        last_rgb = self.memory.get("last_rgb", [255, 0, 0])
        self._color_preview = tk.Label(custom_frame, text="  " * 10,
                                       bg=rgb_to_hex(*last_rgb),
                                       relief=tk.SUNKEN, borderwidth=2)
        self._color_preview.pack(pady=(0, 10), fill=tk.X)

        # RGB 输入
        rgb_frame = ttk.Frame(custom_frame)
        rgb_frame.pack(fill=tk.X)
        labels = ["R", "G", "B"]
        self._rgb_vars: Dict[str, tk.StringVar] = {}
        self._rgb_entries: Dict[str, ttk.Entry] = {}

        for i, (lbl, default) in enumerate(zip(labels, last_rgb)):
            row_f = ttk.Frame(rgb_frame)
            row_f.pack(fill=tk.X, pady=2)
            ttk.Label(row_f, text=f"{lbl}:", font=("微软雅黑", 9), width=3
                      ).pack(side=tk.LEFT)

            var = tk.StringVar(value=str(default))
            self._rgb_vars[lbl.lower()] = var
            entry = ttk.Entry(row_f, textvariable=var, width=6, font=("微软雅黑", 9))
            entry.pack(side=tk.LEFT, padx=(3, 0))
            self._rgb_entries[lbl.lower()] = entry

            # 数值变化时更新预览
            var.trace_add("write", lambda *_: self._update_rgb_preview())

        # 应用自定义颜色按钮
        ttk.Button(custom_frame, text="✅ 应用自定义颜色",
                   command=self._apply_custom_rgb,
                   width=16).pack(pady=(10, 0))

        ttk.Label(custom_frame,
                  text="输入 0-255 之间的数值",
                  foreground="#999", font=("微软雅黑", 8),
                  ).pack(pady=(5, 0))

        # 状态提示
        self._color_status = tk.Label(f, text="", font=("微软雅黑", 9))
        self._color_status.pack(anchor=tk.W, pady=(5, 0))

        # 加载记忆的颜色状态
        if self._color_mode_var.get() == "aci":
            self._select_preset(self._color_var.get(), "aci")

    def _select_preset(self, aci_idx: int, mode: str) -> None:
        """选择预设颜色"""
        self._color_var.set(aci_idx)
        self._color_mode_var.set(mode)
        self.selected_color_index = aci_idx
        self.color_mode = mode

        # 获取 RGB 显示
        rgb = self.acad.get_rgb_from_color_index(aci_idx) if self.acad else None
        if not rgb:
            rgb = ACI_COLORS.get(aci_idx, ("", None))[1]
        if rgb:
            self.selected_rgb = rgb
            self._update_color_preview_display(rgb)

        # 更新状态
        color_name = ACI_COLORS.get(aci_idx, ("",))[0]
        self._color_status.config(
            text=f"✅ 已选择: ACI {aci_idx} ({color_name})",
            fg="#2a7")
        self.log(f"已选择预设颜色: ACI {aci_idx} ({color_name})", "INFO")

    def _select_bylayer(self) -> None:
        """选择 ByLayer"""
        self._color_var.set(256)
        self._color_mode_var.set("bylayer")
        self.selected_color_index = 256
        self.color_mode = "bylayer"
        self._color_preview.config(text="  " * 10, bg="#f0f0f0")
        self._color_status.config(text="✅ 已选择: ByLayer（随层）", fg="#2a7")
        self.log("已选择: ByLayer（随层）", "INFO")

    def _select_byblock(self) -> None:
        """选择 ByBlock"""
        self._color_var.set(0)
        self._color_mode_var.set("byblock")
        self.selected_color_index = 0
        self.color_mode = "byblock"
        self._color_preview.config(text="  " * 10, bg="#f0f0f0")
        self._color_status.config(text="✅ 已选择: ByBlock（随块）", fg="#2a7")
        self.log("已选择: ByBlock（随块）", "INFO")

    def _update_rgb_preview(self) -> None:
        """实时更新 RGB 预览色块"""
        try:
            r = min(255, max(0, int(self._rgb_vars["r"].get() or 0)))
            g = min(255, max(0, int(self._rgb_vars["g"].get() or 0)))
            b = min(255, max(0, int(self._rgb_vars["b"].get() or 0)))
            self._color_preview.config(bg=rgb_to_hex(r, g, b))
        except ValueError:
            pass

    def _apply_custom_rgb(self) -> None:
        """应用自定义 RGB 颜色"""
        try:
            r = min(255, max(0, int(self._rgb_vars["r"].get() or 0)))
            g = min(255, max(0, int(self._rgb_vars["g"].get() or 0)))
            b = min(255, max(0, int(self._rgb_vars["b"].get() or 0)))
        except ValueError:
            mb.showwarning("提示", "RGB 值必须是 0-255 之间的整数。")
            return

        self.selected_rgb = (r, g, b)
        self.selected_color_index = -1  # 自定义
        self.color_mode = "true_color"

        self._color_preview.config(bg=rgb_to_hex(r, g, b))
        self._color_status.config(
            text=f"✅ 已选择自定义颜色: RGB({r}, {g}, {b})",
            fg="#2a7")
        self.log(f"已选择自定义 RGB 颜色: ({r}, {g}, {b})", "INFO")

    def _update_color_preview_display(self, rgb: Tuple[int, int, int]) -> None:
        """更新预览色块显示"""
        r, g, b = rgb
        self._color_preview.config(bg=rgb_to_hex(r, g, b))
        self._rgb_vars["r"].set(str(r))
        self._rgb_vars["g"].set(str(g))
        self._rgb_vars["b"].set(str(b))

    def _save_color_from_ui(self) -> bool:
        """从 UI 保存颜色选择"""
        # 如果用户没主动点过预设或自定义，使用默认值
        if not self.color_mode:
            self.color_mode = "aci"
            self.selected_color_index = self._color_var.get()
            rgb = ACI_COLORS.get(self.selected_color_index, ("", None))[1]
            if rgb:
                self.selected_rgb = rgb

        self.log(f"颜色确认: 模式={self.color_mode}", "SUCCESS")

        # 保存配置
        if self.color_mode == "true_color":
            r, g, b = self.selected_rgb
            self.config_mgr.save_color("true_color", 0, [r, g, b])
        elif self.color_mode == "bylayer":
            self.config_mgr.save_color("bylayer", 256, [255, 255, 255])
        elif self.color_mode == "byblock":
            self.config_mgr.save_color("byblock", 0, [255, 255, 255])
        else:
            self.config_mgr.save_color("aci", self.selected_color_index,
                                       list(self.selected_rgb))

        return True

    # ══════════════════════════════════════
    #  步骤 3：执行
    # ══════════════════════════════════════

    def _step3_execute(self) -> None:
        f = self._step_frames[self._current_step]

        ttk.Label(f, text="确认以下信息，点击「🚀 开始修改」执行批量颜色修改。",
                   font=("微软雅黑", 9), foreground="#555",
                   ).pack(anchor=tk.W, pady=(0, 12))

        # 信息摘要
        info_frame = ttk.LabelFrame(f, text="📋 修改预览", padding=12)
        info_frame.pack(fill=tk.X, pady=(0, 12))

        # 颜色预览色块
        color_display_frame = ttk.Frame(info_frame)
        color_display_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(color_display_frame, text="选择颜色：",
                  font=("微软雅黑", 10, "bold")).pack(side=tk.LEFT)

        if self.color_mode == "true_color":
            hex_c = rgb_to_hex(*self.selected_rgb)
            color_swatch = tk.Label(color_display_frame, text="  " * 8,
                                    bg=hex_c, relief=tk.SUNKEN, borderwidth=2)
            color_swatch.pack(side=tk.LEFT, padx=(8, 5))
            ttk.Label(color_display_frame,
                      text=f"RGB({self.selected_rgb[0]}, {self.selected_rgb[1]}, {self.selected_rgb[2]})",
                      font=("微软雅黑", 9)).pack(side=tk.LEFT)
        elif self.color_mode == "bylayer":
            ttk.Label(color_display_frame, text="ByLayer（随层）",
                      font=("微软雅黑", 10, "bold"), foreground="#555"
                      ).pack(side=tk.LEFT, padx=(8, 0))
        elif self.color_mode == "byblock":
            ttk.Label(color_display_frame, text="ByBlock（随块）",
                      font=("微软雅黑", 10, "bold"), foreground="#555"
                      ).pack(side=tk.LEFT, padx=(8, 0))
        else:
            color_name = ACI_COLORS.get(self.selected_color_index, ("",))[0]
            rgb = ACI_COLORS.get(self.selected_color_index, ("", (128, 128, 128)))[1]
            if rgb:
                hex_c = rgb_to_hex(*rgb)
                tk.Label(color_display_frame, text="  " * 8,
                         bg=hex_c, relief=tk.SUNKEN, borderwidth=2
                         ).pack(side=tk.LEFT, padx=(8, 5))
            ttk.Label(color_display_frame, text=f"ACI {self.selected_color_index} ({color_name})",
                      font=("微软雅黑", 9)).pack(side=tk.LEFT)

        # 信息行
        info_items = [
            ("目标标签：", f"【{self.selected_tag}】"),
            ("选中块数：", f"{len(self.blocks)} 个带属性块"),
            ("修改范围：", "仅非空值的属性" if self.non_empty_only else "所有属性（含空值）"),
            ("颜色模式：",
             "真彩色 RGB" if self.color_mode == "true_color" else
             "ACI 索引色" if self.color_mode == "aci" else
             "随层 ByLayer" if self.color_mode == "bylayer" else "随块 ByBlock"),
        ]

        for i, (label, value) in enumerate(info_items):
            row_f = ttk.Frame(info_frame)
            row_f.pack(fill=tk.X, pady=2)
            ttk.Label(row_f, text=label, font=("微软雅黑", 9)).pack(side=tk.LEFT)
            ttk.Label(row_f, text=value, font=("微软雅黑", 9, "bold"),
                      foreground="#25a").pack(side=tk.LEFT, padx=(5, 0))

        # 结果区域（执行后显示）
        result_frame = ttk.LabelFrame(f, text="📊 执行结果", padding=8)
        result_frame.pack(fill=tk.BOTH, expand=True)

        self._result_text = tk.Text(result_frame, height=8, font=("微软雅黑", 10),
                                    wrap=tk.WORD, state=tk.DISABLED,
                                    bg="#fafafa", relief=tk.SUNKEN, borderwidth=1)
        result_sb = ttk.Scrollbar(result_frame, orient=tk.VERTICAL,
                                  command=self._result_text.yview)
        self._result_text.configure(yscrollcommand=result_sb.set)
        self._result_text.tag_configure("success", foreground="green")
        self._result_text.tag_configure("error", foreground="red")
        self._result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        result_sb.pack(side=tk.RIGHT, fill=tk.Y)

        if self._exec_done:
            self._show_execution_result()

    def _show_execution_result(self) -> None:
        """显示执行结果"""
        self._result_text.configure(state=tk.NORMAL)
        self._result_text.delete(1.0, tk.END)

        total = len(self.blocks)
        self._result_text.insert(tk.END,
            f"✅ 批量修改完成！\n\n"
            f"  总块数: {total}\n"
            f"  成功修改: {self._modified_count}\n"
            f"  跳过: {self._skipped_count}\n\n"
            f"  目标标签: 【{self.selected_tag}】\n",
            "success")

        if self.color_mode == "true_color":
            r, g, b = self.selected_rgb
            self._result_text.insert(tk.END,
                f"  颜色: RGB({r}, {g}, {b})\n")
        elif self.color_mode == "bylayer":
            self._result_text.insert(tk.END,
                f"  颜色: ByLayer（随层）\n")
        elif self.color_mode == "byblock":
            self._result_text.insert(tk.END,
                f"  颜色: ByBlock（随块）\n")
        else:
            color_name = ACI_COLORS.get(self.selected_color_index, ("未知",))[0]
            self._result_text.insert(tk.END,
                f"  颜色: ACI {self.selected_color_index} ({color_name})\n")

        if self._modified_count > 0:
            self._result_text.insert(tk.END,
                "\n💡 提示: 在 AutoCAD 中执行 REGEN 可刷新显示。\n")

        self._result_text.configure(state=tk.DISABLED)

    # ══════════════════════════════════════
    #  执行颜色修改
    # ══════════════════════════════════════

    def _execute_color_change(self) -> None:
        """批量修改属性文字颜色"""
        if self.acad is None or self.blocks is None:
            self.log("请先连接并选择块！", "ERROR")
            return

        if not self.selected_tag:
            self.log("请先选择属性标签！", "ERROR")
            return

        if not self.color_mode:
            self.log("请先选择颜色！", "ERROR")
            return

        self._set_busy(True, "正在修改...")
        self.log("开始批量修改属性文字颜色...")
        self.root.update()

        try:
            self._modified_count = 0
            self._skipped_count = 0
            tag = self.selected_tag
            total = len(self.blocks)

            for idx, blk in enumerate(self.blocks):
                # 获取属性实体
                attr_ent = self.acad.get_attribute_entity(blk, tag)
                if attr_ent is None:
                    self._skipped_count += 1
                    logger.debug("块 %d 没有标签 %s", idx, tag)
                    continue

                # 如果仅修改非空值，检查值是否为空
                if self.non_empty_only:
                    val = attr_ent.TextString
                    if not val or not val.strip():
                        self._skipped_count += 1
                        continue

                # 设置颜色
                success = False
                if self.color_mode == "aci":
                    success = self.acad.set_attribute_color(
                        attr_ent, self.selected_color_index)
                elif self.color_mode == "true_color":
                    r, g, b = self.selected_rgb
                    success = self.acad.set_attribute_true_color(
                        attr_ent, r, g, b)
                elif self.color_mode == "bylayer":
                    success = self.acad.set_attribute_color_by_layer(attr_ent)
                elif self.color_mode == "byblock":
                    success = self.acad.set_attribute_color_by_block(attr_ent)

                if success:
                    self._modified_count += 1
                else:
                    self._skipped_count += 1

                # 每 20 块刷新窗口
                if (idx + 1) % 20 == 0:
                    self.log(f"进度: {idx+1}/{total}（已改 {self._modified_count} 个）", "INFO")
                    self.root.update()

            # 强制刷新
            try:
                self.acad.doc.Regen()
            except Exception:
                pass

            self._exec_done = True
            self.log(
                f"✅ 批量修改完成: 成功 {self._modified_count} 个, "
                f"跳过 {self._skipped_count} 个",
                "SUCCESS"
            )
            write_log(
                f"颜色修改完成: 标签={tag}, 模式={self.color_mode}, "
                f"成功={self._modified_count}, 跳过={self._skipped_count}"
            )

            # 显示结果
            if self._step_frames[3] is not None:
                self._show_execution_result()

            self._set_busy(False)
            self._update_buttons()

            # 提示
            if self._modified_count > 0:
                mb.showinfo("修改完成",
                    f"✅ 成功修改 {self._modified_count} 个属性文字的颜色。\n"
                    f"跳过 {self._skipped_count} 个。\n\n"
                    "如果 CAD 中未立即显示，请执行 REGEN 命令刷新。")

        except Exception as e:
            self.log(f"修改失败: {e}", "ERROR")
            write_log(f"颜色修改失败: {e}\n{traceback.format_exc()}", "ERROR")
            self._set_busy(False, success=False)
            mb.showerror("执行错误", f"修改颜色时发生错误:\n{e}")

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
