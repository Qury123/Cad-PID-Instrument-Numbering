# 仪表自动编号插件

> 基于 AutoCAD COM 的仪表块自动编号工具  
> 版本 **1.2.0** | [更新日志](auto_numbering/CHANGELOG.md) | [用户手册](auto_numbering/USAGE.md)

---

## 快速开始

```bash
cd auto_numbering
python run.py
```

或直接双击 `auto_numbering/releases/v1.2.0/仪表自动编号_v1.2.0.exe`

详细操作见 **[用户操作手册 →](auto_numbering/USAGE.md)**

---

## 目录结构

```
├── auto_numbering/           # 仪表自动编号插件
│   ├── src/                  # 源代码
│   ├── scripts/              # 构建脚本
│   ├── releases/             # 已编译 EXE（按版本）
│   ├── USAGE.md              # 用户操作手册
│   └── CHANGELOG.md          # 更新日志
├── archive/                  # 历史版本归档（LSP → Python 迁移备份）
└── README.md                 # 本文件
```

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11 |
| AutoCAD | 2014+（必须正在运行） |
| Python | 3.8+ |

## 许可

MIT License
