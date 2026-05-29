# CAD 插件工具集

> AutoCAD 辅助工具集合，基于 COM 自动化。

---

## 插件列表

| 插件 | 目录 | 说明 |
|------|------|------|
| 🔢 **仪表自动编号** | [`auto_numbering/`](auto_numbering/) | 框选仪表块，自动按行优先顺序编号，支持手动调序、同位置合并 |
| 🎨 **批量修改块属性文字颜色** | [`batch_attr_color/`](batch_attr_color/) | 框选块 → 选属性标签 → 选颜色 → 批量修改文字颜色 |

---

## 快速使用

```bash
# 仪表自动编号
cd auto_numbering
python run.py

# 批量改色
cd batch_attr_color
python run.py
```

每个插件目录下均有独立的 `README.md`、`USAGE.md` 和 `CHANGELOG.md`。

---

## 目录结构

```
├── auto_numbering/           # 仪表自动编号插件
│   ├── src/                  # 源代码
│   ├── scripts/              # 构建脚本
│   ├── releases/             # 已编译 EXE（按版本）
│   ├── USAGE.md              # 用户操作手册
│   └── CHANGELOG.md          # 更新日志
├── batch_attr_color/         # 批量改色插件
│   ├── src/
│   └── ...
├── archive/                  # 历史版本归档（LSP → Python 迁移备份）
│   ├── lsp_original/         # 原始 AutoLISP 版本
│   ├── step2/ / step3/       # Python 迁移中间版
│   └── backup_final/         # 最终完整备份
└── skills/                   # Reasonix 技能文件（工具用，可忽略）
```

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11 |
| AutoCAD | 2014+（必须正在运行） |
| Python | 3.8+ |

> 每个插件子目录有独立的 `requirements.txt`。

## 许可

MIT License
