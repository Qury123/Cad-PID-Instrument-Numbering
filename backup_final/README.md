# 仪表自动编号插件 - AutoCAD Python 插件

## 概述

对选中的 AutoCAD 仪表块自动编号，**不同类型仪表相互独立编号**。
例如：PT 类型仪表编为 PT-001, PT-002… TE 类型编为 TE-001, TE-002…

## 功能特性

- ✅ 可视化对话框操作（tkinter），告别命令行
- ✅ 框选区域后自动识别所有属性标签
- ✅ 用户选择「仪表类型」标签和「编号」标签
- ✅ 多选需要编号的仪表类型（复选框）
- ✅ 可配置编号样式：前缀、起始号、补零位数
- ✅ 不同类型仪表各自独立编号
- ✅ 行优先排序（Y 容差可调）
- ✅ 记忆上次配置，下次自动加载

## 环境要求

- **操作系统**：Windows（AutoCAD 仅支持 Windows）
- **AutoCAD**：2014 或更高版本（正在运行）
- **Python**：3.8 或更高版本

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

1. 打开 AutoCAD 和含仪表属性块的图纸
2. 在终端运行：
   ```bash
   python run.py
   ```
3. 按对话框引导操作

## 项目结构

```
├── run.py                  # 启动入口
├── requirements.txt        # 依赖清单
├── README.md               # 本文件
├── .gitignore
├── src/
│   ├── acad_com.py         # AutoCAD COM 连接层
│   ├── block_analyzer.py   # 块属性分析器
│   ├── config.py           # 配置持久化
│   ├── numbering.py        # 编号逻辑 + 排序
│   └── ui/
│       ├── tag_selector.py    # 标签选择对话框
│       ├── code_selector.py   # 代号多选对话框
│       └── number_config.py   # 编号配置对话框
└── skills/
    └── SKILL.md            # 开发技能文件
```

## 参考

本插件逻辑参考了 LSP 版本 `自动仪表编号V5.0.3.lsp`，但在以下方面做了改进：

| 方面 | LSP 版本 | Python 版本 |
|------|----------|-------------|
| 界面 | 纯命令行 | 可视化对话框 |
| 编号方式 | 所有类型混排 | 每种类型独立编号 |
| 类型选择 | 输入序号逗号分隔 | 复选框多选 |
| 配置存储 | 自定义 INI 解析 | 标准 JSON |
| 错误处理 | quit 崩溃 | try/except 优雅处理 |
