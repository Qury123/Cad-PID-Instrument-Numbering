#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量修改块属性文字颜色插件 — 启动入口

使用方法：
  双击 run.bat 或在命令行输入：python run.py

所有操作都在可视化窗口 + AutoCAD 内完成，无需查看命令行。
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """启动主窗口"""
    # 先检查依赖
    try:
        import pyautocad
    except ImportError:
        import tkinter.messagebox as mb
        mb.showerror("依赖缺失", "pyautocad 未安装。\n请运行: pip install -r requirements.txt")
        sys.exit(1)

    try:
        import win32com.client
    except ImportError:
        import tkinter.messagebox as mb
        mb.showerror("依赖缺失", "pywin32 未安装。\n请运行: pip install -r requirements.txt")
        sys.exit(1)

    # 启动主窗口
    from src.main_window import MainWindow

    win = MainWindow()
    win.show()


if __name__ == "__main__":
    main()
