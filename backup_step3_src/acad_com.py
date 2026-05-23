#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AutoCAD COM 连接层

通过 COM 接口与正在运行的 AutoCAD 通信。
基于 pywin32 + pyautocad 封装常用操作。
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

import pyautocad
import win32com.client

logger = logging.getLogger(__name__)

# ── 类型别名 ──────────────────────────
# AutoCAD COM 对象用 Any，不强制类型标注
Point3D = Tuple[float, float, float]


class AcadConnectError(Exception):
    """AutoCAD 连接相关的错误"""


class AcadConnect:
    """AutoCAD COM 连接与操作封装

    用法:
        acad = AcadConnect()
        print(acad.doc.Name)  # 当前文档名
        acad.prompt("Hello from Python!")  # 在CAD命令行输出
    """

    def __init__(self) -> None:
        self.app: Any = None
        self.doc: Any = None
        self._connect()

    # ── 连接 ──────────────────────────────

    def _connect(self) -> None:
        """连接到正在运行的 AutoCAD 实例"""
        try:
            self.app = win32com.client.GetActiveObject("AutoCAD.Application")
            self.app.Visible = True
            self.doc = self.app.ActiveDocument
            logger.info("已连接到 AutoCAD: %s", self.doc.Name)
        except Exception as exc:
            raise AcadConnectError(
                f"无法连接到 AutoCAD。请确保 AutoCAD 正在运行。\n细节: {exc}"
            ) from exc

    # ── 基础操作 ──────────────────────────

    def prompt(self, message: str) -> None:
        """在 AutoCAD 命令行输出文字"""
        self.doc.Utility.Prompt(f"\n{message}")

    def get_document_name(self) -> str:
        """获取当前文档名"""
        return self.doc.Name

    def get_database(self) -> Any:
        """获取当前数据库对象"""
        return self.doc.Database

    # ── 选择集 ────────────────────────────

    def prompt_select(
        self,
        filter_type: Optional[List[int]] = None,
        filter_data: Optional[List[Any]] = None,
        prompt_text: str = "请框选仪表块区域...",
    ) -> List[Any]:
        """提示用户框选对象，返回选中实体列表

        Args:
            filter_type: DXF 过滤器类型码列表，如 [0, 66]
            filter_data: DXF 过滤器值列表，如 ["INSERT", 1]
            prompt_text: 提示文字

        Returns:
            选中的实体对象列表
        """
        # 创建唯一名称的选择集
        ss_name = f"YQSS_{id(self)}"
        try:
            ss = self.doc.SelectionSets.Add(ss_name)
        except Exception:
            # 如果已存在则删除重建
            for i in range(self.doc.SelectionSets.Count):
                s = self.doc.SelectionSets.Item(i)
                if s.Name == ss_name:
                    s.Delete()
                    break
            ss = self.doc.SelectionSets.Add(ss_name)

        self.prompt(prompt_text)

        try:
            if filter_type and filter_data:
                # 构建过滤器
                filter_tuple = self._build_filter(filter_type, filter_data)
                ss.SelectOnScreen(filter_tuple)
            else:
                ss.SelectOnScreen()
        except Exception as exc:
            # 用户可能按了 ESC 取消选择
            ss.Delete()
            raise AcadConnectError(f"选择操作被取消或出错: {exc}") from exc

        entities: List[Any] = []
        for i in range(ss.Count):
            entities.append(ss.Item(i))

        ss.Delete()
        logger.info("选中 %d 个实体", len(entities))
        return entities

    def select_blocks_with_attributes(
        self, prompt_text: str = "请框选带属性的仪表块..."
    ) -> List[Any]:
        """提示用户框选带属性的 INSERT 块 (DXF 66=1)"""
        return self.prompt_select(
            filter_type=[0, 66],
            filter_data=["INSERT", 1],
            prompt_text=prompt_text,
        )

    @staticmethod
    def _build_filter(
        filter_type: List[int], filter_data: List[Any]
    ) -> Tuple[Any, Any]:
        """构建 AutoCAD DXF 过滤器元组"""
        assert len(filter_type) == len(filter_data)
        # 类型码数组 + 值数组 => 两个 Variant
        import array

        ft = array.array("i", filter_type)
        fd = win32com.client.Variant(filter_data)  # type: ignore
        return (ft, fd)

    # ── 块属性操作 ────────────────────────

    @staticmethod
    def get_block_attributes(block_ref: Any) -> List[Tuple[str, str, Any]]:
        """获取块参照的所有属性标签和值

        Args:
            block_ref: AutoCAD BlockReference 或 INSERT 实体

        Returns:
            [(tag_name, value, attrib_entity), ...] 列表
        """
        attributes = []
        for attr in block_ref.GetAttributes():
            tag = attr.TagString
            value = attr.TextString
            attributes.append((tag, value, attr))
        return attributes

    @staticmethod
    def get_attribute_value(block_ref: Any, tag_name: str) -> Optional[str]:
        """获取块上指定属性标签的值"""
        for tag, value, _ in AcadConnect.get_block_attributes(block_ref):
            if tag.upper() == tag_name.upper():
                return value
        return None

    @staticmethod
    def get_attribute_entity(block_ref: Any, tag_name: str) -> Any:
        """获取块上指定标签的属性实体（用于后续修改）"""
        for tag, _, attr_ent in AcadConnect.get_block_attributes(block_ref):
            if tag.upper() == tag_name.upper():
                return attr_ent
        return None

    @staticmethod
    def set_attribute_value(attrib_entity: Any, new_value: str) -> None:
        """设置属性实体的值并更新显示"""
        attrib_entity.TextString = new_value
        attrib_entity.Update()

    @staticmethod
    def get_insertion_point(block_ref: Any) -> Point3D:
        """获取块的插入点坐标 (X, Y, Z)"""
        ip = block_ref.InsertionPoint
        return (ip[0], ip[1], ip[2])

    # ── 工具 ──────────────────────────────

    def handle_error(self, user_message: str = "") -> None:
        """AutoCAD 端弹出错误提示"""
        import tkinter.messagebox as mb

        mb.showerror("仪表编号插件 - 错误", user_message)
        logger.error(user_message)


# ── 快速测试 ──────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    acad = AcadConnect()
    print(f"📄 当前文档: {acad.get_document_name()}")
    acad.prompt("✅ Python COM 连接测试通过！")
    print("✅ 请在 AutoCAD 命令行看到提示文字。")
