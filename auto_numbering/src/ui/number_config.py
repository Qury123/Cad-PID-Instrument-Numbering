#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
编号配置对话框

让用户配置编号样式：
1. 编号前缀
2. 起始编号
3. 补零位数
4. Y 坐标容差
5. 自动顺延模式
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "prefix": "",
    "start_number": 1,
    "pad_width": 3,
    "y_tolerance": 50.0,
    "auto_continue": True,
}

NumberConfig = Dict[str, Any]


class NumberConfigDialog:
    """编号配置对话框

    用法:
        dialog = NumberConfigDialog(selected_types=["PT", "TE"])
        result = dialog.show()
    """

    def __init__(
        self,
        selected_types: List[str],
        last_config: Optional[NumberConfig] = None,
    ) -> None:
        self.selected_types = selected_types
        self.last_config = last_config or {}
        self.result: Optional[NumberConfig] = None

        self.root = tk.Tk()
        self.root.title("③ 配置编号格式 - 仪表编号插件")
        self.root.geometry("580x420")
        self.root.minsize(520, 380)
        self.root.attributes("-topmost", True)
        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        ttk.Label(frame, text="配置编号格式",
                  font=("微软雅黑", 13, "bold")).pack(anchor=tk.W)

        types_str = ", ".join(self.selected_types)
        ttk.Label(frame, text=f"将对以下类型独立编号: {types_str}",
                  font=("微软雅黑", 9), foreground="#555",
                  ).pack(anchor=tk.W, pady=(5, 15))

        # 表单区域
        form = ttk.Frame(frame)
        form.pack(fill=tk.BOTH, expand=True)

        self._entries: Dict[str, Any] = {}

        fields = [
            ("编号前缀", "prefix", self.last_config.get("prefix", ""),
             "如 PT-、TE-，留空则不加前缀"),
            ("起始编号", "start_number", self.last_config.get("start_number", 1),
             "从几开始编号（纯数字，≥1）"),
            ("补零位数", "pad_width", self.last_config.get("pad_width", 3),
             "如 3→001,002；0=不补零"),
            ("Y 容差", "y_tolerance", self.last_config.get("y_tolerance", 50.0),
             "Y坐标差在此范围内视为同一行（mm）"),
        ]

        for idx, (label, key, default_value, hint) in enumerate(fields):
            ttk.Label(form, text=label, font=("微软雅黑", 10)
                      ).grid(row=idx, column=0, sticky=tk.W, pady=(0, 10))

            entry = ttk.Entry(form, width=20, font=("微软雅黑", 10))
            entry.insert(0, str(default_value))
            entry.grid(row=idx, column=1, sticky=tk.W, padx=(10, 5), pady=(0, 10))

            ttk.Label(form, text=hint, foreground="#888", font=("微软雅黑", 8),
                      ).grid(row=idx, column=2, sticky=tk.W, padx=(5, 0), pady=(0, 10))

            self._entries[key] = entry

        # 自动顺延
        auto_frame = ttk.Frame(frame)
        auto_frame.pack(fill=tk.X, pady=(10, 0))

        self._auto_var = tk.BooleanVar(
            value=self.last_config.get("auto_continue", True)
        )
        tk.Checkbutton(auto_frame, text="自动顺延：从现有编号最大值+1开始",
                       variable=self._auto_var, font=("微软雅黑", 9),
                       ).pack(anchor=tk.W)
        ttk.Label(auto_frame, text="勾选后「起始编号」字段将被忽略",
                  foreground="#999", font=("微软雅黑", 8),
                  ).pack(anchor=tk.W, padx=(20, 0))

        # 实时预览
        preview_frame = ttk.Frame(frame)
        preview_frame.pack(fill=tk.X, pady=(12, 0))

        ttk.Label(preview_frame, text="编号预览：",
                  font=("微软雅黑", 9, "bold")).pack(anchor=tk.W)

        self._preview_var = tk.StringVar(value=self._update_preview())
        ttk.Label(preview_frame, textvariable=self._preview_var,
                  foreground="#2a7", font=("微软雅黑", 11, "bold"),
                  ).pack(anchor=tk.W, pady=(3, 0))

        for entry in self._entries.values():
            entry.bind("<KeyRelease>", lambda e: self._refresh_preview())
        self._auto_var.trace_add("write", lambda *_: self._refresh_preview())

        # 底部按钮（始终可见）
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(15, 0))

        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=12
                   ).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="✅ 开始编号", command=self._on_confirm, width=14
                   ).pack(side=tk.RIGHT)

    def _get_values(self) -> NumberConfig:
        prefix = self._entries["prefix"].get().strip()
        try:
            start_number = int(self._entries["start_number"].get())
        except ValueError:
            start_number = 1
        try:
            pad_width = int(self._entries["pad_width"].get())
        except ValueError:
            pad_width = 3
        try:
            y_tolerance = float(self._entries["y_tolerance"].get())
        except ValueError:
            y_tolerance = 50.0
        return {
            "prefix": prefix,
            "start_number": max(1, start_number),
            "pad_width": max(0, pad_width),
            "y_tolerance": max(1.0, y_tolerance),
            "auto_continue": self._auto_var.get(),
        }

    def _format_number(self, num: int, config: NumberConfig) -> str:
        num_str = str(num).zfill(config["pad_width"]) if config["pad_width"] > 0 else str(num)
        return f"{config['prefix']}{num_str}"

    def _update_preview(self) -> str:
        config = self._get_values()
        if config["auto_continue"]:
            nums = [self._format_number(i, config) for i in range(1, 4)]
            return f"自动顺延 → {', '.join(nums)}..."
        else:
            start = config["start_number"]
            nums = [self._format_number(i, config) for i in range(start, start + 3)]
            return f"{', '.join(nums)}..."

    def _refresh_preview(self) -> None:
        self._preview_var.set(self._update_preview())

    def _on_confirm(self) -> None:
        config = self._get_values()
        if config["start_number"] < 1:
            from tkinter.messagebox import showwarning
            showwarning("提示", "起始编号必须 ≥ 1")
            return
        if config["pad_width"] < 0:
            from tkinter.messagebox import showwarning
            showwarning("提示", "补零位数不能为负数")
            return
        if config["y_tolerance"] < 1.0:
            from tkinter.messagebox import showwarning
            showwarning("提示", "Y容差至少为 1.0")
            return
        self.result = config
        self.root.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.root.destroy()

    def show(self) -> Optional[NumberConfig]:
        self.root.mainloop()
        return self.result


# ── 独立测试 ──────────────────────────
def demo():
    dialog = NumberConfigDialog(
        selected_types=["PT", "TE", "TT"],
        last_config={"prefix": "PT-", "start_number": 1, "pad_width": 3,
                     "y_tolerance": 50.0, "auto_continue": False},
    )
    result = dialog.show()
    if result:
        print(f"✅ 配置: {result}")
    else:
        print("❌ 用户取消")

if __name__ == "__main__":
    demo()
