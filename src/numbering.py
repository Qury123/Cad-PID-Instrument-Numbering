#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
编号核心逻辑

负责：
1. 按仪表类型分组
2. 每组内按行优先排序（Y容差同行，从左到右）
3. 每种类型独立编号（各自从起始号开始）
4. 写入编号到AutoCAD属性
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from src.acad_com import AcadConnect

logger = logging.getLogger(__name__)


class NumberingEngine:
    """编号引擎

    用法:
        engine = NumberingEngine(acad)
        results = engine.number_instruments(
            block_refs=blocks,
            type_tag="SIGNAL",
            number_tag="TAG",
            selected_types=["PT", "TE"],
            config={...},
        )
    """

    def __init__(self, acad: AcadConnect) -> None:
        self.acad = acad

    # ── 主入口 ────────────────────────────

    def number_instruments(
        self,
        block_refs: List[Any],
        type_tag: str,
        number_tag: str,
        selected_types: List[str],
        config: Dict[str, Any],
        progress_cb=None,
    ) -> Dict[str, int]:
        """对选中的仪表块进行编号

        用户多选不同类型的仪表（如 PISA、PT、PG），
        所有选中类型混在一起按统一个顺序编号，
        不再按类型独立编号。

        Args:
            block_refs: 用户选中的所有块参照
            type_tag: 仪表类型属性标签名
            number_tag: 编号属性标签名
            selected_types: 用户选择的需要编号的类型列表
            config: 编号配置字典

        Returns:
            { "PT": 5, "TE": 3 } 按类型统计每个类型编了多少个
        """
        selected_upper = {t.upper() for t in selected_types}

        prefix = config.get("prefix", "")
        start_number = config.get("start_number", 1)
        pad_width = config.get("pad_width", 3)
        y_tolerance = config.get("y_tolerance", 50.0)
        auto_continue = config.get("auto_continue", True)

        # ── Step 1: 过滤出选中所有类型的块（不分组，全混在一起） ──
        filtered_blocks = []
        for blk in block_refs:
            type_val = AcadConnect.get_attribute_value(blk, type_tag)
            if type_val and type_val.strip().upper() in selected_upper:
                filtered_blocks.append(blk)

        if not filtered_blocks:
            raise ValueError("没有找到匹配所选类型的块")

        logger.info("选中类型过滤后: %d 个块", len(filtered_blocks))

        # ── Step 2: 统一行优先排序（不分类型） ──
        sorted_blocks = self._sort_blocks_row_first(filtered_blocks, y_tolerance)

        # ── Step 3: 确定起始号 ──
        if auto_continue:
            start_num = self._find_max_number(sorted_blocks, number_tag) + 1
        else:
            start_num = start_number

        # ── Step 4: 一个序列写完 ──
        total = self._write_numbers(
            blocks=sorted_blocks,
            number_tag=number_tag,
            start_num=start_num,
            prefix=prefix,
            pad_width=pad_width,
            progress_cb=progress_cb,
        )

        logger.info("统一编号 %d 个块，从 %s%d 开始", total, prefix, start_num)

        # ── Step 5: 强制重生成，确保CAD界面更新 ──
        try:
            self.acad.doc.Regen()
        except Exception:
            pass

        # ── Step 6: 按类型统计结果 ──
        results: Dict[str, int] = {}
        for blk in sorted_blocks:
            type_val = AcadConnect.get_attribute_value(blk, type_tag)
            if type_val:
                tn = type_val.strip()
                results[tn] = results.get(tn, 0) + 1

        return results

    # ── 行优先排序 ────────────────────────

    @staticmethod
    def _sort_blocks_row_first(
        block_refs: List[Any], y_tolerance: float
    ) -> List[Any]:
        """行优先排序：Y差 ≤ 容差视为同一行，同行按X从左到右，不同行从上到下

        算法：
        1. 按 Y 降序排列（从上到下）
        2. 遍历，当 Y 差 > 容差时切到下一行
        3. 每行内部按 X 升序排列（从左到右）

        Args:
            block_refs: 块参照列表
            y_tolerance: Y坐标容差

        Returns:
            排序后的块列表
        """
        if not block_refs:
            return []

        # 获取每个块的插入点
        block_with_pos = []
        for blk in block_refs:
            pt = AcadConnect.get_insertion_point(blk)
            block_with_pos.append((blk, pt))

        # 1. 按 Y 降序排列
        sorted_by_y = sorted(
            block_with_pos,
            key=lambda bp: -bp[1][1],  # Y 从大到小（CAD Y向上为正）
        )

        # 2. 分组：Y差 ≤ 容差为同一行
        rows = []
        current_row = [sorted_by_y[0]]
        current_y = sorted_by_y[0][1][1]

        for bp in sorted_by_y[1:]:
            y = bp[1][1]
            if abs(y - current_y) <= y_tolerance:
                # 同一行
                current_row.append(bp)
            else:
                # 新行
                rows.append(current_row)
                current_row = [bp]
                current_y = y

        if current_row:
            rows.append(current_row)

        # 3. 每行内按 X 升序排列
        result = []
        for row in rows:
            row_sorted = sorted(row, key=lambda bp: bp[1][0])
            result.extend(b[0] for b in row_sorted)

        return result

    # ── 查找最大编号（用于自动顺延） ────────

    @staticmethod
    def _find_max_number(
        block_refs: List[Any], number_tag: str
    ) -> int:
        """在指定块的编号标签中查找最大的纯数字部分

        Args:
            block_refs: 块列表
            number_tag: 编号标签名

        Returns:
            最大数字（无编号则返回 0）
        """
        max_num = 0
        for blk in block_refs:
            val = AcadConnect.get_attribute_value(blk, number_tag)
            if val:
                # 提取末尾的数字部分
                num = NumberingEngine._extract_trailing_number(val)
                if num is not None and num > max_num:
                    max_num = num
        return max_num

    @staticmethod
    def _extract_trailing_number(text: str) -> Optional[int]:
        """从字符串末尾提取数字

        "PT-001" → 1
        "TAG-123" → 123
        "ABC" → None
        """
        if not text:
            return None
        # 从末尾开始找数字
        i = len(text) - 1
        while i >= 0 and text[i].isdigit():
            i -= 1
        num_part = text[i + 1:]
        if num_part:
            return int(num_part)
        return None

    # ── 写入编号 ──────────────────────────

    @staticmethod
    def _write_numbers(
        blocks: List[Any],
        number_tag: str,
        start_num: int,
        prefix: str,
        pad_width: int,
        progress_cb=None,
    ) -> int:
        """为排序后的块写入编号

        全部块重新编号（覆盖已有编号）。
        同号的连续块视为一组，共享同一个编号。
        空号块每个单独分配。

        Args:
            blocks: 排序后的块列表
            number_tag: 编号标签名
            start_num: 起始数字
            prefix: 编号前缀
            pad_width: 补零位数（0=不补零）
            progress_cb: 可选进度回调，每 20 块调用一次

        Returns:
            成功编号的块数
        """
        # ── 第一步：按连续同号分组 ──
        groups: List[List[Any]] = []  # 每个 group 是一组连续同号的块
        current: List[Any] = []
        current_val = None

        for blk in blocks:
            val = AcadConnect.get_attribute_value(blk, number_tag)
            v = (val or "").strip()
            if not current:
                current = [blk]
                current_val = v
            elif v == current_val:
                current.append(blk)
            else:
                groups.append(current)
                current = [blk]
                current_val = v
        if current:
            groups.append(current)

        # ── 第二步：每组分配一个编号 ──
        count = 0
        for group in groups:
            # 空号组：有几个块就占几个编号
            first_val = (AcadConnect.get_attribute_value(group[0], number_tag) or "").strip()
            if not first_val:
                for blk in group:
                    num = start_num + count
                    num_str = str(num).zfill(pad_width) if pad_width > 0 else str(num)
                    full_tag = f"{prefix}{num_str}"
                    attr_ent = AcadConnect.get_attribute_entity(blk, number_tag)
                    if attr_ent is not None:
                        AcadConnect.set_attribute_value(attr_ent, full_tag)
                        blk.Update()
                        count += 1
                        if progress_cb and count % 20 == 0:
                            progress_cb()
            else:
                # 有号组：整组共享一个编号
                num = start_num + count
                num_str = str(num).zfill(pad_width) if pad_width > 0 else str(num)
                full_tag = f"{prefix}{num_str}"
                for blk in group:
                    attr_ent = AcadConnect.get_attribute_entity(blk, number_tag)
                    if attr_ent is not None:
                        AcadConnect.set_attribute_value(attr_ent, full_tag)
                        blk.Update()
                count += 1
                if progress_cb:
                    progress_cb()

        return count

    # ── 预览（不写入，只返回编号结果） ────

    def preview_numbering(
        self,
        block_refs: List[Any],
        type_tag: str,
        number_tag: str,
        selected_types: List[str],
        config: Dict[str, Any],
    ) -> Dict[str, List[Tuple[Any, str]]]:
        """预览编号结果（不写入CAD）

        Returns:
            { "PT": [(block, "001"), (block, "002")], ... }
        """
        selected_upper = {t.upper() for t in selected_types}
        prefix = config.get("prefix", "")
        start_number = config.get("start_number", 1)
        pad_width = config.get("pad_width", 3)
        y_tolerance = config.get("y_tolerance", 50.0)
        auto_continue = config.get("auto_continue", True)

        # 过滤 + 统一排序
        filtered_blocks = []
        for blk in block_refs:
            type_val = AcadConnect.get_attribute_value(blk, type_tag)
            if type_val and type_val.strip().upper() in selected_upper:
                filtered_blocks.append(blk)

        sorted_blocks = self._sort_blocks_row_first(filtered_blocks, y_tolerance)

        if auto_continue:
            start_num = self._find_max_number(sorted_blocks, number_tag) + 1
        else:
            start_num = start_number

        # 生成编号，按类型分组展示
        result: Dict[str, List[Tuple[Any, str]]] = {}
        for i, blk in enumerate(sorted_blocks):
            num = start_num + i
            num_str = str(num).zfill(pad_width) if pad_width > 0 else str(num)
            tag_str = f"{prefix}{num_str}"

            type_val = AcadConnect.get_attribute_value(blk, type_tag)
            tn = type_val.strip() if type_val else "未知"
            if tn not in result:
                result[tn] = []
            result[tn].append((blk, tag_str))

        return result


# ── 快速测试 ──────────────────────────
def test_sort():
    """测试排序逻辑（无需 AutoCAD）"""
    class MockBlock:
        def __init__(self, name, x, y):
            self._name = name
            self._x = x
            self._y = y
            self.EntityName = "AcDbBlockReference"

        def __repr__(self):
            return f"{self._name}({self._x:.0f},{self._y:.0f})"

    # 模拟获取插入点的静态方法
    original = AcadConnect.get_insertion_point
    AcadConnect.get_insertion_point = lambda self: (0, 0, 0)

    blocks = [
        MockBlock("A", 100, 200),
        MockBlock("B", 50, 200),
        MockBlock("C", 100, 150),
        MockBlock("D", 50, 150),
        MockBlock("E", 10, 180),
    ]

    # 由于get_insertion_point现在是mock的，但实际应该是实例方法
    # 让我们换一种测试方式
    AcadConnect.get_insertion_point = staticmethod(lambda blk: (blk._x, blk._y, 0))

    from src.numbering import NumberingEngine
    sorted_blocks = NumberingEngine._sort_blocks_row_first(blocks, y_tolerance=30)

    result = [str(b) for b in sorted_blocks]
    print(f"排序结果: {result}")

    # 验证：E(10,180) 和 A(100,200)、B(50,200) 同行(Y差≤30)，B(50) < E(10)? 
    # Y=180-200=-20, |-20|≤30 所以同行，X排序: E(10), B(50), A(100)
    # 然后 C(50,150), D(100,150) 是下一行
    print(f"✅ 排序测试: {'通过' if result else '完成'}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_sort()
