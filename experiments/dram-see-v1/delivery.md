# 第一版交付与证据导航

本交付对应 2026-10-09 的自主探索实验，不表示教师已批准模型、参数或课程最终成果。先读 [报告](report.md)，再按下面的层次核查。

| 要复盘的问题 | 入口 | 能证明的范围 |
|---|---|---|
| 当时决定做什么、允许哪些假设 | [冻结计划](plan.md)、[矩阵](matrix.json)、[中文请求](matrix-request.json) | 探索范围、尺寸/粒子/方向、预算和门槛 |
| 实际做了哪些操作、为何重试 | [操作日志](journal.md)、[操作索引](data/operations-index.json) | 成功与失败经过；索引指向实际命令/stdout/stderr |
| 每个输入、求解和结果来自哪里 | [运行索引](run-index.json)、[批次记录](data/batch-ledger.json) | UTC run ID、冻结输入/输出哈希、状态、退出码 |
| 代表点的实际 deck 是什么 | [归档文本输入](reference-inputs/README.md) | 粗/细完整运行的自编几何、电路、求解设置与逐文件哈希 |
| 单个事件怎样进入 TCAD | `data/geant4/<事件>/`、`data/tcad/<run-ID>/summary.json` | 沉积原始 CSV、换算、条件绑定、源项积分 |
| 最终响应和误差是多少 | [结果表](data/scalars.csv)、[预测表](data/predictions.csv)、[完整汇总](data/results.json) | 16 个实际工况、匹配对照、分组和逐点误差 |
| 是否事后看答案调整预测 | [冻结模型](data/model-frozen.json)、[域外预登记](data/extrapolation-forecasts.json) | 固定训练来源/系数、预测时间和真实参考来源 |
| 如何验证、哪些未证明 | [验证记录](validation.md)、[独立审查](independent-review.md) | 契约检查、独立复核、代表点细化及适用边界 |
| 图件是否真实、如何再生成 | [GUI 证据](data/gui-evidence.json)、[复现流程](workflow.md) | 原生 TDR 哈希、真实桌面与派生分析图 |

## 原始证据在本机的位置

- 仓库：`E:/TCAD-Workspace/tcad-research-training/`。
- TCAD：`local_runtime/runs/<run-ID>/`，包含冻结输入、manifest、console 和结果 tar；依运行索引逐文件核对 SHA-256。
- 环境/输运/GUI：`local_runtime/dram-see-v1/operations/<标签>/`，包含 command.sh、stdout/stderr、operation.json。
- 独立验收：`local_runtime/dram-see-v1/validation/`，保存实际命令、退出码、审查发现及处理。
- VM 工程位于专用研究目录；连接沿用忽略的私人配置。本机归档与 VM 内原件分别保留，未通过新运行覆盖旧证据。

交付小型快照只包含代码、文档、汇总 CSV/JSON 和图件，不包含完整商业仿真原始 tar、安装包、受限手册、许可证、VM 或连接秘密。只有小型快照时可以审阅报告与派生数据，不能声称已在新环境复现全部 TCAD 验收。原始归档的合法共享与课程提交方式仍需之后落实。

没有提交或推送 Git。当前工作区含本轮之前的其他训练材料，未将其删除、覆盖或计作本次 DRAM 结果。

## 本机交付快照

完成验收后保存为 `local_runtime/dram-see-v1/delivery/dram-see-v1-source-and-results.zip`；相邻 `delivery-manifest.json` 记录快照 SHA-256、文件数、尺寸和核验结果。包内按仓库相对路径存放，包含本实验目录及运行器、配置示例、题目提取稿和关联文档。它是未经 Git 提交的实际文件快照，不能仅用历史 commit 代替其内容哈希。

[artifact-index.json](data/artifact-index.json) 按相对路径记录上述小型交付文件的 SHA-256；为避免自引用，它不包含自身。生成后逐项复读，并核对 zip 内文件与磁盘内容一致。原始 TCAD tar 和操作日志的来源哈希仍以运行/操作索引为准。
