# 第一版复现与交付流程

本轮由用户授权自主探索。实际路线是已打开的 VMware 客户机、严格 SSH、CLI 真实求解、Sentaurus Visual GUI 读图；没有把 CLI 工程冒称为 Workbench 节点工程，也没有验证 Workbench 的 Run 按钮。参数来源、科学边界见 [plan.md](plan.md)，失败经过见 [journal.md](journal.md)。

## 1. 保留环境和输入

从仓库根目录执行。连接沿用 `scripts/tcad.py`，由忽略目录中的连接配置与 VMware Tools 发现地址，不能把私人连接配置复制进报告。先核对已打开的 VM、已有求解和 GUI，再操作。完整原始输出保存在 `local_runtime/`，商业软件、数据包和许可证不作为仓库附件。

Geant4 的包、编译与数据路径见 [environment.md](environment.md)。本轮环境已建成，复现单个事件不需要重装。安装及探测命令逐条记在 `local_runtime/dram-see-v1/operations/<标签>/command.sh`，对应 stdout、stderr、起止时间、退出码和脚本 SHA-256 同目录保存。

## 2. 约束自然语言并冻结矩阵

`request_to_matrix.py` 将限定中文模板转为显式参数集合；最初 12 点示例见 `request.json`，包含域外尺寸的完整 16 点表达见 `matrix-request.json`，实际冻结矩阵见 `matrix.json`。完整表达已逐字段核对与矩阵一致。它不是通用语言模型接口。未识别语义、越界数值、非法粒子和过大任务拒绝执行，不能默默猜参数或把用户文本交给 shell。

正式矩阵使用四种栅长、两种粒子、两种方向，共 16 个工况。训练及域内/域外留出在读取正式响应前固定；生成失败不能随意替换成“容易拟合”的点。

## 3. 真实粒子输运与传递

```powershell
python experiments/dram-see-v1/transport.py <新的事件标签> --length 0.25 --particle alpha --energy 5 --angle 0
```

固定种子在参数及事件元数据中保存。标签不能覆盖已有事件。程序在 VM 调用真实 Geant4，可审查的逐步沉积与汇总进入 `data/geant4/<标签>/`。电离能先换成电荷，再除以几何径迹长生成 HeavyIon LET；没有把三维径迹逐点传入二维器件。

## 4. 建模、写入、保持与粒子瞬态

```powershell
python experiments/dram-see-v1/build_case.py local_runtime/dram-see-v1/inputs/<新的工程标签> --length 0.25 --charge-pc <事件中的实际电荷pC> --event experiments/dram-see-v1/data/geant4/<事件标签>/event.json
python scripts/tcad.py run local_runtime/dram-see-v1/inputs/<新的工程标签>
python experiments/dram-see-v1/analyze.py <实际返回的run-ID>
```

这些尖括号是必须替换的参数，不能照抄执行。生成器拒绝覆盖目录。`project.json` 声明 SDE 与 SDevice 产物，runner 保存实际输入、源码哈希、命令和结果归档。单线程、单核 affinity 和项目锁不绕过。只有 runner 成功且分析契约通过的运行，才用于正式标量表。

完整运行包括 0–0.95 ns 充电/关断/保持、0.95–1.05 ns 事件精细时间段、1.05–3 ns 恢复段。无粒子对照与事件共享同尺寸和模型。每个尺寸首次完整运行保存 0.95 ns 状态；仅同几何/网格可加载，该状态哈希及父归档哈希进入续算输入。先比较同事件全程与续算，再允许批量续算。

分析同时检查退出码、完成时间、写入电压、保持偏压、KCL、端电流与电容电荷及 HeavyIon 生成率积分。电路采用后向欧拉，守恒比较按实际离散时刻的右端点电流积分；梯形积分值另行保留，不能混用离散方法导致假守恒误差。

## 5. 批量执行和失败恢复

```powershell
python experiments/dram-see-v1/run_batch.py --pilot-run <通过分析的完整pilot-run-ID>
```

运行状态保存在 `local_runtime/dram-see-v1/batch-state.json`；各子调用输出在 `batch-logs/`。只串行调用现有 runner，已验证项可恢复，未解决的失败项会阻止继续。SSH 断开或超时先确认远端状态，不能重复提交。历史 manifest 不改写；修正原因及新输入必须另记。

同一批次再次执行该命令会复用已验证运行，不表示又计算了一遍。需要独立重复时，按第 3–4 节使用新的事件/工程标签，保留原批次；当前版本未提供多批次命名空间或自动重置数据的接口。

## 6. 数值检查、拟合和图件

用同一事件的细化网格/时间步及匹配对照验证代表点。保持预先声明的容差，失败不放宽。矩阵完成后，用现有分析环境运行 `summarize.py`；回归只在训练点拟合，域内及域外点用于评价，逐点误差和训练均值基准同时保留。此模型依赖 Geant4 沉积电荷输入，是两阶段代理模型。

`visualize.tcl` 在新的 Visual GUI 加载实际成功 run 的网格及 1 ns TDR，导出结构、电场和电子密度；记录 TDR SHA-256，并单独用 `tests/pn-field-desktop/desktop.py` 抓取真实客户机桌面。原生导出与桌面截图分别检查，已有用户窗口不关闭。

## 7. 交付与再次运行

阅读顺序为 README → report → journal → 本流程 → 参数/代码/索引。仓库内小型 CSV、JSON、图件便于审查；完整日志与 TDR/PLT 仍留本机，依 `run-index.json` 的 run ID、哈希定位。仅有 Git commit 不足以复现未提交工作，须同时保留实际输入及脚本哈希。交付前核对链接、清单、截图变量和数值结论；未经授权不提交或推送。

## 8. 离线审阅与轻量复算

无需启动 VM 即可先审阅 `data/results.json`、`data/predictions.csv`、`data/model-frozen.json` 和 `data/extrapolation-forecasts.json`，按 run ID 查 `data/tcad/` 派生曲线及 `run-index.json`。批调度记录见 `data/batch-ledger.json`；它包含恢复历史，不等于全体调试/细化运行索引。

实际分析环境为本机已有 Python 虚拟环境，版本记录见 `data/analysis-environment.json`。下列命令在仓库根目录执行，仅重建派生汇总和证据清单，必须已保留对应原始归档；它们不启动新的求解：

```powershell
& local_runtime/vdmos-analysis-venv/Scripts/python.exe experiments/dram-see-v1/summarize.py
python experiments/dram-see-v1/catalog_evidence.py
```

若需要核验来源，先将 `run-index.json` 对应的 `local_runtime/runs/<run-ID>/` 原始归档与清单哈希比较，再重算；不要用重新生成的清单代替对原清单的核对。`summarize.py` 会核对冻结矩阵、训练来源及系数，且检查事件原始 CSV 和 TCAD 归档的来源绑定。最早 pilot/首个续算没有内嵌事件文件，仍按 legacy 方式外部交叉核验，不伪装成新格式归档。

完整原始包需要单独交付或备份，不能只拷贝 Git 源码后声称可复现商业仿真。课程提交前还需协商合法的归档访问方式；当前没有把原始 tar、商业工具、许可证或私有连接信息上传到外部服务。

## 9. 本轮实际数值比较命令

以下命令只重分析已归档的四个运行，不启动 solver；完整原始归档必须存在。实测退出 0，预先冻结的门槛未修改：

```powershell
python experiments/dram-see-v1/compare_refinement.py 20261009T165901Z-pilot-alpha5-l025-a0-r4-078fde99 20261009T170632Z-control-l025-cd6c15bc 20261009T185046Z-refine-alpha5-l025-a0-27978762 20261009T190518Z-refine-control-l025-a0-f0526020
```

两版完整运行的实际自编文本输入及逐文件来源哈希已提取到 [reference-inputs](reference-inputs/README.md)，方便直接对比。这里的输入保持历史原样，生成器后续增加的来源绑定不会追写到旧输入中。
