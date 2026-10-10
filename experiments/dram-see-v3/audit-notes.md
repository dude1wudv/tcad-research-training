# v3 归档审计与匹配指标

本文记录实际实现及已做的软件验证，不代表 v3 求解矩阵已完成。所有默认入口只读；显式 `--export` 只写本实验目录。

## 接口

- `audit.audit(run_id, export=False)`：直接读取 `local_runtime/runs/<run_id>/inputs.tar`、`results.tar`、`manifest.json`，返回可序列化审计 summary。主要字段为 `parameters`、`archive_sha256`、`mesh_sha256`、`solver_s`（同 `wallclock_s`）、`audit_status`、`radiation`、`BE_charge_checks`、`four_terminal_closure`。
- `audit.load_curves(run_id)`：重新审计后返回 `{summary, parameters, circuit}`；曲线直接来自原始 tar，不依赖派生 CSV。旧纯解析函数以唯一模块名、内存源码执行加载，不调整 `sys.path`，不写旧目录的字节码。
- `metrics.paired_metrics(event, control, neutral)`：参数可为 run ID 或 `audit()` summary。summary 仅作为索引，重新读取和核对归档哈希。返回 `deltaQ_fC`、`D4_V`、`M4_V`、`control_M4_V`、`deltaM_V`、三阈值 `classification` 和 `read_window`。
- `metrics.compare_reference(physical, signal, neutral)`：相同输入约定；返回 `passed`、`status`、`differences_4ns`、两种分类表。信号 BL、参考 BL、D 各自差异必须 ≤0.1 mV，三阈值分类必须一致；两侧相同电压误差不能相消后通过。
- `compute_curves`、`compare_physical_curves` 为纯函数，供软件 fixture 使用；正式流程用上述 archive 入口。

CLI 示例：`python -B experiments/dram-see-v3/audit.py <run-id> --export`；`python -B experiments/dram-see-v3/metrics.py compute <event-id> <control-id> <neutral-id> --export`；`compare-physical` 子命令采用 physical/signal/neutral 顺序。

## 门槛和来源

审计需要原始 `COLLECTED`、执行 SSH=0、tar/input 哈希一致、远端退出=0、工程完成标志、SDevice 完成日志、声明输出非空和完整 4 ns。D1 的单次恢复例外不适用于 v3；缺原始标志时明确失败。

保留 v2/D1 的 0.95 ns 初态 ≤1 mV、3 ns 预充 ≤10 µV；核对完整 WL 波形。KCL 使用逐时间步 `1 pA + 0.1% × 本步各项电流绝对值和`。BE 电荷误差采用 `max(0.001 fC, 0.1% × |电容增量|)`，四端积分闭合采用 `max(0.002 fC, 0.1% × |增量|)`；检查源/漏电流符号、总/e/h/位移分量与电路时间网格。相同时间戳的相边界按旧经过验证的第一输入端点/最后输出端点区分，不把电阻切换重印当作新收敛步。

源证据包括事件 JSON、两份 CSV 及冻结哈希；合法零沉积也必须有完整事件身份。实际 deck 必须与声明的 v3 器件/电路/时序/源精确对应。HeavyIon 只允许出现在信号 Device；物理参考必须使用独立 Device、完整初始化、无重启。参考源积分上限为 `1e-12 fC`；没有 HeavyIon 输出列时，必须由已核对的独立无源 Physics 定义证明该列缺失对应无源。源积分目标始终为原 Geant4 总沉积电荷，误差 ≤5%，不以高斯截断分数修正目标或 LET。

匹配必须同时满足完整 `matching_contract`、哈希、尺寸/氧化/网格尺度/步长/所有时序和电容/物理模型/几何脚本一致，以及实际 `cell_msh.tdr` SHA-256 一致。缺参数拒绝；网格脚本相同不代替实际网格相同。若以后发现实际 TDR 时间元信息导致字节差异，需另行保存拓扑/坐标证据并经主代理处理，本实现不会自动豁免。

指标以原始位符号计算 `ΔQ=Cstore×(SN事件−SN对照)`（2.8 ns，fC）、`D=BL信号−BL中性`、`M=(2b−1)D`（4 ns）、`ΔM=M对照−M事件`。窗口为 3.8–4 ns；在线性插值的全部曲线拐点并集计算范围，不外插，不固定减 12 mV。阈值仍为 2.5/5/10 mV，等于阈值归 `critical`。

## 旧证据桥接

旧 v2 完整无粒子对照可以映射；D1 仅允许已正常完整归档的 `20261010T073750Z-rodiag1-center050-2fde80ba` 中性曲线。桥接重新核对旧模型、geometry、完整 device/circuit/initialization/timing deck 的精确一致性，D1 还核对原基准与继承 mesh 哈希。原参数作为 `legacy_bridge.original_parameters` 保留；仅返回规范化 v3 参数供新指标匹配，不改旧文件、不复用旧分类、不纳入旧粒子响应。

2026-10-10 实际只读检查八份 v2 基准和该 D1 中性归档均通过上述审计。同尺寸的 0/1 网格字节一致；L=0.25 µm 中性网格也相同，SHA-256 为 `9c5bbcc270e2bf4fb32fd3a848c2b70a5e38cb10b208fe512f6e844d4b9c41ad`。L=0.25 的新匹配无粒子有符号裕量为 bit1 `37.23433408015997 mV`、bit0 `37.389286925930965 mV`，三阈值均正确。这是重算旧基准，新增独立事件数为 0；仍需 v3 物理双支路验证。

## 已执行的软件验证和边界

`python -B local_runtime/dram-see-v3/audit-fixtures/verify.py` 退出 0，14 项通过：单/双支路模拟归档、符号电荷/裕量、端点和哈希损坏、缺完成标志、初态、KCL/四端闭合、参考源泄漏、5% 源积分、合法零沉积、缺匹配字段、网格不匹配、两侧电压误差相消陷阱、真实 v2 父档重启来源与篡改拒绝。fixture 明确标注非求解观测；全部位于被忽略的 `local_runtime/dram-see-v3/audit-fixtures/`。日志为 `test-output.txt`，旧归档只读结果为 `legacy-readonly-results.json` 和 `legacy-metrics-results.json`。

`NUMERICAL_CONTRACT_PASSED` 只表示本审计覆盖的原始证据与数值门槛通过。`response_validity` 保持待匹配参考及数值敏感性验证；全矩阵参考、半步长/网格检查、近阈值不确定标记、原生 TDR 字段/Visual 检查由阶段控制器与最终验收另行合并。TDR 在这里检查存在、非空、哈希，未声称解析商业二进制字段。没有执行求解、SSH、安装或 Git 操作。
