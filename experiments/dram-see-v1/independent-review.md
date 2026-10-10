# DRAM SEE 最终独立数值复验（2026-10-09）

## 结论

已按冻结条件运行代表性 alpha 垂直入射细化点和同状态无粒子 control。两次真实 runner 均退出 0，analyze 与比较脚本也退出 0。粗细 baseline-corrected 响应差低于预定电压、电荷阈值；该结果只支持 L=0.25 um、alpha、0° 的一次同时网格/时间步细化，不代表独立收敛阶或整个矩阵网格无关。

另对全部 16 个已完成矩阵点从原始归档重新分析，并独立重建训练拟合与四个外推预测。15 个 SEE 归档具有输入内事件证据 hash；L=.25 alpha 0° 的一个历史点仍明确标为 legacy 外部交叉核验，不重标为新格式。外推预测均在各自 TCAD run 完成前登记，系数与预测值复算一致。域内四个留出响应在模型系数文件冻结前已可见，因此只能称未参与系数拟合的留出评价，不能称严格前瞻盲测。

## 实际命令与退出码

仓库根目录 E:\TCAD-Workspace\tcad-research-training。

1. python scripts/tcad.py run local_runtime/dram-see-v1/inputs/refine-alpha5-l025-a0  
   退出码 0。run ID 20261009T185046Z-refine-alpha5-l025-a0-27978762；runner 归档 state COLLECTED、SSH 退出 0。输入参数 L=.25 um、alpha 5 MeV、0°、Q=.007659403595125654 pC、mesh=.7、step=.5。运行 ID 时间 18:50:46 UTC，SDevice 完成日志时间 19:04:56 UTC，约 14m10s；归档于 19:04:58 UTC 收集。未超过 15 分钟，因此没有触发中断/进程检查。

2. python experiments/dram-see-v1/analyze.py 20261009T185046Z-refine-alpha5-l025-a0-27978762  
   退出码 0。归档 hash c55daed24ce787de21f623846798b81cdf836ddb7f19762e5a872853b863ae9e。输入事件绑定为 archived_input_hashes。

3. python experiments/dram-see-v1/build_case.py local_runtime/dram-see-v1/inputs/refine-control-l025-a0 --length 0.25 --mesh 0.7 --step 0.5 --restart-run 20261009T185046Z-refine-alpha5-l025-a0-27978762  
   退出码 0。只生成获准的 fine-control 测试输入，charge=0，恢复 fine 的 .95 ns 保存状态。

4. python scripts/tcad.py run local_runtime/dram-see-v1/inputs/refine-control-l025-a0  
   退出码 0。run ID 20261009T190518Z-refine-control-l025-a0-f0526020；state COLLECTED、SSH 退出 0。约 5m11s 完成。

5. python experiments/dram-see-v1/analyze.py 20261009T190518Z-refine-control-l025-a0-f0526020  
   退出码 0。

6. python experiments/dram-see-v1/compare_refinement.py 20261009T165901Z-pilot-alpha5-l025-a0-r4-078fde99 20261009T170632Z-control-l025-cd6c15bc 20261009T185046Z-refine-alpha5-l025-a0-27978762 20261009T190518Z-refine-control-l025-a0-f0526020  
   退出码 0，passed=true。脚本生成 data/numerical-validation.json。

## 细化结果与数值门槛

Fine 网格日志 cell_msh.log 记有 9,268 vertices、17,928 elements；网格生成耗时 0.506 s。最终时间 3 ns；810 circuit/device samples。prestrike voltage 0.952929875046279 V，final voltage 0.463561492377479 V，原始 ΔV 0.489368382668800 V，电容变化 4.893683826688 fC。最大 KCL 残差 2.6044e-15 A。源项积分生成 7.605058341469545 fC，目标 7.65940359512565 fC，相对误差 0.7095233%，低于 5% 门槛。BE 离散端电荷残差 5.6088e-28 C。

Fine-control 的 prestrike 与 fine 完全相同，final 为 0.952929873149280 V，无 radiation 数据，电压变化 1.8970e-9 V；用于扣除基线的无源控制有效。

| 指标 | 粗网格 | 细网格 | 绝对差 | 允许差 | 判定 |
|---|---:|---:|---:|---:|---|
| Baseline-corrected ΔV (V) | 0.489018696031368 | 0.489368380771801 | 0.000349684740433 | 0.0244509348015684 | 通过 |
| Baseline-corrected ΔQ (fC) | 4.89018696031368 | 4.89368380771801 | 0.003496847404330 | 0.244509348015684 | 通过 |

门槛分别为 max(0.01 V, 5% 粗网格信号) 与 max(0.1 fC, 5% 粗网格信号)。粗网格 BE/梯形端电荷差为 0.0721610 fC，细网格为 0.0380316 fC，差异随 step=.5 减小；这只表示该代表点的同时细化变化，不能分离 mesh 与 timestep 影响，也不能替代全矩阵或多级收敛验证。粗、细源项相对误差分别为 0.21755% 和 0.70952%，都低于 5%。

归档与关键日志 SHA-256：

| Run | results.tar | execution.log | transient_des.log |
|---|---|---|---|
| Fine 20261009T185046Z-refine-alpha5-l025-a0-27978762 | c55daed24ce787de21f623846798b81cdf836ddb7f19762e5a872853b863ae9e | 5e62619dfe637b422b69a2b1dc1a5a3d90529c373d4662b3baf8fceb2d4dce41 | b00cddc20b951b1fa1a89251a621e1a86ba007792beaab1610100aef95bed266 |
| Fine-control 20261009T190518Z-refine-control-l025-a0-f0526020 | 3356bb7b311bf32070ef0b63af700956f2a543b81e07e789eb4f6910904ade2e | 03a437cd9d2259a9f1e5acb66704329dd833ba556b73ff1ebb76cf0fe4291dcd | 4fdf5bed8cac7e0b04b5bf869763ffc8b44962e56e0f34213d5b2e97ce3a2dd8 |

Fine geometry.log SHA-256 为 7261e0baaf2292aa55df38d79e7f94f0224db9cbcda3a40b0933089e1817db10；cell_msh.log 为 e58de24107be60b1d1e3805a511861aef4bc54f743a2f7eb4092f2d9203867e0。完整未裁剪运行日志保存在各自 local_runtime/runs/<run-id>/results.tar。

## 16 点归档、模型与预测独立核验

粗矩阵 SHA-256 e74691aec1ec162a6c5298564502e76de8252c24cf47db29e4eab816338c0005，分组 8 train / 4 interpolation / 4 extrapolation。逐点重跑 analyze(export=False)，并从每点实际事件元数据与 SEE/control 归档重新计算 Q、baseline-corrected ΔV、ΔQ、源项误差，再与 data/results.json 对照：16/16 数值吻合。

事件证据绑定为 15 archived_input_hashes + 1 legacy_external_event_crosscheck。唯一 legacy 点为 l025-alpha-e5-a0，run 20261009T170858Z-see-l025-alpha-e5-a0-c07e356d；其矩阵条件、原始 CSV hash、raw energy→Q 和 TCAD 参数 Q 均核对吻合，但 metadata 未冻结进旧 TCAD 输入，保持原标签。它不被冒称为新格式。其余 15 点的三个 source evidence 文件 hash 均与归档参数/manifest 及当前事件文件相符。

冻结模型文件 SHA-256 为 3cd946a3bbd4f37ad40846bbec54bb29b3f981183c6f48268b70a2b4fd373351；matrix hash 匹配。独立从 16 份原始归档重算响应后，只用 8 个 train 点进行 OLS：设计矩阵 rank=4，重建系数与 model-frozen.json 的最大绝对差 1.95e-16；训练 run IDs 一致。与 results.json 的数值指标吻合：

- Train：MAE 0.0026340556 V，最大绝对误差 0.0046793117 V。
- Interpolation holdout：MAE 0.0043924826 V，最大绝对误差 0.0157603105 V。
- Extrapolation：MAE 0.0034135914 V，最大绝对误差 0.0070052679 V。

每组最大误差低于 0.05 V 目标。模型在 2026-10-09 18:23:58.530486 UTC 冻结，拟合列表包含 8 个训练 run；当时也已观察到 4 个 interpolation 响应，但拟合代码和独立 OLS 重算只将 train 标签用于最小二乘。因域内响应在系数冻结前可见，域内结果是未参与拟合的留出评价，不是严格前瞻盲测。

外推模型 SHA-256 与 event SHA-256 均逐项复核；按实际 Geant4 Q 和模型系数重新计算，预测与 extrapolation-forecasts.json 及 results.json 一致。四个事件注册时间都早于对应 batch finished_utc：

| 外推工况 | Forecast UTC | TCAD finished UTC | 冻结预测 (V) | results.json 实测 (V) | 误差 (V) |
|---|---|---|---:|---:|---:|
| l045-alpha-e5-a0 | 18:32:21.201837 | 18:34:58.816339 | 0.4837592100 | 0.4907644779 | -0.0070052679 |
| l045-alpha-e5-a30 | 18:36:05.724504 | 18:40:04.801305 | 0.4485379733 | 0.4541429900 | -0.0056050167 |
| l045-proton-e5-a0 | 18:40:45.461965 | 18:44:37.758266 | 0.0210838867 | 0.0207666770 | 0.0003172097 |
| l045-proton-e5-a30 | 18:46:21.570953 | 18:49:08.778025 | 0.0187541347 | 0.0194810060 | -0.0007268713 |

## 未验证范围

细化只使用一个 alpha 垂直代表点，并同时改变 mesh 与 timestep；不能得出独立网格/时间步收敛阶，也不能声称 16 工况均网格无关。模型依赖 Geant4 Q 作为输入，单事件、未校准二维简化模型不构成独立粒子到器件的端到端预测或商业 DRAM upset/cross-section 结论。未重跑此前已通过的简单契约测试；本任务集中于冻结数值输入、归档、独立重算与比较结果。

数值比较 JSON：experiments/dram-see-v1/data/numerical-validation.json，SHA-256 58480c7046fd320296b707ea38cd529519e42526e2f995b79992b1c72ba7c88f。全 16 点原始归档重算/OLS/forecast 审计为只读 PowerShell here-string piped to workspace Python (numpy 2.3.5)，退出码 0；重算 4 个 control 和 16 个 SEE 归档。
