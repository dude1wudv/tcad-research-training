# DRAM SEE v2 接续记录

本次接续从既有目录与原始归档继续，不重建实验。记录时间采用 UTC，用户界面时区为 UTC−08:00。

## 安全接管事实

- 根目录核验：`E:/TCAD-Workspace/tcad-research-training`；分支 `main`，HEAD `e0638adb57def26bf3fe78c52d9c609215233e97`。原有未提交改动保留，无提交或推送。
- 用户确认旧执行来自 Dot 工作残留，其 UI 无法提供实际运行状态。因此以 Windows 进程、虚拟机 `/proc/<pid>/cwd`、命令、原始归档和运行索引交叉核实，不把另一空闲 Codex 聊天当成旧 Dot 已停止的证明。
- 接管发现旧基准控制器 Windows PID 103952 的线程为 `Wait/Suspended`；旧后续调度器 PID 132128 在等待基准，无子进程。先保存身份、索引和源码哈希，再仅停止等待中的后续调度器，防止自动冻结和提交粒子批次。
- 接管期间 `20261010T021423Z-v2-base-l035-b1-e8e23dd5` 的 SDevice PID 112661 以 `--threads 1 --exit-on-failure` 正常求解，未被终止。随后它正常完成、归档为 `COLLECTED`；远端无 SDevice，Windows 控制器仍挂起且无子进程。结束该挂起控制器后，对已完成原始归档执行 `audit(export=False)`，补登记该 run，不重复求解。
- 恢复后继续同一 `python -B experiments/dram-see-v2/run_stage.py baselines`，已经 `VERIFIED` 的五项仅重新核验归档；剩余为 0.35 µm/位0、0.45 µm/位1和位0。
- 证据：`local_runtime/dram-see-v2/takeover-20261010/`；只读远端探查命令、输出、退出码见相邻 `operations/takeover-*`。首个探查误用了不存在的 `sdevice.log`，故退出1；实际日志名为 `transient_des.log`，后续探查退出0。这个探查错误不是求解失败。
- 旧脚本、报告、可变汇总已另存 `existing-v2-source-and-deliverables.zip`；原始输入/结果 tar 保持原位，未删除旧成果。

这些事实仅证明接管时已辨认的两个旧Windows控制进程停止，不能证明旧Dot云端任务永远不会恢复。每次新增提交前仍须交叉核对Windows命令/父子关系、VM进程cwd、ledger和原始manifest；未知状态只读调查，不再启第二个控制器。可直接运行的只读核查及恢复顺序见 [操作文档](workflow.md)。正常求解不得终止，已完成归档不得重跑。

## 接管后阶段快照

`data/summary/statistics.json` 的 `2026-10-10T02:26:43Z` 快照显示5个正式基准、0个正式粒子响应，冻结设计哈希仍为空。这里是当时快照，不替代后续ledger：八基准尚未全完成，0.35 µm/位0已由原阶段控制器继续，之后为0.45 µm/位1和位0。已有单个alpha输运文件不等于正式TCAD粒子响应或冻结统计已经完成。

已保留真实GUI证据：`figures/native/20261010T014743Z-v2-base-l025-b1-143253c7/`。`own-window.png` 是真实SVisual窗口截图，`final-field-native.png` 是原生导出，`evidence.json`绑定原始归档和加载TDR哈希；主Agent已目视核对。它证明该基准的实际GUI显示，不代表全部粒子或数值检查完成。Matplotlib数据图另存 `figures/`，新增 `06-control-readout` 和 `07-read-window-and-thresholds`，均带实际run ID；缺少粒子响应时02–05尚不会生成。

## 接管时的设计候选（历史状态）

接管时没有 `stats-design.json`。旧 `finish_batch.py --n 4` 只是候选调度：每粒子4种子，4小时累计solver预算；旧plan仍写首选6种子及3小时预算。正式粒子响应尚未出现。必须先完成八基准，再依据实际成本冻结事件清单和预算，之后不按读出结果增删样本。所有预算停止、失败和缺失单独列出。

既定主判据5 mV及敏感性2.5/5/10 mV保持。每事件配对0/1仍只算一个独立事件。重复求解、完整/恢复等价性及步长检查不增加统计样本量。

当前 `run_stage.py freeze` 只冻结焦点0.25 µm清单；plan中的其他三尺寸粒子探索尚无对应执行阶段，不能宣称已覆盖。冻结后先各粒子首事件0/1配对，再完整/续算等价性，通过后执行余下冻结事件，再做匹配对照步长细化。累计4小时预算包括v2失败、调试及数值验证，单次15分钟阈值触发检查；不按是否误读提前停止或换样本。

## 本次审计与数值验收口径

- 粒子audit要求源event/steps/events及其哈希、沉积/传递电荷证据；restart要求父归档、复制文件和完整模型契约绑定。
- 步长细化选择离任一事前登记阈值最近的响应，只决定数值验证位置，不改变事件队列或统计分母。细化对照和事件均保留新run ID。
- 响应D、对照D、对照修正差分变化均须<=0.5 mV，所有登记阈值分类须稳定、对照须正确。已检查响应在某阈值粗/细跨界时，相应统计标为uncertain；保留粗/细原始值，不用主阈值通过掩盖敏感性跨界。
- 上述为已落实到代码的验收要求，不是粒子或步长检查已经通过的声明。最终证据须读取 `data/summary/numerical-checks.json` 与原始归档；新的全矩阵网格独立性仍未验证。

## 配置边界

本聊天本地会话元数据报告模型 `gpt-6-astra`、推理等级 `high`；仓库历史约定为 `medium`。未声称已切换或证明OAuth运行态，未读取任何凭据。验证代理按用户当前AGENTS使用 `worker`（Luna/high）仅做独立验证，主Agent负责设计、代码和最终验收。

## 当前结论边界

接续更新：2026-10-10 02:43 UTC，八个正式基准均已完成、从原始归档审计通过，累计基准solver时间2976.59 s；`stats-design.json`已在首个粒子TCAD提交前冻结（每粒子4事件，共8事件/16配对响应）。原先的五项快照保留为历史事实。首个粒子pilot已启动，启动不表示粒子与数值检查已验收。

这份接续记录不代表整个实验验收通过。以 `ledger.json`、原始tar重算结果、最终报告和数值检查为准。正常保持、电压下降和判据误读必须分别解释；该模型没有真实感放锁存和恢复，不能称作已校准商业DRAM的物理位翻转概率或辐射截面。

## 最终执行状态：2026-10-10 05:17 UTC

主样本8个无粒子基准、8个独立粒子事件的16个响应均已VERIFIED；full/restart和匹配半时间步检查均通过。半步验证选中alpha seed202610101/存储1，粗细差分差0.034033 mV，对照修正差0.034721 mV；2.5/5/10 mV下分类都保持临界。仅验证这一代表点的时间步敏感性，未验证全矩阵空间网格收敛。

主批与数值检查控制器均退出0；最终Windows调度器快照为空，VM无sdevice/sde/snmesh/transport，ledger无RUNNING。累计计费求解12508.290855/14400秒，预算未耗尽；本次没有追加种子。分支仍main，HEAD仍e0638adb57def26bf3fe78c52d9c609215233e97，没有提交或推送。进程和预算证据见`local_runtime/dram-see-v2/takeover-20261010/final-process-and-budget.json`与同目录Windows快照。

5 mV下alpha事件对为0明确误读、3临界、1正确；proton事件对为0明确误读、0临界、4正确，每类分母都是4。零明确误读的exact单侧95%上界52.7%，不能解读为零风险；alpha临界也不能算作正确。其他阈值、置信区间与原始数值见最终[报告](report.md)。

已有7套带CSV来源的PNG/SVG数据图，另有无粒子和alpha两组真实SVisual截图/原生导出，各自绑定原始TDR及文件哈希。所有正式输入、原始输出、历史失败均保留。最终交付导航为`data/summary/delivery-index.json`；它只在全部写入停止后生成。再次接续仍先核查实时进程和原始manifest，禁止按这份历史PID或摘要盲目重跑。
