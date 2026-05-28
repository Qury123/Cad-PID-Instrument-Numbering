# 批量修改块属性文字颜色插件

> 基于 AutoCAD COM 的批量修改块属性文字颜色工具  
> 版本 **1.0.0**

---

## 功能

在 AutoCAD 中批量修改选中块中**指定属性标签的文字颜色**。

| 功能 | 说明 |
|------|------|
| 框选块 | 在 AutoCAD 中框选，自动过滤带属性块 |
| 读取当前选择 | 先手动在 CAD 选中，插件直接读取 |
| 标签识别 | 自动列出所有属性标签，选择要改色的目标标签 |
| 颜色选择 | 预设色板（20 种常用色）+ RGB 自定义输入 |
| 颜色模式 | ACI 颜色索引 / 真彩色 RGB / ByLayer / ByBlock |
| 仅改非空值 | 可选：仅修改有内容的属性文字 |
| 配置记忆 | 上次的选择和参数自动保存到 config.json |

## 使用方法

```bash
pip install -r requirements.txt
python run.py
```

或直接双击 `run.bat`。

### 操作步骤

1. **连接 AutoCAD** — 插件自动连接正在运行的 AutoCAD
2. **选择块** — 框选 / 读取当前选中
3. **选择属性标签** — 下拉选择要改颜色的属性标签
4. **选择颜色** — 点击色板预设颜色，或输入 RGB 自定义
5. **执行修改** — 一键批量写入

## 项目结构

```
batch_attr_color/
├── run.py              # 启动入口
├── run.bat             # 一键启动
├── README.md           # 本文件
├── requirements.txt    # 依赖
├── config.json         # 配置缓存（自动生成）
├── plugin.log          # 运行日志（自动生成）
└── src/
    ├── __init__.py     # 包说明
    ├── acad_com.py     # AutoCAD COM 连接层 + 颜色操作
    ├── config.py       # 配置持久化
    └── main_window.py  # 主窗口（4 步向导）
```

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11 |
| AutoCAD | 2014+（必须正在运行） |
| Python | 3.8+ |

## 依赖

- `pyautocad` — AutoCAD COM 操作封装
- `pywin32` — Windows COM 接口

## 许可

MIT License
