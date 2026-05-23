#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
仪表自动编号插件 — 启动入口

工作流程：
  1. 连接 AutoCAD
  2. 用户框选带属性块
  3. 选择仪表类型标签和编号标签
  4. 选择需要编号的仪表类型
  5. 配置编号样式
  6. 按类型独立编号并写入 AutoCAD

使用方法：
  1. 确保 AutoCAD 正在运行，并打开含仪表块的图纸
  2. 运行 python run.py
  3. 按对话框引导操作
"""

import sys
import tkinter.messagebox as mb


def main():
    """主入口 — 逐步实现"""
    print("=" * 50)
    print("  仪表自动编号插件 v1.0")
    print("=" * 50)
    print()
    print("  框架就绪 — 等待各模块实现后串联完整流程。")
    print()
    print("  依赖安装: pip install -r requirements.txt")
    print("  使用方式: python run.py")
    print()
    print("  环境要求:")
    print("    - Windows 系统")
    print("    - AutoCAD 2014+ 正在运行")
    print("    - 打开含仪表属性块的图纸")
    print()

    # Step 9 之前只做框架检查
    try:
        import pyautocad
        print(f"  ✅ pyautocad {pyautocad.__version__} 已安装")
    except ImportError:
        print("  ❌ pyautocad 未安装，请运行: pip install -r requirements.txt")
        sys.exit(1)

    try:
        import win32com.client
        print("  ✅ pywin32 已安装")
    except ImportError:
        print("  ❌ pywin32 未安装，请运行: pip install -r requirements.txt")
        sys.exit(1)

    print()
    print("  ✅ 环境就绪，各模块将在后续步骤中实现。")
    print("=" * 50)


if __name__ == "__main__":
    main()
