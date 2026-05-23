# 仪表自动编号插件 - 开发技能

## 项目概况

Python AutoCAD 插件，对选中仪表块自动编号，不同类型独立编号。
通过 COM 桥接（pyautocad + pywin32）与 AutoCAD 2014+ 通信，
tkinter 提供可视化对话框。

## 开发流程

1. 每步先实现模块功能
2. 运行测试/验证脚本确认可用
3. `git add . && git commit -m "step-N: 描述"`
4. 让用户验证通过后进入下一步

## 关键技术点

- **COM 连接**: `win32com.client.Dispatch("AutoCAD.Application")`
- **块属性**: 遍历 INSERT 实体的 ATTRIB 子实体，提取 Tag 和 Value
- **属性写入**: 修改 ATTRIB 实体的 DXF 组码 1，调用 Update()
- **选择集**: `doc.SelectionSets.Add("SS")` → `ss.SelectOnScreen()`
- **行优先排序**: Y 坐标差 ≤ 容差视为同行，按 X 从左到右
- **独立编号**: 按仪表类型分组，每组各自从起始号开始

## 需求要点

- 用户框选 → 识别所有属性标签
- 下拉框选「仪表类型标签」和「编号标签」
- 复选框多选需要编号的类型值
- 对话框配置编号样式（前缀、起始号、补零、Y容差）
- 每种类型各自独立编号序列
- JSON 记忆配置

## 参考

LSP 版本位于项目根目录 `自动仪表编号V5.0.3.lsp`
