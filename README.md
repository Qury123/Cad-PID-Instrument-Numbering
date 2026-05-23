# 仪表自动编号插件

> 基于 AutoCAD COM 的仪表块自动编号工具  
> 版本 **1.0.0** | [更新日志](CHANGELOG.md) | [用户手册](USAGE.md) | [GitHub](https://github.com/Qury123/Cad-PID-Instrument-Numbering)

---

## 快速开始

```bash
# 方式一：直接双击 EXE
releases\v1.0.0\仪表自动编号_v1.0.0.exe

# 方式二：Python 源码
pip install -r requirements.txt
python run.py
```

详细操作见 **[用户操作手册 →](USAGE.md)**

---

## 功能概要

| 功能 | 说明 |
|------|------|
| 框选块 | 在 AutoCAD 中框选，自动过滤带属性块 |
| 读取当前选择 | 先手动在 CAD 选中，插件直接读取 |
| 标签识别 | 自动列出所有属性标签，选择类型和编号字段 |
| 类型过滤 | 按字母序排列，复选框多选 |
| 自动顺延 | 从已有编号最大值+1 开始 |
| 行优先排序 | Y 容差同行，按 X 从左到右 |
| 配置记忆 | 上次的选择和参数自动保存 |

## 项目结构

```
├── src/                       # 源代码
│   ├── acad_com.py            # AutoCAD COM 连接层
│   ├── block_analyzer.py      # 块属性分析器
│   ├── numbering.py           # 编号逻辑 + 行优先排序
│   ├── config.py              # 配置持久化
│   ├── version.py             # 版本号读取
│   └── ui/
│       └── main_window.py     # 主窗口（5 步向导）
├── scripts/
│   ├── build.bat              # 一键打包 EXE
│   └── git_here.bat           # Git 快捷命令
├── config/
│   └── version_info.txt       # EXE 版本属性
├── releases/                  # 发布 EXE（按版本归档）
├── VERSION                    # 版本号
├── pyproject.toml             # 项目元数据
├── CHANGELOG.md               # 更新日志
├── USAGE.md                   # 用户操作手册
└── README.md                  # 本文件
```

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11 |
| AutoCAD | 2014+（必须正在运行） |
| Python | 3.8+（仅源码方式需要） |

## 构建

```bash
scripts\build.bat
```

输出归档到 `releases\vX.X.X\`。

## 许可

MIT License
