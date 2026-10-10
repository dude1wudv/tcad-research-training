# D1 操作、提取与恢复

工作目录：`E:/TCAD-Workspace/tcad-research-training`。复用Windows Python、已有VM、Sentaurus W-2024.09许可和`scripts/tcad.py`；单核、单线程、项目锁不变。无新增软件、无Git提交/推送。

先核查Windows Python控制器和VM sdevice/sde/snmesh/transport进程，及`local_runtime/runs/*/manifest.json`未解决状态。`run.py`每次新增提交前复查VM并拒绝未解决运行；本机controller.lock只防本诊断的两个控制器，不代替全局人工核查。

```powershell
python -B experiments/dram-readout-offset-d1/run.py freeze
python -B experiments/dram-readout-offset-d1/run.py sanity
python -B experiments/dram-readout-offset-d1/run.py remaining
```

freeze只可成功一次，在创建全部独立输入后保存design.json；不启动求解。sanity只运行桥接与中心两项；remaining要求二者VERIFIED后才继续。已VERIFIED项跳过；FAILED/RUNNING项拒绝自动重发。每条命令是入口，不等于已执行成功。

原始归档由唯一runner保存在`local_runtime/runs/<timestamp>-rodiag1-<tag>-<id>/`。本批输入、ledger、stdout/stderr和只读VM探查位于`local_runtime/dram-readout-offset-d1/`。归档审计与提取实现为`audit.py`，导出到本目录`data/<run-id>/`。输入来源为原v2基准归档，父归档、mesh、源码及各输入哈希可追溯。

连接中断时先查看原controller、远端进程cwd、transient_des.log时间推进、exit-code.txt和manifest；进程退出或工具断连不证明求解停止。不自动重跑同tag，不覆盖失败证据。若已完成但ledger未更新，先独立核查归档并明确恢复索引；本版本没有自动恢复命令。不要删除锁文件来绕过活动controller。

所有阶段完成后重算原v1/v2及其归档保存清单，原pilot判据和统计不变。最终报告列已完成/失败/未做，负面诊断结果也必须保留。

## 已执行的r2修订与当前恢复入口

首次freeze/sanity已完成，不重做。r1大写tag在提交前被发现不符合运行器规则，sanity结束后运行`python -B experiments/dram-readout-offset-d1/amend_naming.py`，保存不可覆盖的design-r2.json与runtime/design-r2.sha256。该工具只能成功一次，并要求独占controller锁、仅两个sanity已VERIFIED；保留r1源码与全部旧输入，名称修订不改变任何物理条件。当前run/audit优先读取design-r2.json，其哈希及有效源码由控制器核验。恢复时继续`python -B experiments/dram-readout-offset-d1/run.py remaining`，但须先读ledger核实活动状态，禁止盲目重复提交。

## r3实例命名修订

第9项首次解析在实例名reference失败，原run及全部证据保留。有效设计现为design-r3.json：仅将器件实例名及对应电流/输出文件名改为refcell，节点ref与物理条件不变；新tag rodiag1-matched-ref-r3。修订工具amend_reference_name.py仅在已确认退出且8项VERIFIED/第9项FAILED时手工执行一次，保存r2源码与ledger快照。审核修订后再运行原remaining入口，控制器跳过前8项；禁止直接清除FAILED状态重发旧tag。失败计入运行尝试，未完成的数值不可视为物理结果。

## 2026-10-10T08:42:07.885381+00:00 — 连接中断后的同run恢复契约

用户交互中断导致Windows controller/SSH包装进程退出，VM原run 20261010T082741Z-rodiag1-matched-ref-r3-99f3de31仍正常求解。只读核实PID24842及真实时间推进，未重发。远端最终exit-code.txt=0，完整transient_des.log显示4 ns完成，solver=716.69 s，所有目标PLT/TDR存在；但tee的execution.log因连接中断截断，缺ENGINEERING_RUN_COMPLETED。第一次严格恢复预检因此退出1，未写入归档或成功状态。

有效design-r4.json仅增加固定此run的收集恢复证据规则，原9项输入与全部科学门槛不变，r3源码已保存。不得补写原日志。以原run.sh字节一致、工具完整结束标志、远端exit0、全部目标文件及输入hash、原4ns/KCL/BE检验交叉验证；manifest明确原执行SSH exit未知，ssh_exit_code仅表示新收集连接，其scope=recovery_collection_only。recover_collection.py仅收集既有run、不提交求解。收集前manifest/ledger快照及恢复证明在该run/collection-recovery/。

恢复命令仅在上述远端终态确认后执行：`python -B experiments/dram-readout-offset-d1/recover_collection.py`。成功后运行remaining入口只跳过已VERIFIED的9项并生成comparisons，不重跑；须读ledger确认再执行。

## 已完成后的分析与取证入口

```powershell
python -B experiments/dram-readout-offset-d1/curve_metrics.py
local_runtime/vdmos-analysis-venv/Scripts/python.exe -B experiments/dram-readout-offset-d1/report.py
python -B local_runtime/dram-readout-offset-diagnostic/validation-preflight/final_d1_archive_recheck.py
```

上述命令不提交求解。audit.audit(run_id, export=False)只读审计；export=True重建派生CSV但不改raw tar。独立验收结果、stdout/stderr/exitcode已提升validation/，原私有脚本及失败日志仍保留。

原生取证已实际执行`python -B experiments/dram-readout-offset-d1/gui_evidence.py 20261010T082741Z-rodiag1-matched-ref-r3-99f3de31`，输出在figures/native/该run目录。现有输出目录会被拒绝，防止重复开窗。自有SVisual PID/窗口ID见evidence.json，窗口保持打开，未关闭用户既有窗口。显示真实4 ns电场，四组读出分析图另标DATA PLOT。

全部派生文件与文档固定后执行`python -B experiments/dram-readout-offset-d1/finalize_evidence.py`，重算原536文件保存检查、确认VM无求解器、生成delivery-index.json与runtime索引哈希。该索引不哈希自身，包含10个实际运行尝试和全部D1源码/输入/数据/图件/日志证据；不提交仿真。
