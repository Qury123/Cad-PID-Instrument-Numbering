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

    # ── 排序模式常量 ──────────────────────
    SORT_MODE_SELECTION = "selection_order"
    SORT_MODE_ROW_FIRST = "row_first"
    SORT_MODE_SNAKE = "snake_row_first"

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
        sort_mode = config.get("sort_mode", self.SORT_MODE_ROW_FIRST)
        first_block_handle = config.get("first_block_handle", None)
        skip_sort = config.get("_skip_sort", False)

        # ── Step 1: 过滤出选中所有类型的块（不分组，全混在一起） ──
        filtered_blocks = []
        for blk in block_refs:
            type_val = AcadConnect.get_attribute_value(blk, type_tag)
            if type_val and type_val.strip().upper() in selected_upper:
                filtered_blocks.append(blk)

        if not filtered_blocks:
            raise ValueError("没有找到匹配所选类型的块")

        logger.info("选中类型过滤后: %d 个块", len(filtered_blocks))

        # ── Step 2: 统一排序（按配置的排序模式）/ 或使用外部传入顺序 ──
        if skip_sort:
            sorted_blocks = filtered_blocks
        else:
            sorted_blocks = self._sort_blocks(
                filtered_blocks,
                sort_mode=sort_mode,
                y_tolerance=y_tolerance,
                first_handle=first_block_handle,
            )

        # ── Step 2.5: 合并同位置块 ──
        merge_distance = config.get("merge_distance", 20.0)
        number_map = None
        if config.get("merge_overlap", False):
            number_map = self._build_overlap_number_map(
                sorted_blocks, merge_distance=merge_distance, type_tag=type_tag,
            )

        # ── Step 3: 确定起始号 ──
        if auto_continue:
            start_num = self._find_max_number(sorted_blocks, number_tag) + 1
        else:
            start_num = start_number

        # ── Step 4: 一个序列写完 ──
        suffix_map = config.get("_suffix_map", None) if isinstance(config, dict) else None
        tag_override = config.get("_tag_override", None) if isinstance(config, dict) else None
        total = self._write_numbers(
            blocks=sorted_blocks,
            number_tag=number_tag,
            start_num=start_num,
            prefix=prefix,
            pad_width=pad_width,
            number_map=number_map,
            progress_cb=progress_cb,
            suffix_map=suffix_map,
            tag_override=tag_override,
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

    # ── 排序方法 ──────────────────────────

    # ── 主排序入口 ────────────────────────

    def _sort_blocks(
        self,
        block_refs: List[Any],
        sort_mode: str,
        y_tolerance: float,
        first_handle: Optional[str] = None,
    ) -> List[Any]:
        """根据指定的排序模式对块列表排序

        Args:
            block_refs: 块参照列表
            sort_mode: 排序模式 — SORT_MODE_SELECTION / SORT_MODE_ROW_FIRST / SORT_MODE_SNAKE
            y_tolerance: Y坐标容差（仅对行优先/蛇形有效）
            first_handle: 可选，指定排序后第一个块的句柄

        Returns:
            排序后的块列表
        """
        if not block_refs:
            return []

        if sort_mode == self.SORT_MODE_SELECTION:
            sorted_blocks = self._sort_by_selection_order(block_refs, first_handle)
        else:
            rows = self._group_rows(block_refs, y_tolerance)
            snake = (sort_mode == self.SORT_MODE_SNAKE)
            sorted_blocks = self._sort_rows(rows, snake=snake)
            if first_handle:
                sorted_blocks = self._move_to_front(sorted_blocks, first_handle)

        return sorted_blocks

    # ── 行分组 ────────────────────────────

    @staticmethod
    def _group_rows(
        block_refs: List[Any], y_tolerance: float
    ) -> List[List[Any]]:
        """将块按 Y 坐标分组为行

        算法：
        1. 按 Y 降序排列（从上到下）
        2. 遍历，当 Y 差 > 容差时切到下一行

        Args:
            block_refs: 块参照列表
            y_tolerance: Y坐标容差

        Returns:
            行的列表，每行是块列表（每行内部仍未按 X 排序）
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
        rows: List[List[Any]] = []
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

        return rows

    # ── 行排序 ────────────────────────────

    @staticmethod
    def _sort_rows(
        row_groups: List[List[Any]], snake: bool = False
    ) -> List[Any]:
        """将行分组展开为一维排序列表

        每行内部按 X 升序排列（从左到右）；
        若 snake=True，偶数行（0-indexed 的第 1、3、5...行）反转（从右到左）。

        Args:
            row_groups: _group_rows 返回的行分组，每行是 [(blk, (x,y,z)), ...]
            snake: 是否蛇形排列

        Returns:
            排序后的块列表
        """
        result: List[Any] = []
        for i, row in enumerate(row_groups):
            # 每行内按 X 升序排列
            row_sorted = sorted(row, key=lambda bp: bp[1][0])
            if snake and i % 2 == 1:
                # 偶数行（第2、4…行）反转
                row_sorted.reverse()
            result.extend(b[0] for b in row_sorted)
        return result

    # ── 按选择顺序 ────────────────────────

    @staticmethod
    def _sort_by_selection_order(
        block_refs: List[Any], first_handle: Optional[str] = None
    ) -> List[Any]:
        """保持用户选择的原始顺序

        若指定了 first_handle，将该块移到头部，其余保持原顺序。

        Args:
            block_refs: 块参照列表（保持原顺序）
            first_handle: 可选，指定第一个块的句柄

        Returns:
            排序后的块列表
        """
        if not first_handle:
            return list(block_refs)
        return NumberingEngine._move_to_front(list(block_refs), first_handle)

    # ── 移动到头部 ────────────────────────

    @staticmethod
    def _move_to_front(
        block_list: List[Any], target_handle: str
    ) -> List[Any]:
        """将指定句柄的块移到列表头部，其余保持相对顺序

        Args:
            block_list: 块列表
            target_handle: 目标块的 Handle（COM 对象属性，字符串）

        Returns:
            调整后的列表

        Raises:
            ValueError: 目标句柄在列表中未找到
        """
        # 查找目标块
        target_idx = None
        for i, blk in enumerate(block_list):
            try:
                if blk.Handle == target_handle:
                    target_idx = i
                    break
            except AttributeError:
                continue

        if target_idx is None:
            raise ValueError(f"句柄 '{target_handle}' 对应的块不在列表中")

        # 移到头部
        target_block = block_list[target_idx]
        remaining = [b for i, b in enumerate(block_list) if i != target_idx]
        return [target_block] + remaining

    # ── 可见性读取 ────────────────────────

    @staticmethod
    def _get_visibility_state(block_ref: Any) -> Optional[str]:
        """获取块参照的所有动态块属性状态（用于区分同位置不同配置的块）

        返回所有动态块属性的拼接字符串，如 "Visibility=显示|Color=红"。
        若无动态属性或出错返回 None。
        若两个块同位置且返回不同的字符串，则视为同一仪表的不同状态→同号。
        """
        states = []
        try:
            for prop in block_ref.GetDynamicBlockProperties():
                try:
                    pn = str(prop.PropertyName)
                    pv = str(prop.Value)
                    states.append(f"{pn}={pv}")
                except Exception:
                    states.append("?")
        except Exception:
            pass
        if states:
            return "|".join(states)
        # 回退：查块属性标签
        vis_tags = {"VISIBILITY", "可见性", "VIS", "SHOW"}
        try:
            for attr in block_ref.GetAttributes():
                tag = attr.TagString.upper() if hasattr(attr, 'TagString') else ""
                if tag in vis_tags:
                    val = attr.TextString.strip() if hasattr(attr, 'TextString') else ""
                    if val:
                        return val
        except Exception:
            pass
        return None

    # ── 位置靠近聚类 ────────────────────────

    @staticmethod
    def _group_by_proximity(
        block_refs: List[Any], merge_distance: float, type_tag: str
    ) -> List[List[int]]:
        """将块按位置靠近 + 类型首字母相同聚类

        两个条件同时满足视为同一仪表：
        1. 插入点距离 ≤ merge_distance
        2. type_tag 的值首字母相同（如 PISA / PT 都首字母 P）

        Returns:
            索引组的列表，每组是 [idx1, idx2, ...]，日志输出分组信息
        """
        positions = []
        type_prefixes = []
        for blk in block_refs:
            pt = AcadConnect.get_insertion_point(blk)
            positions.append(pt)
            try:
                tv = (AcadConnect.get_attribute_value(blk, type_tag) or "").strip()
            except Exception:
                tv = ""
            type_prefixes.append(tv[:1].upper() if tv else "")

        groups: List[List[int]] = []
        assigned: set = set()
        for i in range(len(block_refs)):
            if i in assigned:
                continue
            group = [i]
            assigned.add(i)
            for j in range(i + 1, len(block_refs)):
                if j in assigned:
                    continue
                p_i, p_j = positions[i], positions[j]
                dist = ((p_i[0] - p_j[0])**2 + (p_i[1] - p_j[1])**2)**0.5
                same_prefix = (type_prefixes[i] and type_prefixes[j]
                               and type_prefixes[i] == type_prefixes[j])
                logger.info("  对比 idx %d↔%d: 距离=%.2f  前缀=[%s]↔[%s]  same_prefix=%s",
                            i, j, dist, type_prefixes[i], type_prefixes[j], same_prefix)
                # 距离 ≤ merge_distance + 0.5（留 0.5 余量防测量误差）
                if dist <= merge_distance + 0.5 and same_prefix:
                    logger.info("  ✅ 匹配成功，加入同组: idx %d↔%d 距离=%.1f 前缀=%s",
                                i, j, dist, type_prefixes[i])
                    group.append(j)
                    assigned.add(j)
            groups.append(group)
        return groups

    # ── 重叠编号映射 ──────────────────────

    @staticmethod
    def _build_overlap_number_map(
        blocks: List[Any], merge_distance: float, type_tag: str
    ) -> Optional[Dict[int, int]]:
        """为靠近的块构建编号映射

        插入点距离 ≤ merge_distance 且类型首字母相同的块视为同一仪表，编相同号。

        Returns:
            {block_index: number_position} — 同一 number_position 的块编相同号
        """
        groups = NumberingEngine._group_by_proximity(blocks, merge_distance, type_tag)
        number_map: Dict[int, int] = {}
        num_pos = 0
        for group in groups:
            if len(group) == 1:
                number_map[group[0]] = num_pos
                num_pos += 1
            else:
                handles_str = ", ".join(str(getattr(blocks[i], "Handle", "?")) for i in group)
                logger.info("发现同位置块组: [%s]", handles_str)

                # 读取可见性（日志用，不阻塞合并决策）
                vis_details = []
                for idx in group:
                    vis = NumberingEngine._get_visibility_state(blocks[idx])
                    vis_details.append(vis)
                logger.info("可见性状态: %s", vis_details)

                # 同位置即视为同一仪表的不同配置 → 相同号
                for idx in group:
                    number_map[idx] = num_pos
                num_pos += 1
                logger.info("✅ 同位置块合并编号 → %d [%s]", num_pos - 1, handles_str)
        return number_map

    # ── 向下兼容：保留旧方法名 ─────────────

    def _sort_blocks_row_first(
        self, block_refs: List[Any], y_tolerance: float
    ) -> List[Any]:
        """旧方法名 — 行优先排序

        Deprecated: 请使用 _sort_blocks(..., sort_mode="row_first", ...) 代替。
        """
        return self._sort_blocks(
            block_refs, sort_mode=self.SORT_MODE_ROW_FIRST, y_tolerance=y_tolerance
        )

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
        number_map: Optional[Dict[int, int]] = None,
        progress_cb=None,
        suffix_map: Optional[Dict[int, str]] = None,
        tag_override: Optional[Dict[int, str]] = None,
    ) -> int:
        """为排序后的块写入编号

        Args:
            blocks: 排序后的块列表
            number_tag: 编号标签名
            start_num: 起始数字
            prefix: 编号前缀
            pad_width: 补零位数（0=不补零）
            number_map: 可选，{index: number_position} 重叠块编号映射
            progress_cb: 可选进度回调，每 20 块调用一次
            suffix_map: 可选，{index: "A"} 组后缀映射
            tag_override: 可选，{index: "完整编号"} 直接使用此编号

        Returns:
            成功编号的块数
        """
        count = 0
        total = len(blocks)
        for i, blk in enumerate(blocks):
            # 如果有 tag_override 则直接使用
            if tag_override and i in tag_override:
                full_tag = tag_override[i]
                attr_ent = AcadConnect.get_attribute_entity(blk, number_tag)
                if attr_ent is not None:
                    AcadConnect.set_attribute_value(attr_ent, full_tag)
                    blk.Update()
                    count += 1
                    logger.debug("写入编号 %s (override)", full_tag)
                    if progress_cb and count % 20 == 0:
                        progress_cb()
                else:
                    logger.warning("块 %s 没有标签 %s，跳过", blk.EntityName, number_tag)
                continue

            if number_map:
                num = start_num + number_map[i]
            else:
                num = start_num + i

            # 格式化编号
            num_str = str(num)
            if pad_width > 0:
                num_str = num_str.zfill(pad_width)
            suffix = suffix_map.get(i, "") if suffix_map else ""
            full_tag = f"{prefix}{num_str}{suffix}"

            # 获取属性实体并写入
            attr_ent = AcadConnect.get_attribute_entity(blk, number_tag)
            if attr_ent is not None:
                AcadConnect.set_attribute_value(attr_ent, full_tag)
                blk.Update()  # 刷新块参照（关键！否则CAD不显示变更）
                count += 1
                logger.debug("写入编号 %s", full_tag)
                # 每 20 块保持窗口响应
                if progress_cb and count % 20 == 0:
                    progress_cb()
            else:
                logger.warning("块 %s 没有标签 %s，跳过", blk.EntityName, number_tag)

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

        sort_mode = config.get("sort_mode", self.SORT_MODE_ROW_FIRST)
        first_block_handle = config.get("first_block_handle", None)
        merge_overlap = config.get("merge_overlap", False)
        skip_sort = config.get("_skip_sort", False)

        # 过滤 + 统一排序
        filtered_blocks = []
        for blk in block_refs:
            type_val = AcadConnect.get_attribute_value(blk, type_tag)
            if type_val and type_val.strip().upper() in selected_upper:
                filtered_blocks.append(blk)

        if skip_sort:
            sorted_blocks = filtered_blocks
        else:
            sorted_blocks = self._sort_blocks(
                filtered_blocks,
                sort_mode=sort_mode,
                y_tolerance=y_tolerance,
                first_handle=first_block_handle,
            )

        # 重叠合并
        merge_distance = config.get("merge_distance", 20.0)
        number_map = None
        if merge_overlap:
            number_map = self._build_overlap_number_map(
                sorted_blocks, merge_distance=merge_distance, type_tag=type_tag,
            )

        if auto_continue:
            start_num = self._find_max_number(sorted_blocks, number_tag) + 1
        else:
            start_num = start_number

        # 生成编号，按类型分组展示
        result: Dict[str, List[Tuple[Any, str]]] = {}
        for i, blk in enumerate(sorted_blocks):
            if number_map:
                num = start_num + number_map[i]
            else:
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
        def __init__(self, name, x, y, handle=None):
            self._name = name
            self._x = x
            self._y = y
            self.EntityName = "AcDbBlockReference"
            self.Handle = handle or f"HASH_{name}"

        def __repr__(self):
            return f"{self._name}({self._x:.0f},{self._y:.0f})"

    AcadConnect.get_insertion_point = staticmethod(lambda blk: (blk._x, blk._y, 0))

    blocks = [
        MockBlock("A", 100, 200, "H_A"),
        MockBlock("B", 50, 200, "H_B"),
        MockBlock("C", 100, 150, "H_C"),
        MockBlock("D", 50, 150, "H_D"),
        MockBlock("E", 10, 180, "H_E"),
    ]

    from src.numbering import NumberingEngine
    engine = NumberingEngine.__new__(NumberingEngine)

    # ── 测试1: 行优先（默认） ──
    sorted_blocks = engine._sort_blocks(
        blocks, sort_mode=NumberingEngine.SORT_MODE_ROW_FIRST, y_tolerance=30
    )
    result = [str(b) for b in sorted_blocks]
    # 分组: Y=200(A,B)+Y=180(E) 同行(|180-200|=20≤30) → E(10), B(50), A(100)
    #       Y=150(C,D) 另一行(|150-200|=50>30) → D(50), C(100)
    expected = ["E(10,180)", "B(50,200)", "A(100,200)", "D(50,150)", "C(100,150)"]
    assert result == expected, f"行优先失败: {result} != {expected}"
    print(f"✅ 行优先: {result}")

    # ── 测试2: 蛇形行优先 ──
    sorted_blocks = engine._sort_blocks(
        blocks, sort_mode=NumberingEngine.SORT_MODE_SNAKE, y_tolerance=30
    )
    result = [str(b) for b in sorted_blocks]
    # 第1行(索引0): E(10), B(50), A(100) 正常
    # 第2行(索引1): D(50,150), C(100,150) → 反转 → C(100), D(50)
    expected_snake = ["E(10,180)", "B(50,200)", "A(100,200)", "C(100,150)", "D(50,150)"]
    assert result == expected_snake, f"蛇形失败: {result} != {expected_snake}"
    print(f"✅ 蛇形行优先: {result}")

    # ── 测试3: 按选择顺序 ──
    sorted_blocks = engine._sort_blocks(
        blocks, sort_mode=NumberingEngine.SORT_MODE_SELECTION, y_tolerance=30
    )
    result = [str(b) for b in sorted_blocks]
    assert result == ["A(100,200)", "B(50,200)", "C(100,150)", "D(50,150)", "E(10,180)"]
    print(f"✅ 按选择顺序: {result}")

    # ── 测试4: 指定首个块（行优先 + first_handle） ──
    sorted_blocks = engine._sort_blocks(
        blocks,
        sort_mode=NumberingEngine.SORT_MODE_ROW_FIRST,
        y_tolerance=30,
        first_handle="H_C",
    )
    result = [str(b) for b in sorted_blocks]
    # 行优先结果: [E, B, A, D, C]，C在末尾
    # 移动到头部 → [C, E, B, A, D]
    expected_first = ["C(100,150)", "E(10,180)", "B(50,200)", "A(100,200)", "D(50,150)"]
    assert result == expected_first, f"指定首个失败: {result} != {expected_first}"
    print(f"✅ 指定首个块(C): {result}")

    # ── 测试5: 指定首个块（选择顺序） ──
    sorted_blocks = engine._sort_blocks(
        blocks,
        sort_mode=NumberingEngine.SORT_MODE_SELECTION,
        y_tolerance=30,
        first_handle="H_D",
    )
    result = [str(b) for b in sorted_blocks]
    # D 提到最前，其余保持原顺序
    expected_sel_first = ["D(50,150)", "A(100,200)", "B(50,200)", "C(100,150)", "E(10,180)"]
    assert result == expected_sel_first, f"选择顺序+首个失败: {result} != {expected_sel_first}"
    print(f"✅ 选择顺序+指定首个(D): {result}")

    # ── 测试6: 空列表 ──
    result = engine._sort_blocks([], sort_mode=NumberingEngine.SORT_MODE_ROW_FIRST, y_tolerance=30)
    assert result == [], f"空列表失败: {result}"
    print(f"✅ 空列表: {result}")

    print("\n" + "=" * 30)
    print("🎉 全部 6 项测试通过！")
    print("=" * 30)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_sort()
