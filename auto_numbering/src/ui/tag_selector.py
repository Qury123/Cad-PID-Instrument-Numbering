#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
标签选择对话框

让用户从所有属性标签中选择：
1. 仪表类型标签（如 SIGNAL、TYPE、PNPAttribute0 等）
2. 编号标签（如 TAG、NUMBER、CODE 等）

附带示例值预览，帮助用户判断。
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TagSelectorDialog:
    """标签选择对话框

    用法:
        dialog = TagSelectorDialog(tags_with_samples)
        result = dialog.show()
        if result:
            type_tag, number_tag = result
    """

    def __init__(
        self,
        tags_with_samples: Dict[str, List[str]],
        last_type_tag: Optional[str] = None,
        last_number_tag: Optional[str] = None,
    ) -> None:
        self.tags = list(tags_with_samples.keys())
        self.samples = tags_with_samples
        self._default_type = last_type_tag
        self._default_number = last_number_tag
        self.result: Optional[Tuple[str, str]] = None

        self.root = tk.Tk()
        self.root.title("① 选择属性标签 - 仪表编号插件")
        self.root.geometry("560x400")
        self.root.minsize(520, 380)
        self.root.attributes("-topmost", True)
        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # 说明
        ttk.Label(
            frame, text="请选择属性标签",
            font=("微软雅黑", 13, "bold"),
        ).pack(anchor=tk.W)

        ttk.Label(frame, text=
            "从下面列表中选择「仪表类型」和「编号」分别对应哪个属性标签。\n"
            "仪表类型标签 → 用来识别仪表种类的属性（如 SIGNAL, TYPE）\n"
            "编号标签 → 要写入编号的属性（如 TAG, NUMBER, CODE）",
            font=("微软雅黑", 9), foreground="#555",
        ).pack(anchor=tk.W, pady=(5, 15))

        # ① 仪表类型标签
        ttk.Label(frame, text="① 仪表类型标签：",
                  font=("微软雅黑", 10, "bold")).pack(anchor=tk.W)
        self._type_var = tk.StringVar()
        self._type_combo = ttk.Combobox(
            frame, textvariable=self._type_var,
            values=self.tags, state="readonly",
            width=55, font=("微软雅黑", 9),
        )
        self._type_combo.pack(fill=tk.X, pady=(0, 3))
        self._type_preview = ttk.Label(frame, text="", foreground="#888")
        self._type_preview.pack(anchor=tk.W, pady=(0, 10))

        # ② 编号标签
        ttk.Label(frame, text="② 编号标签：",
                  font=("微软雅黑", 10, "bold")).pack(anchor=tk.W)
        self._num_var = tk.StringVar()
        self._num_combo = ttk.Combobox(
            frame, textvariable=self._num_var,
            values=self.tags, state="readonly",
            width=55, font=("微软雅黑", 9),
        )
        self._num_combo.pack(fill=tk.X, pady=(0, 3))
        self._num_preview = ttk.Label(frame, text="", foreground="#888")
        self._num_preview.pack(anchor=tk.W, pady=(0, 10))

        self._set_defaults()
        self._type_combo.bind("<<ComboboxSelected>>", self._on_type_select)
        self._num_combo.bind("<<ComboboxSelected>>", self._on_num_select)

        # 底部按钮（始终可见）
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=12
                   ).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="✅ 确认选择", command=self._on_confirm, width=14
                   ).pack(side=tk.RIGHT)

    def _set_defaults(self) -> None:
        if self._default_type and self._default_type in self.tags:
            self._type_var.set(self._default_type)
            self._update_type_preview(self._default_type)
        elif self.tags:
            self._type_var.set(self.tags[0])
            self._update_type_preview(self.tags[0])

        if self._default_number and self._default_number in self.tags:
            self._num_var.set(self._default_number)
            self._update_num_preview(self._default_number)
        elif len(self.tags) > 1:
            self._num_var.set(self.tags[1])
            self._update_num_preview(self.tags[1])

    def _on_type_select(self, event=None) -> None:
        self._update_type_preview(self._type_var.get())

    def _on_num_select(self, event=None) -> None:
        self._update_num_preview(self._num_var.get())

    def _update_type_preview(self, tag: str) -> None:
        samples = self.samples.get(tag, [])
        if samples:
            self._type_preview.config(text=f"示例值: {', '.join(samples[:5])}")
        else:
            self._type_preview.config(text="（该标签暂无示例值）")

    def _update_num_preview(self, tag: str) -> None:
        samples = self.samples.get(tag, [])
        if samples:
            self._num_preview.config(text=f"示例值: {', '.join(samples[:5])}")
        else:
            self._num_preview.config(text="（该标签暂无示例值）")

    def _on_confirm(self) -> None:
        type_tag = self._type_var.get().strip()
        num_tag = self._num_var.get().strip()
        if not type_tag or not num_tag:
            from tkinter.messagebox import showwarning
            showwarning("提示", "请分别选择「仪表类型标签」和「编号标签」。")
            return
        if type_tag == num_tag:
            from tkinter.messagebox import showwarning
            showwarning("提示", "「仪表类型标签」和「编号标签」不能相同。")
            return
        self.result = (type_tag, num_tag)
        self.root.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.root.destroy()

    def show(self) -> Optional[Tuple[str, str]]:
        self.root.mainloop()
        return self.result


# ── 独立测试 ──────────────────────────
def demo():
    test_data = {
        "SIGNAL": ["PT", "TE", "TT", "FT"],
        "TAG": ["T-001", "T-002", "T-003"],
        "PNPAttribute0": ["M", "PG"],
        "DESCRIPTION": ["压力变送器", "温度计"],
        "LINE_NUMBER": ["PL-101", "PL-102"],
    }
    dialog = TagSelectorDialog(test_data)
    result = dialog.show()
    if result:
        print(f"✅ 选择了: 类型标签 = {result[0]}, 编号标签 = {result[1]}")
    else:
        print("❌ 用户取消了选择")

if __name__ == "__main__":
    demo()
