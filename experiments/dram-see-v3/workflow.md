# v3 操作与恢复

工作目录 `E:/TCAD-Workspace/tcad-research-training`。所有求解统一通过 `python -B scripts/tcad.py run <冻结输入目录>`；现有严格SSH、VMware Tools地址发现、单核affinity、`--threads 1 --exit-on-failure`及远端flock保持。主代理为唯一调度者。

先读[计划](plan.md)、[冻结设计](stats-design.json)、[最新日志](journal.md)及 `local_runtime/dram-see-v3/ledger.json`（尚不存在代表未启动任何v3响应）。恢复时先看Windows控制器、VM进程/当前输出和全部manifest；连接中断不证明远端退出，禁止盲目重发或删除锁。旧v2/D1 freeze/batch/remaining命令不用于v3。

已执行的只读核查、保全与冻结命令：

```powershell
python -B experiments/dram-see-v3/common.py preflight
python -B experiments/dram-see-v3/common.py preserve
python -B experiments/dram-see-v3/design.py freeze
```

preserve/freeze都是一次性命令，已有文件时拒绝覆盖；接续使用 `common.py check` 检验旧成果。原始证据仅在被忽略的 `local_runtime/`，不读取或拷贝连接秘密、密钥、许可证。代码和依赖还需在第一项提交前另存不可覆盖的执行冻结清单。

限定自然语言接口只解析带单位的明确模板，不执行任意shell：

```powershell
python -B experiments/dram-see-v3/design.py request
```

默认模板生成已冻结矩阵；`--text`可给同格式请求，歧义、越界、额外重复或改变预算均拒绝。成功解析不自动调度。

依赖顺序：参考/基准 → 首批与源隔离 → 其余训练 → 模型及逐测试事件预测冻结 → 留出/外推响应 → 氧化层及数值检查 → 交付。每阶段工程收集与科学审计分开，错误、失败、缺失、临界及数值不确定分开登记。不得用失败子集调整种子、指标或阈值。

中断时保存现有run ID、输入/归档哈希、进程身份、远端日志时间推进和退出码。若同run仍正常求解，等待；若结束且未归档，定向收集原run并记录真实SSH状态。D1的r4恢复例外只属于旧run，不能自动用于v3。预算只限制后续提交，不终止正常求解。

源项保留 `LET=Qdep/track_length`，归一化系数1。30°侧退出与高斯截断的几何估计只作诊断，实际积分仍和原Qdep比较≤5%；不事后将目标改成截断后Q。4/6nm扩展重新生成网格与其自身基准/参考，固定硅入口事件，不改变Geant4材料栈。
