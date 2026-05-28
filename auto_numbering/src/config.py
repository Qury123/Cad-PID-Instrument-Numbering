#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置持久化

使用 JSON 文件保存/加载上次使用的配置：
- 上次选择的仪表类型标签名
- 上次选择的编号标签名
- 上次选择的仪表类型列表
- 上次的编号配置参数

配置文件保存在插件目录下的 config.json。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 配置文件路径 ──────────────────────
# 保存在插件所在目录（即当前工作目录）
CONFIG_FILE = "config.json"

# 默认配置
DEFAULT_CONFIG: Dict[str, Any] = {
    "last_type_tag": "",
    "last_number_tag": "",
    "last_selected_types": [],
    "last_number_config": {
        "prefix": "",
        "start_number": 1,
        "pad_width": 3,
        "y_tolerance": 50.0,
        "auto_continue": True,
    },
}


class ConfigManager:
    """配置管理器

    用法:
        cfg = ConfigManager()
        cfg.load()           # 加载配置
        cfg.save(data)       # 保存配置
        cfg.reset()          # 重置为默认
    """

    def __init__(self, file_path: str = CONFIG_FILE) -> None:
        self.file_path = file_path

    # ── 加载 ──────────────────────────────

    def load(self) -> Dict[str, Any]:
        """加载配置文件，不存在则返回默认配置"""
        if not os.path.exists(self.file_path):
            logger.info("配置文件 %s 不存在，使用默认配置", self.file_path)
            return dict(DEFAULT_CONFIG)

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 确保所有 key 都存在（合并默认值）
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)

            # 确保嵌套字典也有默认值
            if "last_number_config" in data:
                num_cfg = dict(DEFAULT_CONFIG["last_number_config"])
                num_cfg.update(data["last_number_config"])
                merged["last_number_config"] = num_cfg

            logger.info("已从 %s 加载配置", self.file_path)
            return merged

        except (json.JSONDecodeError, IOError) as exc:
            logger.warning("配置文件读取失败 %s: %s，使用默认配置", self.file_path, exc)
            return dict(DEFAULT_CONFIG)

    # ── 保存 ──────────────────────────────

    def save(self, data: Dict[str, Any]) -> bool:
        """保存配置到 JSON 文件

        Args:
            data: 配置字典

        Returns:
            是否保存成功
        """
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("配置已保存到 %s", self.file_path)
            return True
        except (IOError, TypeError) as exc:
            logger.error("保存配置失败: %s", exc)
            return False

    # ── 重置 ──────────────────────────────

    def reset(self) -> bool:
        """重置配置为默认并保存"""
        return self.save(dict(DEFAULT_CONFIG))

    # ── 便捷读取 ──────────────────────────

    def get_last_tags(self) -> tuple[str, str]:
        """获取上次的标签选择"""
        data = self.load()
        return (
            data.get("last_type_tag", ""),
            data.get("last_number_tag", ""),
        )

    def get_last_types(self) -> List[str]:
        """获取上次选中的仪表类型列表"""
        data = self.load()
        return data.get("last_selected_types", [])

    def get_last_number_config(self) -> Dict[str, Any]:
        """获取上次的编号配置"""
        data = self.load()
        return data.get("last_number_config", dict(DEFAULT_CONFIG["last_number_config"]))

    def save_tags(self, type_tag: str, number_tag: str) -> bool:
        """保存标签选择（增量保存）"""
        data = self.load()
        data["last_type_tag"] = type_tag
        data["last_number_tag"] = number_tag
        return self.save(data)

    def save_types(self, selected_types: List[str]) -> bool:
        """保存选中的类型（增量保存）"""
        data = self.load()
        data["last_selected_types"] = selected_types
        return self.save(data)

    def save_number_config(self, config: Dict[str, Any]) -> bool:
        """保存编号配置（增量保存）"""
        data = self.load()
        data["last_number_config"] = config
        return self.save(data)


# ── 快速测试 ──────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    cfg = ConfigManager("test_config.json")
    print("✅ 配置管理器已初始化")

    # 测试保存
    test_data = {
        "last_type_tag": "SIGNAL",
        "last_number_tag": "TAG",
        "last_selected_types": ["PT", "TE", "TT"],
        "last_number_config": {
            "prefix": "PT-",
            "start_number": 1,
            "pad_width": 3,
            "y_tolerance": 50.0,
            "auto_continue": False,
        },
    }
    ok = cfg.save(test_data)
    print(f"✅ 保存: {'成功' if ok else '失败'}")

    # 测试加载
    loaded = cfg.load()
    print(f"✅ 加载: type_tag={loaded['last_type_tag']}, types={loaded['last_selected_types']}")

    # 测试便捷方法
    type_tag, num_tag = cfg.get_last_tags()
    print(f"✅ 便捷读取: 类型标签={type_tag}, 编号标签={num_tag}")

    types = cfg.get_last_types()
    print(f"✅ 便捷读取: 选中类型={types}")

    num_cfg = cfg.get_last_number_config()
    print(f"✅ 便捷读取: 编号前缀={num_cfg['prefix']}")

    # 清理测试文件
    import os
    os.remove("test_config.json")
    print("✅ Step 8 全部正确")
