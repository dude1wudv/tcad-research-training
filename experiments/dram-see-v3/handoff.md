# DRAM SEE v3 执行交接与新对话提示词

## 1. 本轮交付及状态

- 保存时间基准：`2026-10-10T09:33:33.4405536Z`（保存前核查时间）。
- 来源对话：`01a1239b-5c49-7f32-9e60-fd0d19097d14`。
- 项目根目录：`E:\TCAD-Workspace\tcad-research-training`。
- 保存前分支：`main`；HEAD：`c072df8a4fedc51906be770c9fd5b8290c1ff01c`。
- 保存前 Git 状态有 ` D README.txt`，这是本轮开始前已有的改动，未恢复、覆盖或提交。开始执行时重新读取状态，不依赖本快照。
- 本轮仅新增 [plan.md](plan.md) 与本文。没有新增 v3 源码、输入 deck、机器可读冻结设计、队列或运行编号；没有启动仿真，没有提交或推送 Git。
- 本轮没有重新连接 VM 检查进程。上一轮只读核查无 SDevice/SDE/snmesh/transport 进程和未结 manifest，存在已有 SVisual 窗口；不能把上一轮快照当作当前状态。
- 本对话不再调度新版实验。新对话在实时核查后担任唯一求解调度者；文档/代码可按仓库约定分工，求解器仍串行。

用户要求在新对话执行。本文件只是交接说明，不是运行器状态文件，不要向旧 ledger 填写尚未发生的运行。

## 2. 阅读与接管顺序

1. 项目根目录 `AGENTS.md`、[协作规范](../../design-notes/agent-workflow.md)、[运行规范](../../design-notes/workflow.md)。
2. [本次定稿计划](plan.md)、[总实验计划](../plan.md)、[总路线](../roadmap.md)、[课程大纲](../../docs/course-project-syllabus.md)、[报告提纲](../../reports/outline.md)。总路线和报告提纲含早期状态，需要执行阶段更新，不能据此重跑旧实验。
3. [v2 README](../dram-see-v2/README.md)、[v2 报告](../dram-see-v2/report.md)、[v2 工作流](../dram-see-v2/workflow.md)、[v2 冻结设计](../dram-see-v2/stats-design.json)、[v2 交付索引](../dram-see-v2/data/summary/delivery-index.json)。
4. [D1 README](../dram-readout-offset-d1/README.md)、[D1 解释](../dram-readout-offset-d1/interpretation.md)、[D1 工作流](../dram-readout-offset-d1/workflow.md)、[D1 最新日志](../dram-readout-offset-d1/journal.md)、[D1 有效设计](../dram-readout-offset-d1/design-r4.json)、[D1 交付索引](../dram-readout-offset-d1/delivery-index.json)。
5. 实时读取 `local_runtime/dram-see-v2/ledger.json`、`local_runtime/dram-readout-offset-d1/ledger.json`、`local_runtime/dram-readout-offset-d1/session-state.json`、`local_runtime/runs/<run-id>/manifest.json`；核对本地控制器、VM 进程、输出与队列。没有确认结束的运行不重发。

两阶段状态必须分开：输入/设计冻结是待执行条件；`COLLECTED` 只表示工程收集，物理与数值审计通过后才可标记有效。旧程序可能会写回旧目录，复用前检查副作用；不直接运行旧的 freeze、batch、remaining、report 命令来启动 v3。

## 3. 可复用证据与关键限制

### 历史完成情况

- v1 已有四尺寸×两粒子×两方向的 16 工况及旧定义下的拟合/外推验证；初态并非新版统一 0.1/0.9 V，因此不能并入新版响应统计。
- v2 已有八个无粒子基准、焦点尺寸 0.25 µm 的八个独立粒子事件及 16 个配对响应。5 mV 判据下 alpha 存储1为 1 正确、3 临界、0 明确误读；历史分类保留。
- D1 已完成 9 个确定性诊断工况，另保留 1 次解析失败；新增独立粒子事件数为 0。物理参考与离线参考仅在一个尺寸、一个无粒子信号状态验证过，不能写成全矩阵已验证。
- D1 最后工况曾中断本地主控连接，远端原 run 正常完成后收集恢复；原执行 SSH 状态未知，恢复收集 SSH 和远端退出均为 0。r4 是特定 run 的证据例外，不得自动推广成新实验失败或日志缺失的通用豁免。

### 保存前实际核对的哈希

| 文件（相对项目根目录） | SHA-256 |
|---|---|
| `experiments/dram-see-v2/stats-design.json` | `f85653a58316c6d43858898ecb9976ec6b42bcb3e88da45cfa302d941f263170` |
| `experiments/dram-see-v2/data/summary/delivery-index.json` | `9a3566a1b31da1ee7094461b4a133b4b5ea943431c8f687e5188961af75f0a75` |
| `experiments/dram-readout-offset-d1/design-r4.json` | `810a08d08e872887d822a50e983a7a7021ed883aa3f5af69176c676e5d13cf87` |
| `experiments/dram-readout-offset-d1/delivery-index.json` | `8618ed05ee8033f394c374116654660c1dae6f9f0d60a6bdf82a6abfb7e02ff6` |

上述仅为本轮核对的四份入口文件哈希，不代表本轮重新审计了全部原始归档。开始执行时建立包含 v1/v2/D1 及所复用归档的保全快照，并验证实际依赖。

### 实现前已经发现的约束

- v2 的角度在 `transport.py`、`event_audit.py`、`build_case.py` 多处写死为 0°；不能只改变一个 CLI 参数。v1 的 Geant4 源码和事件契约已有 30° 方向与边界处理，可复用。
- 坐标约定为 `direction=(-sinθ, cosθ, 0)`；表面入射点 `x=L+0.45 µm`；真空发射点需补偿 0.001 µm 的入射偏移。非零角径迹长为 `min(1.2/cosθ, (L+0.45)/sinθ)`，0° 单独取 1.2 µm。0.18 µm/30° 从左侧退出，0.25 µm/30° 靠近左下角，必须审计源截断积分。
- D1 的 `Cell access` 与 `Cell refcell` 共用同一 Device。直接将粒子源加到共用定义会照射两个器件；新版必须分离类型，只在信号定义内注入，同时验证参考零源。
- 物理双支路不得直接加载旧单支路 `.sav`；旧父状态缺参考器件状态。输入、模型与参考匹配键要包含尺寸、氧化层厚度、网格、步长、时序和电容。
- Geant4 当前模型为硅与真空，未含栅氧；TCAD 的 5 nm 栅氧不意味着两端完整材料栈一致。4/5/6 nm 检查固定硅入口事件，TCAD 同步修改氧化层边界、栅接触定位、网格窗口及氧化层分辨率；每个新厚度使用自己的基准和参考。
- 主矩阵的 0/1 都保留初始位定义。`ΔQ=Cstore×(SN事件−SN对照)` 保留符号，不把所有电压下降统称误读；`ΔM=M对照−M事件` 正值表示裕量下降。
- 离线参考必须使用相同参数的完整中性参考曲线。不能直接沿用旧 summary 的裕量/分类，不能统一减掉 12 mV，也不能用标量 SN 接近代替载流子历史相同。
- 原始粒子工况每响应约 395–515 s，平均 alpha 434.10 s、proton 416.04 s；D1 单器件约 340–380 s，双器件一次为 716.69 s。这是预算依据，不是 v3 实测成本。24 小时为本次新版累计求解预算，包含新增诊断、数值检查、扩展和失败开销，不等于日历完成承诺。

冻结前还须把定稿中的统计区间算法、数值验证点的距离排序/并列规则、交叉验证评分及实现细节写入机器可读设计，并完成相应契约检查；这些细化不得改变已定的指标、阈值、事件清单、数据划分和预算，也不得使用未来测试响应做选择。

## 4. 新对话可复制提示词

```text
请接续 E:\TCAD-Workspace\tcad-research-training 的 DRAM 单粒子效应项目，执行已保存的定稿，不要从零重建。

先完整读取：
1. experiments/dram-see-v3/plan.md
2. experiments/dram-see-v3/handoff.md
以及 AGENTS.md 和交接文档指定的操作规范、最新日志、设计与运行索引。

这两份文件目前仅为计划和交接，v3 尚未实现或启动。先核实项目路径、Git 分支和改动、本地控制器、VM 求解进程、队列与输出，确认唯一调度者。保留现有用户改动；不要恢复交接时已存在的 README.txt 删除改动。状态不明先只读核查，不重复提交，不终止正常求解。

按定稿顺序执行：先落实并冻结评价指标、参考支路和事件设计，再验证无粒子基准与小批量，之后扩大至四尺寸×alpha/proton×0°/30°，5 MeV，每工况4个独立事件，每事件配对0/1，共64事件、128响应。累计求解预算约24小时，包含参考、数值验证和氧化层扩展；按真实耗时暂停后续提交，不按结果挑选或替换样本。

采用逐尺寸匹配的0.5 V中性参考，以真实双支路验证后用于批量分析；粒子源只作用于信号Device。保留原v1/v2/D1、pilot及±5 mV主判据、±2.5/±10 mV敏感性阈值。训练尺寸为0.18/0.35 µm，0.25 µm域内留出、0.45 µm外推；模型和测试预测冻结后才提交测试响应。另做焦点尺寸4/5/6 nm氧化层单因素检查，固定硅入口事件，不增加独立事件计数。

复用现有运行器、VM和许可证，单求解器、单线程；不安装软件、不推送GitHub、不删除旧成果。同步更新总路线、操作文档、报告提纲与证据索引，完成定稿中的数值检查、统计区间、CSV和图件、真实Sentaurus Visual截图及课程交付材料。实际分工、教师审核等未发生事项不得标为完成。

先报告实际状态和前三个执行步骤，然后继续实施；每完成一阶段更新证据与操作文档。失败、缺失、临界和数值不确定分别报告，不把电压下降直接叫位翻转，不外推商业DRAM可靠性或真实辐射截面。
```
