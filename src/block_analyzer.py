#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
块属性分析器

分析 AutoCAD 选中的带属性块，提取属性标签、值，并按仪表类型分组。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from src.acad_com import AcadConnect

logger = logging.getLogger(__name__)

# ── 数据结构 ──────────────────────────
# 一个块的完整属性信息
BlockAttributeInfo = Dict[str, Tuple[str, Any]]
# 键 = 属性标签名, 值 = (属性值, 属性实体)


class BlockAnalyzer:
    """块属性分析器

    用法:
        analyzer = BlockAnalyzer(acad)
        blocks = analyzer.select_blocks()       # 用户框选块
        tags = analyzer.get_all_tags(blocks)    # 所有唯一标签名
        info = analyzer.get_blocks_info(blocks) # 每个块的所有属性
        values = analyzer.get_unique_values(blocks, "SIGNAL")  # 某标签的唯一值列表
    """

    def __init__(self, acad: AcadConnect) -> None:
        self.acad = acad

    # ── 选择块 ────────────────────────────

    def select_blocks(self, prompt_text: str = "请框选带属性的仪表块...") -> List[Any]:
        """让用户框选带属性的 INSERT 块"""
        return self.acad.select_blocks_with_attributes(prompt_text=prompt_text)

    def read_active_blocks(self) -> List[Any]:
        """读取 CAD 当前选中的带属性块（用户预先选好的）"""
        all_entities = self.acad.get_active_selection()
        blocks = []
        for ent in all_entities:
            try:
                if ent.EntityName == "AcDbBlockReference":
                    atts = ent.GetAttributes()
                    if len(atts) > 0:
                        blocks.append(ent)
            except Exception:
                pass
        logger.info("当前选中中过滤出 %d 个带属性块", len(blocks))
        return blocks

    # ── 获取所有唯一标签 ──────────────────

    @staticmethod
    def get_all_tags(block_refs: List[Any]) -> List[str]:
        """从选中的块中提取所有唯一的属性标签名，按首次出现顺序返回

        Args:
            block_refs: INSERT 实体列表

        Returns:
            排序后的唯一标签名列表
        """
        seen: Set[str] = set()
        ordered: List[str] = []
        for blk in block_refs:
            for tag, _, _ in AcadConnect.get_block_attributes(blk):
                tag_upper = tag.upper()
                if tag_upper not in seen:
                    seen.add(tag_upper)
                    ordered.append(tag)  # 保留原始大小写
        logger.info("共发现 %d 个唯一属性标签", len(ordered))
        return ordered

    # ── 获取每个块的完整属性映射 ──────────

    @staticmethod
    def get_blocks_info(block_refs: List[Any]) -> List[BlockAttributeInfo]:
        """获取每个选中块的全部属性，以字典形式返回

        Returns:
            [ { tag: (value, entity), ... }, ... ]  每个块一个字典
        """
        result: List[BlockAttributeInfo] = []
        for blk in block_refs:
            info: BlockAttributeInfo = {}
            for tag, value, attr_ent in AcadConnect.get_block_attributes(blk):
                info[tag] = (value, attr_ent)
            if info:  # 只保留有属性的块
                result.append(info)
        logger.info("解析了 %d 个块的属性", len(result))
        return result

    # ── 获取某标签的唯一值列表 ────────────

    @staticmethod
    def get_unique_values(
        block_refs: List[Any], tag_name: str
    ) -> List[str]:
        """获取选中块中指定标签的所有唯一值（去重、按字母排序）

        Args:
            block_refs: INSERT 实体列表
            tag_name: 要提取的标签名

        Returns:
            唯一值列表（去除空值）
        """
        values: Set[str] = set()
        for blk in block_refs:
            val = AcadConnect.get_attribute_value(blk, tag_name)
            if val and val.strip():
                values.add(val.strip())
        sorted_vals = sorted(values, key=str.upper)
        logger.info(
            "标签 '%s' 共有 %d 个唯一值: %s",
            tag_name,
            len(sorted_vals),
            sorted_vals,
        )
        return sorted_vals

    # ── 按类型值过滤块 ────────────────────

    @staticmethod
    def filter_blocks_by_type(
        block_refs: List[Any],
        type_tag: str,
        selected_types: List[str],
    ) -> List[Any]:
        """只保留指定类型值的块

        Args:
            block_refs: 所有选中的块
            type_tag: 仪表类型标签名
            selected_types: 用户选择的类型值列表（如 ["PT", "TE"]）

        Returns:
            过滤后的块列表
        """
        selected_upper = {t.upper() for t in selected_types}
        filtered = []
        for blk in block_refs:
            val = AcadConnect.get_attribute_value(blk, type_tag)
            if val and val.strip().upper() in selected_upper:
                filtered.append(blk)
        logger.info(
            "类型过滤: %d → %d 个块", len(block_refs), len(filtered)
        )
        return filtered

    # ── 按类型分组 ────────────────────────

    @staticmethod
    def group_blocks_by_type(
        block_refs: List[Any],
        type_tag: str,
    ) -> Dict[str, List[Any]]:
        """按仪表类型值将块分组

        Returns:
            { "PT": [block1, block2, ...], "TE": [block3, ...] }
        """
        groups: Dict[str, List[Any]] = defaultdict(list)
        for blk in block_refs:
            val = AcadConnect.get_attribute_value(blk, type_tag)
            if val and val.strip():
                groups[val.strip()].append(blk)
        logger.info(
            "按类型分组成 %d 组: %s", len(groups), list(groups.keys())
        )
        return dict(groups)

    # ── 获取标签的示例值（用于下拉框预览） ─

    @staticmethod
    def get_tag_sample_values(
        block_refs: List[Any], tag_name: str, max_samples: int = 3
    ) -> List[str]:
        """获取某标签的若干示例值，用于 UI 预览"""
        samples = []
        for blk in block_refs:
            val = AcadConnect.get_attribute_value(blk, tag_name)
            if val and val.strip() and val.strip() not in samples:
                samples.append(val.strip())
                if len(samples) >= max_samples:
                    break
        return samples


# ── 快速测试 ──────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("🔍 块属性分析器测试")
    print("=" * 50)

    acad = AcadConnect()
    analyzer = BlockAnalyzer(acad)

    print("\n请框选一些带属性的仪表块（框选后自动读取）...")
    try:
        blocks = analyzer.select_blocks()
    except Exception as e:
        print(f"❌ 选择取消或出错: {e}")
        exit(1)

    if not blocks:
        print("❌ 未选中任何块")
        exit(1)

    print(f"\n✅ 选中 {len(blocks)} 个块")

    # 1. 获取所有标签
    tags = analyzer.get_all_tags(blocks)
    print(f"\n📋 属性标签列表:")
    for i, tag in enumerate(tags, 1):
        samples = analyzer.get_tag_sample_values(blocks, tag, max_samples=2)
        sample_str = f" (示例值: {', '.join(samples)})" if samples else ""
        print(f"   {i}. {tag}{sample_str}")

    # 2. 如果标签不多，遍历展示每个块的值
    print(f"\n📋 各块属性详情:")
    infos = analyzer.get_blocks_info(blocks)
    for idx, info in enumerate(infos, 1):
        vals = {tag: val for tag, (val, _) in info.items()}
        print(f"   块{idx}: {vals}")

    print("\n✅ 属性分析完成！")
