# D1 执行日志

接续时已验证根目录、main分支及HEAD=e0638adb57def26bf3fe78c52d9c609215233e97；保留所有未提交用户改动。Windows无旧求解controller，VM无sdevice/sde/snmesh/transport，原v2 ledger无RUNNING。原pilot全部完成，当前任务为新增独立确定性诊断。

前置只读端口调查见`local_runtime/dram-readout-offset-diagnostic/inspection/`。方案、判据及代码审查在第一项提交前完成；正式执行时间与状态以design.json、独立ledger和原始manifest为准。

## 2026-10-10T07:32:23.426988+00:00 — 冻结与sanity启动

9个工况已冻结于design.json，SHA-256 b034e06845934bf9b50e760430065cdf884de3736280d243d535f5aef3c4b644。独立worker私有fixture首跑发现CRLF/LF替换不匹配，退出1且证据保留；生成器在正式冻结前统一换行后，9项输入复验退出0，mesh/geometry与原基准完全一致。主Agent已读stdout与exit-code并审阅回报，验收仅涵盖输入构建，未把它当求解通过。sanity控制器已启动，先bridge090，完成后自动按已冻结顺序运行center050；仅此一个controller。

## 2026-10-10T07:44:51.953609+00:00 — sanity完成与命名修订

桥接和中性对照均VERIFIED，run ID及完整结果见ledger。bridge D=49.604330680522 mV，与原基准一致；center D=12.369996600362 mV、offset=12.368452986311 mV。两次solver为340.33/343.40 s，未重试Newton。

呈现审查发现未提交tag rodiag1-alphaSN含大写，违反tcad.py名称规则；补充私有safe-tag检查退出1且保留证据。sanity正常退出后，以amend_naming.py执行仅命名修订：新tag rodiag1-alpha-match，旧design.json/原源码source-revisions/r1/旧未提交inputs全部保留，其余8输入未改。新旧alpha物理deck、mesh、geometry逐字节相同，仅project名称及parameters中tag/builder来源不同。design-r2.json SHA-256 475db7f4889007cfe4a01ff8fa46168f020e4c4ad78b452f94fd3d0bb418b0c6。矩阵9项、顺序、阈值、预算未变；两个既有sanity结果复用，不重跑。等待独立预发复验后继续remaining。

## 2026-10-10T07:45:50.628904+00:00 — remaining启动

独立r2_frozen_input_check退出0，9/9输入和safe-name通过；主Agent读取报告与退出码，确认8项输入未变、新旧alpha物理文件相同并验收。本批remaining控制器session37994启动，仅此调度器，顺序2–8串行；原两个sanity不重跑。

## 2026-10-10T08:11:33.015376+00:00 — SN扫描完成

6/9工况VERIFIED，原alpha101的无粒子SN匹配对照D=2.454960555355 mV，与原2.450301092792 mV差0.004659462563 mV；实际读前SN差0.049914850629 mV，满足1 mV冻结容差。SN=0.35/0.45/0.55 V时offset分别12.007293/12.250609/12.483973 mV，均完成4 ns与守恒审计。WL-off正在正常求解；WL-slow及物理matched-ref仍未做。剩余顺序、输入、预算未改变。

## 2026-10-10T08:26:23.931071+00:00 — 第9项解析失败与r3手工恢复准备

前8项均VERIFIED。WL-slow D=12.369996600361 mV，与标准50 ps ramp的4 ns差约1e-12 mV。旧matched-ref run 20261010T082333Z-rodiag1-matched-ref-a289c12b状态FAILED_COLLECTED、ssh exit5；原日志在device.cmd第14行拒绝实例名reference，瞬态未开始。VM只读核查无活动solver，失败输入/归档/日志全部保留。

amend_reference_name.py在独占controller锁下执行r3修订，将实例名改refcell，同步i()引用与输出名，新tag rodiag1-matched-ref-r3。物理连接、节点ref、参数、时序、方程和验收不变；原r2源码保存source-revisions/r2，旧ledger快照保留，失败条目补全真实run ID/解析错误。design-r3 SHA9899b4a8ad1ffb1eab05d0c90aecd3acb4c369746a04c35bdc762345695ddd91。不是自动重试，待独立预发复验通过再单独提交；前8项不重跑。

## 2026-10-10T08:28:00.397741+00:00 — r3输入验收后启动

r3独立预发复验退出0：主Agent已读stdout和退出码、审阅精确命名差异，接受其仅调度/实例名修正的证据。worker首次私有检查误假设失败ledger已有run_id，退出1留存；修正测试对原快照的事实预期后再次通过，没有放松失败保留或物理检查。remaining入口再次执行，跳过8项VERIFIED，只提交新matched-ref-r3，session6543。

## 2026-10-10T08:42:07.885381+00:00 — 连接中断后的同run恢复契约

用户交互中断导致Windows controller/SSH包装进程退出，VM原run 20261010T082741Z-rodiag1-matched-ref-r3-99f3de31仍正常求解。只读核实PID24842及真实时间推进，未重发。远端最终exit-code.txt=0，完整transient_des.log显示4 ns完成，solver=716.69 s，所有目标PLT/TDR存在；但tee的execution.log因连接中断截断，缺ENGINEERING_RUN_COMPLETED。第一次严格恢复预检因此退出1，未写入归档或成功状态。

有效design-r4.json仅增加固定此run的收集恢复证据规则，原9项输入与全部科学门槛不变，r3源码已保存。不得补写原日志。以原run.sh字节一致、工具完整结束标志、远端exit0、全部目标文件及输入hash、原4ns/KCL/BE检验交叉验证；manifest明确原执行SSH exit未知，ssh_exit_code仅表示新收集连接，其scope=recovery_collection_only。recover_collection.py仅收集既有run、不提交求解。收集前manifest/ledger快照及恢复证明在该run/collection-recovery/。

## 2026-10-10T08:49:11.666419+00:00 — 最终验收

r4恢复例外独立静态审阅退出0，主Agent阅读差异和证据后接受；同run收集/生产审计退出0，collector SHA已保存。remaining入口仅跳过9VERIFIED并生成comparisons，物理/离线差约2e-12 mV，小于0.1 mV冻结门槛。

独立原始复核最终退出0：9/9、536原文件保持；solver3548.78 s、Newton0、最大读前SN误差0.07718 mV、预充3.815 µV、最大BE残差1.2119e-8 fC。首次私有launcher路径及tar ./前缀问题的失败证据保留，修正私有读取方式后通过，未改数值断言。主Agent已读关键stdout/exitcode、审核实际数值并验收子代理成果。

四组数据图逐图目视审核，修正两处显示间距后再次检查。真实SVisual截图显示正确Abs(ElectricField-V)、单位及run ID，无伪造界面。九项确定性诊断不新增粒子样本，未改原pilot和阈值；局限与下一步见interpretation.md。
