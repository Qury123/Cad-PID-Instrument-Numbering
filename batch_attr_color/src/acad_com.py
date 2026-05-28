#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AutoCAD COM 连接层

通过 COM 接口与正在运行的 AutoCAD 通信。
基于 pywin32 + pyautocad 封装常用操作。

新增颜色相关操作：获取/设置属性文字的 ACI 颜色索引和真彩色。
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

import win32com.client

logger = logging.getLogger(__name__)

# ── 类型别名 ──────────────────────────
Point3D = Tuple[float, float, float]


class AcadConnectError(Exception):
    """AutoCAD 连接相关的错误"""


# ── ACI 颜色常量 ──────────────────────
ACI_COLORS = {
    1:  ("红",     (255, 0, 0)),
    2:  ("黄",     (255, 255, 0)),
    3:  ("绿",     (0, 255, 0)),
    4:  ("青",     (0, 255, 255)),
    5:  ("蓝",     (0, 0, 255)),
    6:  ("品红",   (255, 0, 255)),
    7:  ("白/黑",  (255, 255, 255)),  # 背景色决定
    8:  ("深灰",   (128, 128, 128)),
    9:  ("浅灰",   (192, 192, 192)),
    10: ("红橙",   (255, 80, 0)),
    11: ("橙",     (255, 128, 0)),
    12: ("橙黄",   (255, 200, 0)),
    13: ("黄绿",   (128, 255, 0)),
    14: ("浅绿",   (0, 255, 128)),
    15: ("天蓝",   (0, 255, 255)),
    16: ("浅蓝",   (0, 128, 255)),
    20: ("褐",     (128, 64, 0)),
    30: ("橙红",   (255, 64, 0)),
    40: ("粉红",   (255, 128, 128)),
    50: ("紫",     (128, 0, 255)),
    60: ("靛",     (64, 0, 255)),
    70: ("淡紫",   (128, 128, 255)),
    80: ("灰绿",   (128, 255, 128)),
    90: ("灰青",   (128, 255, 255)),
    100: ("灰蓝",  (128, 192, 255)),
    110: ("灰紫",  (192, 128, 255)),
    120: ("灰品",  (255, 128, 192)),
    130: ("淡红",  (255, 128, 128)),
    140: ("淡橙",  (255, 200, 128)),
    150: ("淡黄",  (255, 255, 128)),
    160: ("淡绿",  (128, 255, 128)),
    170: ("淡青",  (128, 255, 255)),
    180: ("淡蓝",  (128, 200, 255)),
    190: ("淡紫",  (200, 128, 255)),
    200: ("深红",  (200, 0, 0)),
    210: ("深橙",  (200, 100, 0)),
    220: ("深黄",  (200, 200, 0)),
    230: ("深绿",  (0, 128, 0)),
    240: ("深青",  (0, 128, 128)),
    250: ("深蓝",  (0, 0, 128)),
    251: ("深品",  (128, 0, 128)),
    252: ("墨绿",  (0, 64, 0)),
    253: ("墨青",  (0, 64, 64)),
    254: ("墨蓝",  (0, 0, 64)),
    256: ("ByLayer", None),   # 随层
    0:   ("ByBlock", None),   # 随块
}

# 常用颜色快速选择（色板用）
QUICK_COLORS = [
    (1,  "红",     "#FF0000"),
    (2,  "黄",     "#FFFF00"),
    (3,  "绿",     "#00FF00"),
    (4,  "青",     "#00FFFF"),
    (5,  "蓝",     "#0000FF"),
    (6,  "品红",   "#FF00FF"),
    (7,  "白",     "#FFFFFF"),
    (8,  "深灰",   "#808080"),
    (9,  "浅灰",   "#C0C0C0"),
    (10, "红橙",   "#FF5000"),
    (11, "橙",     "#FF8000"),
    (30, "橙红",   "#FF4000"),
    (50, "紫",     "#8000FF"),
    (20, "褐",     "#804000"),
    (40, "粉红",   "#FF8080"),
    (230, "深绿",  "#008000"),
    (250, "深蓝",  "#000080"),
    (200, "深红",  "#C80000"),
    (240, "深青",  "#008080"),
]


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

        # ① 清理同名的旧选择集
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

        # ⑤ 逐个读取选中实体
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
        self, prompt_text: str = "请框选带属性的块..."
    ) -> List[Any]:
        """提示用户框选带属性的 INSERT 块，返回带属性的块参照"""
        all_entities = self.prompt_select(prompt_text=prompt_text)
        blocks = []
        for ent in all_entities:
            try:
                if ent.EntityName == "AcDbBlockReference":
                    atts = ent.GetAttributes()
                    if len(atts) > 0:
                        blocks.append(ent)
            except Exception:
                pass
        logger.info("过滤后得到 %d 个带属性块", len(blocks))
        return blocks

    # ── 当前选择读取 ──────────────────────

    def get_active_selection(self) -> List[Any]:
        """读取 AutoCAD 当前选中的对象（带蓝色夹点的选择）"""
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

    # ── 块属性操作 ────────────────────────

    @staticmethod
    def get_block_attributes(block_ref: Any) -> List[Tuple[str, str, Any]]:
        """获取块参照的所有属性标签和值

        Returns:
            [(tag_name, value, attrib_entity), ...]
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

    # ── 颜色操作 ──────────────────────────

    @staticmethod
    def get_attribute_color(attrib_entity: Any) -> int:
        """获取属性实体的 ACI 颜色索引

        Returns:
            ACI 颜色索引 (0-256)，失败返回 None
        """
        try:
            return attrib_entity.Color
        except Exception:
            return None

    @staticmethod
    def set_attribute_color(attrib_entity: Any, color_index: int) -> bool:
        """设置属性实体的 ACI 颜色索引

        Args:
            attrib_entity: 属性实体 (AttributeReference)
            color_index: ACI 颜色索引 (0-256)

        Returns:
            是否成功
        """
        try:
            attrib_entity.Color = color_index
            attrib_entity.Update()
            return True
        except Exception as exc:
            logger.error("设置颜色失败: %s", exc)
            return False

    @staticmethod
    def set_attribute_true_color(
        attrib_entity: Any, red: int, green: int, blue: int
    ) -> bool:
        """设置属性实体的真彩色 (RGB)

        Args:
            attrib_entity: 属性实体 (AttributeReference)
            red: 0-255
            green: 0-255
            blue: 0-255

        Returns:
            是否成功
        """
        try:
            # 创建 TrueColor 对象
            true_color = win32com.client.Dispatch("AutoCAD.AcadTrueColor")
            true_color.Red = red
            true_color.Green = green
            true_color.Blue = blue
            attrib_entity.TrueColor = true_color
            attrib_entity.Update()
            return True
        except Exception as exc:
            logger.error("设置真彩色失败: %s", exc)
            return False

    @staticmethod
    def set_attribute_color_by_layer(attrib_entity: Any) -> bool:
        """将属性颜色设为 ByLayer（随层）

        ACI 256 = ByLayer
        """
        try:
            attrib_entity.Color = 256
            attrib_entity.Update()
            return True
        except Exception as exc:
            logger.error("设置 ByLayer 失败: %s", exc)
            return False

    @staticmethod
    def set_attribute_color_by_block(attrib_entity: Any) -> bool:
        """将属性颜色设为 ByBlock（随块）

        ACI 0 = ByBlock
        """
        try:
            attrib_entity.Color = 0
            attrib_entity.Update()
            return True
        except Exception as exc:
            logger.error("设置 ByBlock 失败: %s", exc)
            return False

    # ── 标签分析（独立自足，无需 BlockAnalyzer） ──────────

    @staticmethod
    def get_all_tags(block_refs: List[Any]) -> List[str]:
        """从选中的块中提取所有唯一的属性标签名，按首次出现顺序返回

        Args:
            block_refs: INSERT 实体列表

        Returns:
            唯一标签名列表（按首次出现顺序）
        """
        seen: set = set()
        ordered: List[str] = []
        for blk in block_refs:
            for tag, _, _ in AcadConnect.get_block_attributes(blk):
                tag_upper = tag.upper()
                if tag_upper not in seen:
                    seen.add(tag_upper)
                    ordered.append(tag)
        return ordered

    @staticmethod
    def get_tag_sample_values(
        block_refs: List[Any], tag_name: str, max_samples: int = 3
    ) -> List[str]:
        """获取某标签的若干示例值，用于 UI 预览

        Args:
            block_refs: 块列表
            tag_name: 标签名
            max_samples: 最多返回几个示例值

        Returns:
            示例值列表（去重）
        """
        samples = []
        for blk in block_refs:
            val = AcadConnect.get_attribute_value(blk, tag_name)
            if val and val.strip() and val.strip() not in samples:
                samples.append(val.strip())
                if len(samples) >= max_samples:
                    break
        return samples

    # ── 颜色索引转换 ──────────────────────

    @staticmethod
    def get_rgb_from_color_index(color_index: int) -> Optional[Tuple[int, int, int]]:
        """将 ACI 颜色索引转换为近似 RGB 值

        Args:
            color_index: ACI 颜色索引

        Returns:
            (R, G, B) 元组，或 None（如 ByLayer/ByBlock）
        """
        info = ACI_COLORS.get(color_index)
        if info:
            return info[1]  # (r, g, b) or None for ByLayer/ByBlock
        return None

    # ── 工具 ──────────────────────────────

    @staticmethod
    def get_insertion_point(block_ref: Any) -> Point3D:
        """获取块的插入点坐标 (X, Y, Z)"""
        ip = block_ref.InsertionPoint
        return (ip[0], ip[1], ip[2])

    def handle_error(self, user_message: str = "") -> None:
        """AutoCAD 端弹出错误提示"""
        import tkinter.messagebox as mb
        mb.showerror("批量改色插件 - 错误", user_message)
        logger.error(user_message)


# ── 快速测试 ──────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    acad = AcadConnect()
    print(f"📄 当前文档: {acad.get_document_name()}")
    acad.prompt("✅ Python COM 连接测试通过！")

    # 颜色索引测试
    print("\n🎨 常用颜色索引:")
    for idx, (name, rgb) in sorted(ACI_COLORS.items()):
        rgb_str = f"RGB{rgb}" if rgb else "—"
        print(f"  {idx:>3}: {name:<8} {rgb_str}")
    print("\n✅ 颜色库就绪")
