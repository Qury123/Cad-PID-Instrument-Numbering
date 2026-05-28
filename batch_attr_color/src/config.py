#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置持久化

使用 JSON 文件保存/加载上次使用的配置：
- 上次选择的属性标签名
- 上次选择的颜色索引
- 用户偏好设置

配置文件保存在插件目录下的 config.json。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── 配置文件路径 ──────────────────────
CONFIG_FILE = "config.json"

# 默认配置
DEFAULT_CONFIG: Dict[str, Any] = {
    "last_tag": "",
    "last_color_index": 3,        # 默认绿色
    "last_color_mode": "aci",     # "aci" | "true_color"
    "last_rgb": [255, 0, 0],      # 默认红色
    "color_non_empty_only": True, # 仅修改非空值
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

    def get_last_tag(self) -> str:
        """获取上次选择的属性标签"""
        data = self.load()
        return data.get("last_tag", "")

    def get_last_color_info(self) -> Tuple[str, int, List[int]]:
        """获取上次的颜色设置

        Returns:
            (color_mode, aci_index, [r, g, b])
        """
        data = self.load()
        return (
            data.get("last_color_mode", "aci"),
            data.get("last_color_index", 3),
            data.get("last_rgb", [255, 0, 0]),
        )

    def save_tag(self, tag_name: str) -> bool:
        """保存标签选择（增量保存）"""
        data = self.load()
        data["last_tag"] = tag_name
        return self.save(data)

    def save_color(self, color_mode: str, aci_index: int, rgb: List[int]) -> bool:
        """保存颜色设置（增量保存）"""
        data = self.load()
        data["last_color_mode"] = color_mode
        data["last_color_index"] = aci_index
        data["last_rgb"] = rgb
        return self.save(data)

    def save_options(self, non_empty_only: bool) -> bool:
        """保存选项设置"""
        data = self.load()
        data["color_non_empty_only"] = non_empty_only
        return self.save(data)


# ── 快速测试 ──────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    cfg = ConfigManager("test_config.json")
    print("✅ 配置管理器已初始化")

    # 测试保存
    test_data = {
        "last_tag": "SIGNAL",
        "last_color_index": 1,
        "last_color_mode": "aci",
        "last_rgb": [255, 0, 0],
        "color_non_empty_only": True,
    }
    ok = cfg.save(test_data)
    print(f"✅ 保存: {'成功' if ok else '失败'}")

    # 测试加载
    loaded = cfg.load()
    print(f"✅ 加载: tag={loaded['last_tag']}, color={loaded['last_color_index']}")

    # 测试便捷方法
    tag = cfg.get_last_tag()
    mode, aci, rgb = cfg.get_last_color_info()
    print(f"✅ 便捷读取: tag={tag}, mode={mode}, ACI={aci}, RGB={rgb}")

    # 清理测试文件
    import os
    os.remove("test_config.json")
    print("✅ 全部测试通过")
