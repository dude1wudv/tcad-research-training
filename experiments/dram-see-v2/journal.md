# v2 实际操作日志

时间使用UTC。正在实施，未完成项不写成已完成。

- 2026-10-10 读取工作区AGENTS与v1报告/复盘。Git存在此前修改和未跟踪材料，全部保留；未建立会丢失它们的干净worktree，使用独立v2目录。
- doctor沙箱内vmrun报告VM未开机；沙箱外沿原配置成功：严格SSH、W-2024.09工具、许可证checkout/checkin。01:26:08–01:26:11的initial-inventory操作退出0，未发现活动sdevice/snmesh，约13.6 GiB可用内存、home约43 GiB剩余；已有Geant4二进制哈希与v1证据一致。
- 新版本在独立目录生成初态钳位、有限位线/参考和读出代码。指定Astra medium worker按请求启动，但接口未给运行时/OAuth证明，不冒称符合历史指定配置验收。
- pilot r1 `20261010T012717Z-v2-pilot-control-l025-b1-fed51e56`：到2.8 ns的保持求解完成，但Set(bl=.5)后静态Coupled发生`Linear system cannot be solved`，ssh_exit_code=2、FAILED_COLLECTED。已保留完整tar/输入/日志。完成标志行存在但不能据此认定成功，远端退出码和4 ns均不满足。
- pilot r2 `20261010T013430Z-v2-pilot-control-l025-b1-r2-c2e79b3c`：移除预充DC，仅作调试；初始WL关断附近反复Newton重试。设计被平滑预充方案取代，01:37:40–01:37:42核实PID106471、cmdline、cwd完全对应r2后仅发送TERM，归档退出143、FAILED_COLLECTED；没有中断其他任务。
- r3仅生成输入，未启动，保留该事实；r4改用PWL有限斜率电源、100 ohm预充电阻、3 ns关断预充，以及WL初始化0的受控初态。正式粒子批量仍等待r4及八个基线验证。
- 首个独立alpha源`l025-alpha-s202610101`由真实已有Geant4程序完成，电离沉积0.178057287517589 MeV、Q=7.924422932613915 fC。新seed的逐步CSV与v1固定事件不同；源元数据包含位置、方向、种子、源/二进制/CSV哈希。尚不把已生成源当成TCAD响应。
- 4项定向契约测试退出0：读出边界/位极性、零次上界与临界点处理、Wilson参考值、零沉积保留及来源错配/损坏拒绝；不代替真实工具验证。
- worker静态审查指出原始输入绑定、重复时刻、预充冲击、统计分母及恢复兼容性缺口；已补充结果归档输入逐字节哈希、重复电压跳变拒绝/raw CSV保存及有限斜率预充。定向动态复验尚待执行。

- 01:44:55 UTC: r4 debug run completed through 4 ns; solver 397.67 s, no Newton retries; SN initial 0.899999999689649 V, D=49.60433068052195 mV. Independent worker confirmed raw phase endpoint handling and BE/KCL. r4 lacks the later full model-contract record, so it is not an official statistical baseline.
- 01:47:43 UTC: started eight official baselines with initial gate electrode zero and full frozen model contracts. First run `20261010T014743Z-v2-base-l025-b1-143253c7` completed with solver 371.12 s; D=49.60433068052195 mV, correct at 2.5/5/10 mV.
- 01:56 UTC: after a host connection interruption, inspected existing VM command and cwd; only `20261010T015428Z-v2-base-l025-b0-c7f26462` was solving. No duplicate submission.
- Pure contract tests now include missing-outcome bounds and exact Wilson endpoints to avoid floating-point negative error bars. No simulation result is substituted by these tests.

- 2026-10-10T02:43:38.577837+00:00: 八个正式无粒子基准全部从原始归档重新审计通过；累计正式基准solver 2976.59 s。结束旧挂起控制器并恢复第五项索引，没有重复求解。
- 事前冻结每粒子n=4，独立事件总数8，配对响应16；L=0.25 µm、5 MeV、垂直入射，种子alpha 202610101–202610104/proton 202610201–202610204。累计预算14400 s包含调试/失败/验证。设计SHA-256 `f85653a58316c6d43858898ecb9976ec6b42bcb3e88da45cfa302d941f263170`。已披露冻结前单个alpha输运源可见，但没有粒子TCAD响应，未按源电荷筛种子。
- 首批命令 `python -B experiments/dram-see-v2/run_stage.py pilot` 已启动；启动不是完成，后续以ledger/原始归档为准。

- 2026-10-10T03:17:22.229699+00:00: 首批alpha/proton各一事件配对4响应完成，阶段退出0。主阈值5mV：alpha位1 M=2.450301 mV为临界、位0 M=68.524244 mV正确；proton位1 M=47.136782 mV、位0 M=27.332579 mV均正确。不能将alpha配对记为两个未翻转事件。累计计费solver约5696.91 s/14400 s；完整/恢复等价性检查已启动，尚未验收。
- 已保存并目视核对真实SVisual粒子截图 `figures/native/20261010T024342Z-v2-l025-alpha-s202610101-b1-43ecbaaa/own-window.png`；独立代理复算源积分误差0.21755%、BE/KCL、父状态继承通过，篡改重启来源的私有测试副本被拒绝。证据位于 `local_runtime/dram-see-v2/takeover-validation-20261010/particle-recheck-20261010/`；其三次测试框架错误另记，不冒充生产求解失败。

- 2026-10-10T03:26:10.880549+00:00: 完整/恢复等价性阶段退出0；full run `20261010T031637Z-v2-validate-full-l025-alpha-s202610101-b1-78b9eddc`，solver499.99s；D差1.9984e-12mV、初态差0，满足预先阈值。开始剩余冻结事件，未修改源清单/阈值/模型，验证重复不计独立样本。

## 2026-10-10 04:03 UTC — 冻结响应进度

8 个无粒子基准保持已验证。冻结粒子响应已完成 9/16；alpha 四个存储 1 的 4 ns 裕量依次为 2.450301、2.359399、6.519972、4.582502 mV，5 mV 下三项临界、一项正确；完整配对仍未齐，不作全体配对概率结论。第四 alpha 的存储 0 正在运行，随后继续原冻结质子种子。未改模型、种子、阈值或预算。交付索引脚本主代理已审阅，18 项私有 fixture 检查通过，待全部写入停止后执行正式索引。

## 2026-10-10 04:53 UTC — 主样本完成，时间细化启动

冻结8个独立事件、16个0/1响应全部VERIFIED，particles控制器退出0，VM求解快照为空后启动登记的refine。累计计费求解11132.720855/14400秒。5 mV主阈值：alpha存储1为3临界、1正确；alpha存储0和proton两初态均正确；明确判据误读均0。时间细化按离任一登记阈值最近的固定规则选alpha seed202610101/存储1，先细化匹配控制，再细化相同事件，均不增加独立事件数。最终数值检查尚未完成。

## 2026-10-10 05:18 UTC — 全部求解完成与交付核查

8个基准、16个冻结粒子响应、完整/续算及半时间步检查全部完成。半步控制D=49.605018357446 mV，事件D=2.416268128655 mV，分别耗时643.39和732.18秒；原始差分/对照修正差0.034032964/0.034720641 mV，小于0.5 mV，2.5/5/10 mV分类均稳定。主实验共14次Newton重试后完成，源积分最大相对误差0.2175473%。累计求解12508.290855/14400秒。Windows控制器、VM求解进程和ledger RUNNING均为空；未提交或推送，HEAD未变。

主代理已目视审核7类最终图件的单位、条件、run ID、图例与可读性；两组SVisual截图/原生导出逐文件哈希和TDR归档绑定全部通过。原始两次历史调试失败保留，不计入样本。一次报告编辑命令因默认GBK读取UTF-8失败而退出1，未写文件，改用明确UTF-8/补丁后成功，不属于求解失败。独立最终复核首跑因验证器误把每粒子replicate编号当全局唯一而失败，私有脚本纠正为(particle,replicate)唯一后重新核查；失败记录不删除。最终验收以其实际report/exit-code为准。

主代理最终验收：已读取独立`final-evidence.json`、`final-report.md`和`exit-code.txt=0`，核对27份正式/数值验证归档范围、4 ns双端终点和粗细差分证据与生产输出一致。独立分层/配对分母、Wilson与exact上界复算通过；这解决了从求解输出到最终分类/统计的复现性检查，不扩展到空间网格、物理校准或真实辐射截面。首跑验证器错误记录保留在`attempt1-harness-failure.*`，未修改正式输入、判据或计数来通过。
