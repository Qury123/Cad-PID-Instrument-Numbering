#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
版本信息 — 统一版本号入口
"""
from __future__ import annotations

import os

_VERSION_FILE = os.path.join(os.path.dirname(__file__), "..", "VERSION")


def get_version() -> str:
    """从 VERSION 文件读取版本号"""
    try:
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "VERSION"))
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


def get_version_tuple() -> tuple[int, int, int]:
    """返回 (major, minor, patch)"""
    parts = get_version().split(".")
    try:
        return tuple(int(p) for p in parts[:3])
    except Exception:
        return (0, 0, 0)


def get_build_info() -> str:
    """构建信息，显示在 About 对话框"""
    from datetime import datetime
    ver = get_version()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"v{ver}  build {now}"


__all__ = ["get_version", "get_version_tuple", "get_build_info"]
