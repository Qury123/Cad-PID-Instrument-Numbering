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
            try:
                self.app.Visible = True
            except Exception:
                pass  # 某些 CAD 版本/配置只读，不影响连接
            # 获取当前文档（可能返回 None 或无效对象）
            try:
                self.doc = self.app.ActiveDocument
                doc_name = self.doc.Name
            except Exception:
                self.doc = None
                doc_name = "(无法获取文档名，但连接已建立)"
            logger.info("已连接到 AutoCAD: %s", doc_name)
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
        prompt_text: str = "请框选仪表块区域...",
    ) -> List[Any]:
        """提示用户框选对象，返回选中实体列表

        Args:
            prompt_text: 提示文字

        Returns:
            选中的实体对象列表
        """
        import time

        ss_name = f"YQSS_{int(time.time() * 1000)}"

        # ① 清理同名的旧选择集（如果有）
        self._clean_selection_set(ss_name)

        # ② 创建新选择集
        ss = self.doc.SelectionSets.Add(ss_name)

        # ③ 提示用户在 AutoCAD 里选择
        self.prompt(prompt_text)

        # ④ 等待用户选择
        try:
            ss.SelectOnScreen()
        except Exception as exc:
            self._clean_selection_set(ss_name)
            raise AcadConnectError(f"选择操作被取消: {exc}") from exc

        # ⑤ 逐个读取选中实体（不调用 .Count，避免被拒绝）
        entities: List[Any] = []
        idx = 0
        while True:
            try:
                ent = ss.Item(idx)
                entities.append(ent)
                idx += 1
            except Exception:
                break

        # ⑥ 清理
        self._clean_selection_set(ss_name)
        logger.info("选中 %d 个实体", len(entities))
        return entities

    def _clean_selection_set(self, name: str) -> None:
        """安全删除选择集（捕获所有异常）"""
        try:
            for i in range(self.doc.SelectionSets.Count):
                ss = self.doc.SelectionSets.Item(i)
                if ss.Name == name:
                    try:
                        ss.Delete()
                    except Exception:
                        pass
                    break
        except Exception:
            pass

    def select_blocks_with_attributes(
        self, prompt_text: str = "请框选带属性的仪表块..."
    ) -> List[Any]:
        """提示用户框选带属性的 INSERT 块，返回带属性的块参照

        先用 SelectOnScreen 框选全部，再在 Python 中过滤出带属性的块。
        """
        all_entities = self.prompt_select(prompt_text=prompt_text)
        blocks = []
        for ent in all_entities:
            try:
                if ent.EntityName == "AcDbBlockReference":
                    atts = ent.GetAttributes()
                    if len(atts) > 0:
                        blocks.append(ent)
            except Exception:
                pass  # 跳过无法获取属性的实体
        logger.info("过滤后得到 %d 个带属性块", len(blocks))
        return blocks

    # ── 块属性操作 ────────────────────────

    def get_active_selection(self) -> List[Any]:
        """读取 AutoCAD 当前选中的对象（带蓝色夹点的选择）

        用户先在 CAD 里选中对象，然后点插件按钮读取。
        如果无选中对象，返回空列表。
        """
        entities: List[Any] = []
        try:
            ss = self.doc.ActiveSelectionSet
            count = ss.Count
            if count is not None and count > 0:
                for i in range(count):
                    try:
                        ent = ss.Item(i)
                        entities.append(ent)
                    except Exception:
                        pass
                logger.info("读取当前选择: %d 个实体", len(entities))
            else:
                logger.info("当前选择集为空")
        except Exception:
            logger.info("读取当前选择失败（无选中对象）")
        return entities

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

    @staticmethod
    def get_bounding_box(block_ref: Any) -> Tuple[Point3D, Point3D]:
        """获取块参照的包围盒 (min_point, max_point)

        Returns:
            ((min_x, min_y, min_z), (max_x, max_y, max_z))
            失败时返回 ((0,0,0), (0,0,0))
        """
        try:
            # AutoCAD COM: GetBoundingBox(MinPoint, MaxPoint)
            min_pt = block_ref.GetBoundingBox()
            # win32com 返回一个元组 (minPoint, maxPoint)
            if isinstance(min_pt, tuple) and len(min_pt) == 2:
                return (tuple(min_pt[0]), tuple(min_pt[1]))
            return ((0, 0, 0), (0, 0, 0))
        except Exception:
            # 回退：用插入点估算（某些块不支持 GetBoundingBox）
            ip = AcadConnect.get_insertion_point(block_ref)
            return ((ip[0] - 0.5, ip[1] - 0.5, 0), (ip[0] + 0.5, ip[1] + 0.5, 0))

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
