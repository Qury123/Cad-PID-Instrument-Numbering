#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
代号多选对话框

列出所有仪表类型值（如 PT, TE, TT, FT...），
用户通过复选框多选需要编号的类型。
支持全选、取消全选，鼠标滚轮滚动。
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class CodeSelectorDialog:
    """代号多选对话框

    用法:
        dialog = CodeSelectorDialog(
            type_tag="SIGNAL",
            all_codes={"PT": 5, "TE": 3, "TT": 2},
            last_selected=["PT", "TE"],
        )
        result = dialog.show()
    """

    def __init__(
        self,
        type_tag: str,
        all_codes: Dict[str, int],
        last_selected: Optional[List[str]] = None,
    ) -> None:
        self.type_tag = type_tag
        self.all_codes = all_codes
        self.last_selected = set(last_selected) if last_selected else set()

        self.result: Optional[List[str]] = None
        self._vars: Dict[str, tk.BooleanVar] = {}

        self.root = tk.Tk()
        self.root.title("② 选择需要编号的仪表类型 - 仪表编号插件")
        self.root.geometry("520x500")
        self.root.minsize(460, 400)
        self.root.attributes("-topmost", True)

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # --- 顶部：标题 + 说明 ---
        ttk.Label(frame, text="选择要编号的仪表类型",
                  font=("微软雅黑", 13, "bold")).pack(anchor=tk.W)

        ttk.Label(frame, text=
            f"属性标签「{self.type_tag}」检测到以下类型值。\n"
            "勾选需要编号的类型，每种类型将独立编号。",
            font=("微软雅黑", 9), foreground="#555",
        ).pack(anchor=tk.W, pady=(5, 10))

        # --- 全选/取消按钮行 ---
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(btn_frame, text="☑ 全选", command=self._select_all, width=10
                   ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="☐ 取消全选", command=self._deselect_all, width=10
                   ).pack(side=tk.LEFT)

        total_blocks = sum(self.all_codes.values())
        ttk.Label(btn_frame,
                  text=f"共 {len(self.all_codes)} 种类型 / {total_blocks} 个块",
                  foreground="#888", font=("微软雅黑", 9),
                  ).pack(side=tk.RIGHT)

        # --- 可滚动复选框列表 ---
        canvas_frame = ttk.Frame(frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        canvas = tk.Canvas(canvas_frame, highlightthickness=0, bg="white")
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        # 鼠标滚轮支持（Windows）
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        scroll_frame.bind("<MouseWheel>", _on_mousewheel)

        # 排序：按出现次数降序，同次数按字母序
        sorted_items = sorted(
            self.all_codes.items(),
            key=lambda x: (-x[1], x[0].upper()),
        )

        for code, count in sorted_items:
            item_frame = ttk.Frame(scroll_frame)
            item_frame.pack(fill=tk.X, padx=5, pady=1)

            var = tk.BooleanVar(value=(code in self.last_selected))
            self._vars[code] = var

            cb = ttk.Checkbutton(item_frame, text="", variable=var, width=2)
            cb.pack(side=tk.LEFT)

            # 类型名称（粗体）
            ttk.Label(item_frame, text=code,
                      font=("微软雅黑", 10, "bold"), width=8,
                      ).pack(side=tk.LEFT, padx=(0, 5))

            # 数量
            ttk.Label(item_frame, text=f"({count} 个块)",
                      foreground="#999", font=("微软雅黑", 9),
                      ).pack(side=tk.LEFT)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- 选中摘要 ---
        self._summary_var = tk.StringVar(value=self._get_summary())
        ttk.Label(frame, textvariable=self._summary_var,
                  foreground="#666", font=("微软雅黑", 9),
                  ).pack(anchor=tk.W, pady=(5, 0))

        for var in self._vars.values():
            var.trace_add("write", lambda *_: self._update_summary())

        # --- 底部按钮（始终可见，用 side=BOTTOM） ---
        btn_frame2 = ttk.Frame(frame)
        btn_frame2.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        ttk.Button(btn_frame2, text="取消", command=self._on_cancel, width=12
                   ).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame2, text="✅ 确认编号", command=self._on_confirm, width=14
                   ).pack(side=tk.RIGHT)

    def _select_all(self) -> None:
        for var in self._vars.values():
            var.set(True)

    def _deselect_all(self) -> None:
        for var in self._vars.values():
            var.set(False)

    def _get_summary(self) -> str:
        selected = [c for c, v in self._vars.items() if v.get()]
        total_blocks = sum(self.all_codes[c] for c in selected)
        if selected:
            return f"✅ 已选 {len(selected)} 种类型，共 {total_blocks} 个块"
        return "⏳ 尚未选择任何类型，请勾选需要编号的仪表类型"

    def _update_summary(self) -> None:
        self._summary_var.set(self._get_summary())

    def _on_confirm(self) -> None:
        selected = [c for c, v in self._vars.items() if v.get()]
        if not selected:
            from tkinter.messagebox import showwarning
            showwarning("提示", "请至少选择一种需要编号的仪表类型。")
            return
        self.result = selected
        self.root.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.root.destroy()

    def show(self) -> Optional[List[str]]:
        self.root.mainloop()
        return self.result


# ── 独立测试 ──────────────────────────
def demo():
    test_data = {
        "PT": 12, "TE": 8, "TT": 5, "FT": 6,
        "LT": 3, "PDT": 2, "AT": 4, "PIT": 7,
        "FIT": 3, "LIT": 4, "TT_PLANT": 2,
    }
    dialog = CodeSelectorDialog(
        type_tag="SIGNAL", all_codes=test_data,
        last_selected=["PT", "TE"],
    )
    result = dialog.show()
    if result:
        print(f"✅ 选择了: {result}")
    else:
        print("❌ 用户取消")

if __name__ == "__main__":
    demo()
