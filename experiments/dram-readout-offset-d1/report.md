# D1 读出偏移诊断结果

当前采用有效 `design-r4.json`。r1→r2只将未提交工况tag `rodiag1-alphaSN` 改为 `rodiag1-alpha-match`；物理条件、执行顺序、阈值与九工况总数不变。 r2→r3只修订匹配参考实例名 `reference→refcell` 及随之改变的原始输出名，node `ref`不变，新active tag为 `rodiag1-matched-ref-r3`。原始输出是 `refcell_device.plt`，已审计CSV导出名仍为 `reference-device.csv`；物理条件、顺序、阈值不变。 各版设计、源码快照、旧输入及历史失败run均保留。

当前有效冻结工况9项；active ledger VERIFIED为9项，具备完整呈现导出9项，active FAILED为0项，未开始0项。另有历史尝试1项，单列保留，不增加有效工况数。
本报告呈现已有audit导出，不运行求解、不重新作科学验收。图中只有实际已有数据；缺失项不能视为已完成或零效应。

这是无粒子确定性诊断，所有扫描、字线对照和参考支路工况均不是独立粒子事件，不计算概率或置信区间。原v1/v2模型数据、pilot分类和2.5/5/10 mV阈值保持不变。

## 完成、失败与未做

| tag | ledger状态 | run ID | 失败或呈现缺失原因 |
|---|---|---|---|

r4为同run中断恢复审计：原执行SSH退出码未知，execution.log因连接中断缺少末尾流标记；完整器件日志、远端exit-code=0、全部输出与输入哈希及科学检验仍通过。原日志未补写，原run没有重跑。恢复快照及证明见该run的collection-recovery目录。

| rodiag1-bridge090 | VERIFIED | 20261010T073147Z-rodiag1-bridge090-8db1e0b8 | — |
| rodiag1-center050 | VERIFIED | 20261010T073750Z-rodiag1-center050-2fde80ba | — |
| rodiag1-alpha-match | VERIFIED | 20261010T074533Z-rodiag1-alpha-match-d0af10aa | — |
| rodiag1-scan035 | VERIFIED | 20261010T075140Z-rodiag1-scan035-fd250135 | — |
| rodiag1-scan045 | VERIFIED | 20261010T075751Z-rodiag1-scan045-bbc7abd1 | — |
| rodiag1-scan055 | VERIFIED | 20261010T080358Z-rodiag1-scan055-02fe8094 | — |
| rodiag1-wl-off | VERIFIED | 20261010T081041Z-rodiag1-wl-off-55dfc440 | — |
| rodiag1-wl-slow | VERIFIED | 20261010T081707Z-rodiag1-wl-slow-5acda3af | — |
| rodiag1-matched-ref-r3 | VERIFIED | 20261010T082741Z-rodiag1-matched-ref-r3-99f3de31 | — |

### 历史尝试（不计入当前有效九工况）

| tag | ledger / 原始manifest状态 | run ID | 原始原因与控制器记录 |
|---|---|---|---|
| rodiag1-matched-ref | FAILED / FAILED_COLLECTED | 20261010T082333Z-rodiag1-matched-ref-a289c12b | Error in "device.cmd" at line 14, offending input: reference \| syntax error !；ValueError('Runner failure/ambiguous identity') |

ledger的failures列表保留1条记录；与runs中的同一历史失败不重复计数。历史失败不转写为成功，也不替代active matched-ref-r3结果。

## 桥接与参考匹配检查

bridge ledger状态为VERIFIED（控制器在该状态前执行冻结桥接门槛）。新旧D差为+0.000000000 mV；设计门槛为绝对差≤0.01 mV。该差值是呈现，不新增验收规则。
原基准：`20261010T014743Z-v2-base-l025-b1-143253c7`；新桥接：`20261010T073147Z-rodiag1-bridge090-8db1e0b8`。

`comparisons.json`记录的 `passed=True`；该状态直接沿用控制器记录。
离线D=-9.915036045006985 mV，physical D=-9.915036045004989 mV，差=1.9966250874858815e-12 mV，冻结容差=0.1 mV。
新alphaSN无粒子工况与原alpha101读前SN匹配误差=0.04991485062899592 mV；只是标量SN匹配，不代表载流子或场历史相同。

## 实际数据

| tag | SN(3 ns)/V | D(4 ns)/mV | 二电容预测/mV | offset/mV | SN+BL净增/fC | gate积分/fC | body积分/fC |
|---|---:|---:|---:|---:|---:|---:|---:|
| rodiag1-bridge090 | 0.900077175 | 49.604331 | 36.367185 | 13.237146 | 1.456086028 | 1.466198748 | -0.010112708 |
| rodiag1-center050 | 0.500055125 | 12.369997 | 0.001544 | 12.368453 | 1.360529828 | 1.464107028 | -0.103577200 |
| rodiag1-alpha-match | 0.393777670 | 2.454961 | -9.660043 | 12.115004 | 1.332650425 | 1.463569701 | -0.130919276 |
| rodiag1-scan035 | 0.350047852 | -1.628188 | -13.635481 | 12.007293 | 1.320802248 | 1.463343929 | -0.142541679 |
| rodiag1-scan045 | 0.450052639 | 7.706472 | -4.544137 | 12.250609 | 1.347566943 | 1.463855487 | -0.116288558 |
| rodiag1-scan055 | 0.550057673 | 17.031202 | 4.547230 | 12.483973 | 1.373236993 | 1.464358068 | -0.091121075 |
| rodiag1-wl-off | 0.500055125 | -0.003816 | 0.001544 | -0.005359 | -0.000000209 | 0.000000044 | -0.000000253 |
| rodiag1-wl-slow | 0.500055125 | 12.369997 | 0.001544 | 12.368453 | 1.360529828 | 1.464107028 | -0.103577200 |
| rodiag1-matched-ref-r3 | 0.393777670 | -9.915036 | -9.656229 | -0.258807 | 1.332650425 | 1.463569701 | -0.130919276 |

电荷关系沿用audit：`ΔQcap=+∫circuit流入dt≈−∫(Is+Id)dt=∫(Ig+Ib)dt`；device端口电流与circuit节点流入方向相反。二电容预测使用实际3 ns的SN、BL、REF，offset解释同时保留终点SN−BL未等势项与REF漂移。WL-off不能假设已经完成电荷共享。

gate TotalCurrent与DisplacementCurrent、eCurrent、hCurrent分别列于CSV；栅位移电流不等于载流子穿越栅氧。端口守恒能量化外部交换，但不能唯一拆分内部重叠电容、沟道形成和耗尽变化的各自贡献。

## 原alpha101只读依据（本批冻结前已知）

原alpha101位1`20261010T024342Z-v2-l025-alpha-s202610101-b1-43ecbaaa`：3–4 ns理想电容净增1.332637033 fC；除以110 fF对应12.114882118 mV，与该run实际BL相对封闭共享值的偏移12.114882118 mV对应。
gate积分+1.463569446 fC，body积分-0.130932412 fC。这是原始只读取证结果，不计为D1新增结果。
原summary记录D=2.450301093 mV、读前SN=0.393727754889 V。

[原端口证据](../../local_runtime/dram-readout-offset-diagnostic/inspection/sign-check-and-alpha101-charge.json)；[原alpha summary](../dram-see-v2/data/tcad/20261010T024342Z-v2-l025-alpha-s202610101-b1-43ecbaaa/summary.json)。

## 图件、数据与边界

- [SN传递与offset](figures/01-sn-transfer-and-offset.png)
- [WL、gate/body电流与BL−REF读出](figures/02-wl-and-terminal-currents.png)
- [端口积分与电荷闭合](figures/03-port-integrals-and-closure.png)
- [理想、离线与physical参考及原alpha101对照](figures/04-reference-readout-contrasts.png)
- [源汇总CSV](data/summary.csv)；[图件来源与SHA-256](figures/figure-evidence.json)；每图同时保留SVG。

所有图均标注DATA PLOT、单位、条件与实际run ID；不是Sentaurus Visual截图。离线参考曲线仅对center BL作线性时间插值以相减，不产生新的求解点。04图中的原alpha101实际曲线和4 ns值属于有粒子、不同历史的只读旧证据，其CSV/summary另有哈希和run ID，不计入本批九项，也不修改原pilot判据。CSV保留未开始、失败和缺失状态。

未做：新的空间网格/时间步独立性、真实感放锁存/恢复、噪声和失调分布、实际工艺校准、新粒子能量或位置扫描。原alpha与无粒子标量SN相近不证明内部状态相同。不能由本批推出真实DRAM可靠性、辐射截面或误读概率。
