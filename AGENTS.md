---
description: 
alwaysApply: true
---

# 专利建模项目规则（FreeCAD MCP 使用纪律）

本项目所有 FreeCAD 建模、装配、姿态验证、图纸导出均通过本机 FreeCAD MCP 执行。完整调用纪律见 `.cursor/skills/freecad-mcp/SKILL.md`（全局 skill，必须遵守）。以下为本项目高频约束。

## 启动与连接

1. FreeCAD 启动时若自动打开大装配（V9 全尺寸约 289 对象），**等待加载完成再发建模请求**：启动后先探测（`ping` 秒回但 `execute_code` 超时 = GUI 仍在忙，等 10~20 秒再试）。
2. 禁止连续重试同一个超时请求——XML-RPC 是单线程，重试只会堆积排队并连环阻塞；确认无写入后重启 FreeCAD（RPC 自动恢复），先跑空探针（`print(App.Version())`）再继续。
3. 版本由统一启动器 `C:/Users/Administrator/AppData/Local/FreeCADMCP/Start-FreeCADMCP.ps1` 管理，禁止手工 `uvx` / `uv tool install` / 本地源码运行。

## 调用纪律

4. 一次只做一个动作：绝不把「复制零件 + 重型布尔 + 导出 + 截图」合并进同一次 `execute_code`。重型 OCCT 操作（布尔/放样/整机重算）用 `execute_code_async`（后台线程，不占 GUI）。
5. 中文文档名不直接传参给 `get_objects` / `get_object`（XML-RPC 编码损坏 → 空数组或 `Unknown document`）。用 `execute_code` 内 `App.listDocuments()` / `App.getDocument(<name>)` 处理。
6. 保存后必须验证（`list_documents` / 查文件存在）再进入下一步；超时后先确认无写入再重来。
7. 截图按需开启（`include_screenshot` / `view_name`），纯查询分析不开截图。

## 文件位置

- 建模参数与提示词：`建模工程/参考资料/`（00_README 索引、04_AI建模提示词）
- 模型：`建模工程/模型/V*_*/`
- 版本归档：`建模工程/版本归档/`
- 建模记录：`建模工程/建模记录/`
- 设计规格与执行规格书：`docs/2026-08-03-陇盾MDS-1通用形变监测站设计/`

## Python 环境（重要）

本项目使用项目内虚拟环境，禁止使用全局 Python（机器上有 C:\Python314、Anaconda 等多个全局解释器，多个 Cursor 实例并行工作时共用全局环境会互相冲突）。

- 运行脚本一律使用：`.venv\Scripts\python.exe <script>`（不要裸用 `python` / `py`）
- 安装依赖一律使用：`.venv\Scripts\python.exe -m pip install ...`，禁止向全局 Python 安装任何包
- 若 `.venv` 不存在，先执行 `py -m venv .venv`，再 `.venv\Scripts\python.exe -m pip install -r requirements.txt`
- 新增依赖时同步更新 `requirements.txt`
- 所有脚本从项目根目录运行；不要弹出黑窗格（新控制台窗口），一律在后台静默执行
