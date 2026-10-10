# VDMOS 0–60 krad 总剂量训练工程

本目录为用户授权的完整流程训练，不是教师正式题目，也不是商业器件鉴定或实测报告。目标：新建硅 N 沟道 VDMOS，获得辐照后 ID–VG、关断漏电/雪崩扫描及击穿电压随剂量的变化，整理真实求解数据、报告、文献方法和实际排障经验。

## 执行原则

- 新建独立模型，不覆盖 PN 基准、旧项目、现有用户文档或用户图形会话。
- 已采用0、10、20、30、40、50、60 krad(SiO2)；剂量介质、温度、偏置、缺陷映射与提取判据在扫描前冻结于[plan.md](plan.md)。
- TID 通过有明确出处的氧化层电荷/界面陷阱机制表达。没有工艺、辐照偏置和测量数据时，映射系数属于明确标注的训练假设，不能宣称预测真实器件的绝对抗辐照性能。
- 复用 `../../scripts/tcad.py`，单核、串行、独立 run；完整输入、TDR/PLT 和日志保存在被忽略的 `local_runtime/`。训练目录只保存源码、审核后的图表/表格与证据索引。
- 当前主会话为 `openai-codex/gpt-6.1-sol`；接口不提供子代理 slow 模型的显式指定与运行配置证明，不冒称完成切换。不使用普通 Luna worker 进行文档、电脑操作或物理建模等高难任务。
- 使用真实 Sentaurus 工具链；CLI 求解与 GUI 显示分别取证，不宣称点击 Workbench 节点完成运行。所有失败和未验证项保留。

## 完成状态与入口

七剂量主扫描与0/60端点细化共9个真实run已完成；18份电学逐点CSV、5幅电学图、0/60场图与真实桌面已核对。7项单测通过，两端点数值门槛通过；归档/CSV只读验收通过。细化单轮超过8 min计划上限，明确记录预算偏差，不能称所有计划指标均达标。

- **结果：** Vth从3.871339降至3.671610 V；电流判据BV从78.953690变为78.853823 V，基本稳定；更细端点保持约−0.200 V阈值差及约−0.102 V的很小BV差。
- **边界：** 未经实验校准的等效缺陷训练；二维半胞、单位深度，不能代表整芯片额定耐压或真实抗辐照等级；未验证Workbench Run按钮。

| 材料 | 入口 |
|---|---|
| 完整训练报告与结果分析 | [report.md](report.md) |
| 文献阅读证据与采用/不采用内容 | [literature.md](literature.md) |
| 最简建模与辐照方法 | [methods.md](methods.md) |
| 已实测执行、提取与GUI复用 | [workflow.md](workflow.md) |
| 实际麻烦、原因、处理与验证 | [lessons.md](lessons.md) |
| 冻结参数/门槛与模型代码 | [plan.md](plan.md)、[geometry.scm](model/geometry.scm)、[build_case.py](build_case.py) |
| 后处理与图形脚本 | [analyze.py](analyze.py)、[visualize.tcl](visualize.tcl)、[test_analysis.py](test_analysis.py) |
| 逐点CSV、小型汇总、全部电学图 | [data/](data/)、[scalars.csv](data/scalars.csv)、[summary.json](data/summary.json)、[resolution-check.json](data/resolution-check.json) |
| 实际原生图与桌面 | [figures/](figures/)、[desktop-final.png](figures/desktop-final.png) |
| run对应关系、哈希与验收边界 | [run-index.json](run-index.json)、[result.json](result.json) |

原始输入、完整log/PLT/TDR与第三方PDF留在被忽略的`local_runtime/`，没有上传受限工具手册、许可证或密钥。复现优先按workflow调用唯一runner，不另写并行求解器、不覆盖基准。

