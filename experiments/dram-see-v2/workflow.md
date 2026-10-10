# v2 操作与复现记录

所有命令从 `E:/TCAD-Workspace/tcad-research-training` 的 PowerShell 执行。先审阅 [接续记录](takeover.md)、[方案](plan.md)、[日志](journal.md)、最终冻结设计及实际失败记录；下列命令是入口，不表示全部已经运行。运行现状以 `local_runtime/dram-see-v2/ledger.json`、原始归档和 [报告](report.md) 为准。

## 环境与授权

保留当前Git修改，不checkout/reset/提交/推送；v1输入、数据、报告、运行归档保持。已启动VM通过local_runtime/connection.json及VMware Tools发现地址，专用密钥、严格公钥检查；不把连接秘密复制到实验文档。以现有Python和Geant4 10.7.3二进制/数据、Sentaurus W-2024.09执行，不安装软件。

环境确需重验且已确认无其他 solver 时才执行 `python -B scripts/tcad.py doctor`。它调用 `sdevice -v`，会签出许可证，不是纯只读进程检查。连接或 VM 检测失败不构成重启授权，不改地址或安全设置。TCAD 唯一入口保持单核、`--threads 1`、`--exit-on-failure` 及 flock；该锁不约束手工 solver，也不是 controller/ledger 并发写锁。只允许一个本实验调度者。

## 接管时先只读核查

旧进程停止只是接管时的观测，不能证明旧 Dot 云端任务以后不会恢复。每次恢复前核对 Windows、VM、ledger、原始 manifest；PID 会复用，不按历史 PID 直接停止进程。以下命令不提交求解，也不签出 SDevice 许可证。

```powershell
git status --short
git branch --show-current
git log -1 --format='%H %cI %s'
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'dram-see-v2|scripts[\\/]tcad\.py' } |
  Select-Object ProcessId, ParentProcessId, Name, CreationDate, CommandLine
Get-Content local_runtime/dram-see-v2/ledger.json
Get-ChildItem local_runtime/runs -Directory -Filter '*-v2-*' |
  Sort-Object Name |
  ForEach-Object {
    $manifestPath = Join-Path $_.FullName 'manifest.json'
    if (Test-Path -LiteralPath $manifestPath) {
      $runManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
      [pscustomobject]@{ RunId=$_.Name; State=$runManifest.state }
    }
  }
```

虚拟机进程核查复用现有 `tcad.connection()`，不打印连接配置。将 PID、父 PID、状态、运行时间和 cwd 与 manifest 对照；进程快照为空不等于队列为空，还须检查 Windows 等待控制器和 ledger。

```powershell
@'
import sys
sys.path.insert(0, 'scripts')
import tcad
_, ssh, _ = tcad.connection()
script = r'''ps -eo pid,ppid,stat,etime,comm,args | awk '$5 ~ /^(sdevice|sde|snmesh|transport)$/ {print}'
for proc in /proc/[0-9]*; do
  name=$(cat "$proc/comm" 2>/dev/null) || continue
  case "$name" in
    sdevice|sde|snmesh|transport) printf '%s cwd=' "${proc##*/}"; readlink "$proc/cwd" ;;
  esac
done
true
'''
result = tcad.remote(ssh, script, capture_output=True, text=True, timeout=45)
print(result.stdout)
print(result.stderr, file=sys.stderr)
print('remote_exit_code=', result.returncode)
'@ | python -B -
```

`python -B scripts/tcad.py shell` 是已实现的交互 SSH 入口；可以按 manifest 的真实远端路径只读查看 `transient_des.log`、退出码和输出。不要猜 `sdevice.log` 名称。两次快照间日志/CPU/瞬态时间仍推进时保留求解，不因 SSH 断线重发。

## 电路、时序和判据

沿用未校准二维NMOS、10 fF存储电容、300 K及1 µm有效厚度。0.18/0.25/0.35/0.45 µm是模型栅长，不是商业DRAM工艺节点。

| 时间/参数 | 定义 |
|---|---|
| 初态与释放 | 位0/1目标为0.1/0.9 V；理想SN辅助钳位在0.6 ns释放，0.95 ns核对误差<=1 mV并保存父状态；不代表访问管写入校准 |
| 入射与保持 | 1 ns入射；0.95–2.8 ns提取保持响应，BL为0 V |
| BL/REF | 各100 fF；2.8–2.9 ns经100 ohm电阻平滑预充BL至0.5 V，保持至3 ns，预充误差<=10 µV |
| 读取 | 3 ns预充电阻改为1e20 ohm并释放REF；3.05–3.10 ns WL从0升至1.8 V；4 ns固定采样 |
| 符号判据 | `D=V(BL)-V(REF)`，`M=(2b-1)*D`；M>epsilon正确，M<-epsilon判据误读，含边界的其余区域临界/不确定 |
| 敏感性 | 主阈值5 mV，登记阈值2.5/5/10 mV；均为模型假设 |

先看匹配无粒子保持漂移，再用同位、同尺寸对照修正粒子扰动，最后判断读出。参考电容是简化支路，没有真实感放锁存与恢复，SN电压下降不能直接称为持久物理位翻转。

## 执行顺序

1. 单个无粒子模型：

```powershell
python -B experiments/dram-see-v2/build_case.py local_runtime/dram-see-v2/inputs/<新标签> --length 0.25 --bit 1
python -B scripts/tcad.py run local_runtime/dram-see-v2/inputs/<新标签>
python -B experiments/dram-see-v2/audit.py <真实run-id>
```

2. 先完成8个无粒子基线（四栅长×两位），再依据实际成本冻结种子和样本量。此次已完成八基准，并在首个粒子响应提交前写入 `stats-design.json`：每粒子4个独立种子、累计14400 s solver预算。6种子和3小时属于更早候选，已在plan中更新。以下是实际执行顺序；已有冻结文件必须沿用，接续时跳过freeze，程序拒绝覆盖：

```powershell
python -B experiments/dram-see-v2/run_stage.py baselines
python -B experiments/dram-see-v2/run_stage.py freeze --n 4
python -B experiments/dram-see-v2/run_stage.py pilot
python -B experiments/dram-see-v2/numerical_checks.py equivalence
python -B experiments/dram-see-v2/run_stage.py particles
python -B experiments/dram-see-v2/numerical_checks.py refine
```

上面命令必须逐条顺序执行并检查退出码，失败后不运行下一阶段。freeze支持 `--n 3/4/6`，当前只生成焦点0.25 µm事件，没有其他三尺寸粒子扫描阶段。pilot是每粒子首个冻结事件的0/1配对，particles复用它们后继续剩余清单。完整/续算等价性和重复数值验证不增加独立事件数。不要同时启动 `finish_batch.py` 与显式阶段；本次旧等待器已停止。

controller保存ledger和每子命令stdout/stderr，VERIFIED项恢复时重新审计归档，不重复求解；未解决的RUNNING/FAILED停止调度，不自动重发。预算包括v2调试、失败及数值验证的solver耗时；缺少solver时间时保守计入本地运行耗时。每次新增运行前检查累计预算，单次超过900 s保留结果并停止批次待检查；累计预算不是运行中的强制杀进程计时器。

3. 手动输运只生成一个独立事件：

```powershell
python -B experiments/dram-see-v2/transport.py <新标签> --length 0.25 --particle alpha --seed <冻结种子>
```

真实源程序、已安装二进制SHA及steps/events CSV在event.json中绑定。固定5 MeV、垂直、x=L+0.45 µm、z=0。零沉积保留。事件进入TCAD时三份source文件内嵌冻结；同事件0/1复用来源，仅改变同位的成功父状态，不能跨几何或位加载。

4. `equivalence` 使用首个冻结alpha事件的位1，要求完整运行与续算的D差<=0.1 mV、入射前SN差<=0.001 mV。`refine` 在冻结响应全部完成后，选择离任一登记的±2.5/5/10 mV边界最近点；这是数值验证选择，不改变样本清单。先求新完整无粒子父运行（--step .5），再求同事件细化子运行。响应D、对照D及对照修正差分变化均须<=0.5 mV，所有阈值下分类稳定、对照仍正确。已检查响应发生粗/细跨界时，summarize将相应阈值统计标为uncertain并保留原始分类。失败不扩大阈值；本检查仅是时间步检查，不能证明新全矩阵网格独立。

以上手工命令中的尖括号需替换为实际值。手工调试采用新标签并保留旧输入，不会自动成为正式ledger样本。

## 中断与安全恢复

1. 完成只读核查，保存tag、输入哈希、进程身份、manifest和日志证据。保留正常求解与用户GUI，不删除lock、ledger条目或原始归档。
2. RUNNING可能是仍在求解，也可能是主机控制器中断；COLLECTED只表示归档完成。若VM仍有对应solver，观察原始日志并等待，不再启动同阶段。失败或身份冲突时停止新增提交。
3. 原始归档完成但ledger未登记时，先只读审计；下面调用不导出CSV也不修改ledger：

```powershell
@'
import json, sys
sys.path.insert(0, 'experiments/dram-see-v2')
from audit import audit
print(json.dumps(audit('<真实run-id>', export=False), indent=2))
'@ | python -B -
```

4. 本项目没有自动recover/collect CLI。只有Windows控制器已确认不写入、VM求解结束、tag唯一对应原始归档且审计通过后，主Agent才可先保存旧ledger，再显式补登记原run ID、真实退出码、耗时和恢复依据。不要删除记录绕过RUNNING/FAILED保护，也不把审计失败改写VERIFIED。归档不完整时先检查远端可回收输出，制定定向回收步骤，不用重新求解代替回收。
5. 索引已解决且只有一个调度者后，恢复对应现有阶段。输入不兼容、生成器哈希变化或预算耗尽须调查，不能覆盖输入或改判据继续。确需修改模型时用显式新版本标签，保留失败并重新判断是否可计入冻结统计。

## 审计、数据与绘图

audit从完整原始tar读取PLT，不从可修改summary取结果；验证输入tar与results内输入一致、完成/退出码、4 ns、初态1 mV、预充10 µV、各浮置节点KCL、保持/读出分段BE电荷闭合和源项积分误差<=5%。粒子响应要求源event/steps/events内容、哈希和沉积/传递电荷完整绑定；restart要求复制文件和原始父归档完整绑定。原始重复时刻另存circuit-raw.csv；同时间不同节点电压不能静默丢弃。

数据图使用本机已有`local_runtime/vdmos-analysis-venv/Scripts/python.exe`的NumPy/Matplotlib，输入为实际求解CSV；图注明单位、条件、run IDs和数据图属性，连接线不是新增求解。真实Sentaurus Visual截图另外取证，并绑定加载TDR哈希；不能把Matplotlib图称为工具界面截图。

## 常见失败

- 原始pilot预充后静态Coupled失败：电容不参与DC，浮置SN失去电荷约束；保留失败，不标有效。
- 理想BL电压跳变及初始WL切换导致成本/稳定性问题：正式输入采用有限斜率PWL+100 ohm预充电阻，3 ns切至1e20 ohm；WL初始化保持0，SN辅助钳位明确假设。
- 产物名按混合模式实际`final_access_des.tdr`、`transient_des.log`声明；出现命名错误保留FAILED_COLLECTED。
- 不读取/修改许可证内容或安全配置。未知运行或归档状态先核查，不盲目重跑。终止只针对已核实cwd与cmdline的本任务调试进程。

最终报告须列完整设计分母、失败/未完成项、阈值敏感性、Wilson区间和零次误读单侧上界；不能只统计容易收敛样本或声称真实截面。

## 提取、报告、图件与真实GUI证据

```powershell
python -B experiments/dram-see-v2/summarize.py
python -B experiments/dram-see-v2/make_report.py
local_runtime/vdmos-analysis-venv/Scripts/python.exe -B experiments/dram-see-v2/plot_results.py
python -B experiments/dram-see-v2/gui_evidence.py <verified-run-id>
```

前三条依次重建汇总、报告与图件，应在停止新增提交或取得一致快照后执行。CSV源数据位于 `data/summary/`：`baselines.csv`、`responses.csv`、`event-index.csv`、`all-run-attempts.csv`、`statistics.csv`。`statistics.json` 使用完整冻结事件清单；缺失层不给完整概率区间，给已知结果和确定性范围。失败、缺失、临界事件不能算作正确；每位和配对任一位分别统计，不能将0/1合并成双倍独立粒子数。

| 图件前缀（PNG / SVG） | 内容 |
|---|---|
| `01-uniform-initialization` | 统一初态、误差和存储电荷 |
| `02-hold-transients` | 匹配对照与粒子保持响应 |
| `03-readout-differential` | 0/1粒子与对照BL−REF曲线 |
| `04-event-statistics` | 事件计数与区间，缺失层明确标注 |
| `05-threshold-sensitivity` | 相同原始样本的登记阈值敏感性 |
| `06-control-readout` | 四尺寸无粒子0/1读出曲线 |
| `07-read-window-and-thresholds` | 预充、WL、4 ns采样和阈值带 |

每图带单位、条件、实际run ID；来源与哈希见 `figures/figure-evidence.json`。缺少粒子响应时不生成02–05，不能将部分图件写成全套完成。Matplotlib图明确标注DATA PLOT，连接线不是新增求解。独立事件数很小，区间仅适用于固定位置/方向/能量和当前未校准模型，不外推商业器件可靠性、截面或跨能量行为。

最后一条命令启动真实SVisual窗口，须先核对已有GUI与取证目录。`--resume`只用于该脚本已有启动记录且窗口仍存在的恢复，不能假设历史PID仍有效。`figures/native/<run-id>/evidence.json`绑定归档与加载TDR哈希；`final-field-native.png`是原生导出，`own-window.png`是未修改的真实窗口截图。检查变量 `Abs(ElectricField-V)`、V/cm单位、run ID、色标与图形；保留其他用户窗口。本次已有0.25 µm/位1基准真实截图并经目视检查，见 [接续记录](takeover.md)。

原始输入、结果及manifest保留在 `local_runtime/runs/<run-id>/`；输入参数和生成器哈希在 `local_runtime/dram-see-v2/inputs/<tag>/`，stdout/stderr在同级 `batch-logs/`，探查与输运命令及退出码在 `operations/`。CSV是可重算导出，不能替代原始输入/日志/TDR/PLT及其SHA-256。

The duplicate-time continuity check applies at positive time. Initial DC rows at time zero are retained in raw CSV before controlled transient initialization. At 3 ns, the switch reprint changes resistor current without advancing time: precharge BE uses the incoming first endpoint; KCL uses actual converged time steps and excludes phase-start rows.

## 最终复核与交付索引

完成全部冻结响应及数值验证后，重新执行汇总、报告与绘图命令。最终独立复核入口为：

```powershell
powershell -NoProfile -File local_runtime/dram-see-v2/takeover-validation-20261010/final-recheck/run_final_recheck.ps1
```

该脚本只读原始归档和冻结设计，独立复算分类、统计及源电荷，并核对电路和器件输出的4 ns终点；完整输出、退出码和报告保存在其所在目录。脚本存在或语法通过不等于数据验收通过，须检查实际退出码和`final-report.md`。

确认Windows控制器、VM求解进程与队列均不再写入，完成文档更新后执行：

```powershell
python -B experiments/dram-see-v2/deliverable_index.py
```

产物为`data/summary/delivery-index.json`，记录原始inputs.tar、results.tar、manifest.json、console.log及实验源文件、CSV、图件、文档的实际路径、大小与SHA-256。它不复制大文件，不读取连接配置/密钥/许可证，不增加独立样本数。遇到活动运行或扫描期间文件变化会拒绝发布；文件检查不能代替进程核查。索引自身排除以避免自引用；后续改动文档或图件后须在静止状态重新生成。
