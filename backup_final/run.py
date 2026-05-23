#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
仪表自动编号插件 — 启动入口

完整工作流程：
  1. 连接 AutoCAD → 用户框选带属性块
  2. 分析所有属性标签 → 选「仪表类型」标签和「编号」标签
  3. 列出所有仪表类型值 → 多选需要编号的类型
  4. 配置编号样式（前缀、起始号、补零位数）
  5. 每种类型独立编号 → 写入 AutoCAD

使用方法：
  python run.py

要求：
  - Windows 系统
  - AutoCAD 2014+ 正在运行
  - 打开含仪表属性块的图纸
"""

import logging
import sys
import tkinter.messagebox as mb
import traceback

# ── 导入各模块 ──────────────────────────
from src.acad_com import AcadConnect, AcadConnectError
from src.block_analyzer import BlockAnalyzer
from src.numbering import NumberingEngine
from src.config import ConfigManager

from src.ui.tag_selector import TagSelectorDialog
from src.ui.code_selector import CodeSelectorDialog
from src.ui.number_config import NumberConfigDialog

# ── 日志 ────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """主流程"""
    print("=" * 50)
    print("  仪表自动编号插件 v1.0")
    print("=" * 50)

    # ── 加载记忆配置 ──
    config_mgr = ConfigManager()
    memory = config_mgr.load()

    # ── Step 1: 连接 AutoCAD ──
    print("\n🔌 正在连接 AutoCAD...")
    try:
        acad = AcadConnect()
    except AcadConnectError as e:
        mb.showerror("连接失败", str(e))
        print(f"❌ {e}")
        sys.exit(1)
    print(f"✅ 已连接到: {acad.get_document_name()}")

    # ── Step 2: 用户框选块 ──
    print("\n📦 请在 AutoCAD 中框选要编号的仪表块...")
    analyzer = BlockAnalyzer(acad)
    try:
        blocks = analyzer.select_blocks(
            prompt_text="\n请框选要编号的仪表块（右键结束选择）..."
        )
    except AcadConnectError as e:
        mb.showerror("选择出错", f"选择操作失败:\n{e}")
        print(f"❌ {e}")
        sys.exit(1)

    if not blocks:
        mb.showwarning("提示", "未选中任何带属性的块。")
        print("❌ 未选中任何块")
        sys.exit(1)

    print(f"✅ 选中 {len(blocks)} 个带属性块")

    # ── Step 3: 分析属性标签 ──
    print("\n🏷️  正在分析属性标签...")
    all_tags = analyzer.get_all_tags(blocks)
    if not all_tags:
        mb.showerror("错误", "选中的块没有可读的属性标签。")
        print("❌ 无属性标签")
        sys.exit(1)

    # 构建标签名 → 示例值的映射（用于对话框预览）
    tags_with_samples = {}
    for tag in all_tags:
        samples = analyzer.get_tag_sample_values(blocks, tag, max_samples=5)
        tags_with_samples[tag] = samples

    print(f"   发现 {len(all_tags)} 个属性标签")

    # ── Step 4: 标签选择对话框 ──
    print("\n🗔 弹出标签选择对话框...")
    last_type_tag, last_number_tag = memory.get("last_type_tag", ""), memory.get(
        "last_number_tag", ""
    )
    tag_dialog = TagSelectorDialog(
        tags_with_samples=tags_with_samples,
        last_type_tag=last_type_tag or None,
        last_number_tag=last_number_tag or None,
    )
    tag_result = tag_dialog.show()

    if tag_result is None:
        print("❌ 用户取消操作")
        sys.exit(0)

    type_tag, number_tag = tag_result
    print(f"✅ 已选择: 类型标签=【{type_tag}】, 编号标签=【{number_tag}】")

    # 保存标签选择到记忆
    config_mgr.save_tags(type_tag, number_tag)

    # ── Step 5: 获取唯一类型值 ──
    print(f"\n📋 正在提取标签「{type_tag}」的所有类型值...")
    unique_values = analyzer.get_unique_values(blocks, type_tag)
    if not unique_values:
        mb.showwarning(
            "提示", f"标签「{type_tag}」在所有选中块中都没有非空值。"
        )
        print("❌ 无类型值")
        sys.exit(1)

    # 获取每种类型的出现次数
    type_counts = {}
    for blk in blocks:
        val = AcadConnect.get_attribute_value(blk, type_tag)
        if val and val.strip():
            type_counts[val.strip()] = type_counts.get(val.strip(), 0) + 1

    print(f"   共 {len(unique_values)} 种类型: {', '.join(unique_values[:10])}")

    # ── Step 6: 类型多选对话框 ──
    print("\n🗔 弹出类型选择对话框...")
    last_types = memory.get("last_selected_types", [])
    code_dialog = CodeSelectorDialog(
        type_tag=type_tag,
        all_codes=type_counts,
        last_selected=last_types,
    )
    selected_types = code_dialog.show()

    if selected_types is None:
        print("❌ 用户取消操作")
        sys.exit(0)

    print(f"✅ 选择了 {len(selected_types)} 种类型: {', '.join(selected_types)}")
    config_mgr.save_types(selected_types)

    # ── Step 7: 编号配置对话框 ──
    print("\n🗔 弹出编号配置对话框...")
    last_num_config = memory.get("last_number_config", {})
    config_dialog = NumberConfigDialog(
        selected_types=selected_types,
        last_config=last_num_config,
    )
    number_config = config_dialog.show()

    if number_config is None:
        print("❌ 用户取消操作")
        sys.exit(0)

    print(
        f"✅ 编号配置: 前缀=「{number_config['prefix']}」"
        f" 起始={number_config['start_number']}"
        f" 补零={number_config['pad_width']}"
        f" 容差={number_config['y_tolerance']}"
        f" 自动顺延={'是' if number_config['auto_continue'] else '否'}"
    )
    config_mgr.save_number_config(number_config)

    # ── Step 8: 执行编号 ──
    print("\n✏️  正在编号...")
    engine = NumberingEngine(acad)
    try:
        results = engine.number_instruments(
            block_refs=blocks,
            type_tag=type_tag,
            number_tag=number_tag,
            selected_types=selected_types,
            config=number_config,
        )
    except ValueError as e:
        mb.showerror("编号错误", str(e))
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        mb.showerror("编号错误", f"写入编号时发生错误:\n{e}")
        logger.error(traceback.format_exc())
        print(f"❌ 写入错误: {e}")
        sys.exit(1)

    # ── 完成 ──
    total = sum(results.values())
    print(f"\n🎉 编号完成！")
    for type_name, count in sorted(results.items()):
        print(f"   {type_name}: {count} 个块")
    print(f"   共计: {total} 个块")

    # 在 AutoCAD 命令行输出结果
    acad.prompt(
        f"\n✅ 仪表编号完成！共 {total} 个块，"
        + " ".join(f"{k}={v}" for k, v in sorted(results.items()))
    )

    mb.showinfo(
        "编号完成",
        f"✅ 成功编号 {total} 个仪表块！\n\n"
        + "\n".join(f"  {t}: {c} 个" for t, c in sorted(results.items())),
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(traceback.format_exc())
        mb.showerror("意外错误", f"程序发生意外错误:\n{e}")
        print(f"❌ 程序崩溃: {e}")
        sys.exit(1)
