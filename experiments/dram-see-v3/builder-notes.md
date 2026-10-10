# v3 输入生成器

本文件说明实际实现和纯构建检查；不表示 TCAD 求解、物理审计或参考一致性已经通过。

入口为 `build_case.py`：

```python
build(out, length=.25, bit=1, event=None, parent=None,
      step=1., mesh=1., oxide_nm=5., reference='offline', neutral=False)
```

- `out` 必须是 `experiments/dram-see-v3/` 或 `local_runtime/dram-see-v3/` 下尚不存在、末级名称符合运行器规则的目录；写入前完成语义与父状态验证，独占创建且所有文件使用 `xb`。生成器不提交运行、不访问 SSH、不修改旧实验。
- `reference='offline'` 保留 v2 单器件 `Cell access` 电路及完整初始化时序。孤立的 `ref=0.5 V` 输出只为延续原始输出结构；新版离线差分必须另取匹配中性运行的 `v(bl)`。
- `neutral=True` 是单器件、无粒子、完整初始化的 `SN=0.5 V` 工况，`stored_bit=null`，不得用于粒子或物理双支路，也不加载父状态。
- `reference='physical'` 使用两个独立的 `Device SignalCell` / `Device ReferenceCell`，实例为 `access` / `refcell`。只有信号定义包含粒子源。参考节点为 `snr` / `ref`，元件为 `cstoreref` / `cref` / `rsnr` / `rref` / `rpreref`。两支路完整初始化、同时释放和预充；此模式拒绝任何 `parent`。
- 主条件为四尺寸、0/1、`step=1/.5`、`mesh=1/.7`。氧化层只支持 4/5/6 nm，4/6 nm 仅允许 0.25 µm。阈值保留 5 mV 和 2.5/10 mV。

## 几何与实际来源

生成器用唯一模块名加载 v1 几何生成器，仅在输出父目录下的独立临时目录调用其无粒子构建；旧输入没有写入副作用。5 nm 的几何文件保持 v1/v2 输出字节不变，允许真实旧基准进行严格匹配。4/6 nm 同时修改氧化层顶边界、栅接触、全局窗口和硅/氧化层界面网格尺寸，并增加随厚度缩放的氧化层窗口：最大垂直尺寸为厚度的 0.4 倍、最小为 0.2 倍，再乘 `mesh`。硅区域及其掺杂、表面网格不改。

4/6 nm 是定稿指定的探索性敏感性假设，来源不是工艺校准。其网格必须重新生成，并使用该厚度自身的无粒子与中性参考。几何/网格的真实质量和敏感性还需后续求解检查。

`parameters.json` 保留 v2 主要电容、时序、阈值、温度和初态字段，增加氧化层、参考配置、明确初态/字线时刻、参数来源与 v1/v2/D1/v3 源文件哈希。`project.json` 明确单/双支路所需 `.plt`、`.tdr` 和日志输出。

## 匹配与父状态

`matching_contract` 的字段列表由代码 `MATCHING_KEYS` 唯一定义，另加 `geometry_sha256`、`physics`、`circuit_revision`。它绑定尺寸、厚度、网格/步长、完整时序、电容、参考目标、初态过程和物理模型；为让信号、同条件中性曲线及物理验证可对应，不包含 `stored_bit`、`target_voltage_V`、`neutral` 或 `reference_mode`。

`model_contract` 在此基础上加入 schema、位/目标、neutral、reference_mode/reference_instance，以及未加粒子的完整输入 deck SHA-256。两个契约的哈希均沿用 `sha256(json.dumps(contract, sort_keys=True).encode())`，因此审计不得擅自改成紧凑 JSON 再比较。

允许 v2 或 v3 的无粒子完整单支路父状态；不允许 D1、粒子父状态或链式重启。v2 的 schema 差异通过明确的物理模型映射处理，不能只凭 schema 或少数电压参数接受：

1. 运行 manifest 必须 `COLLECTED`、SSH 退出 0，结果归档 SHA-256 一致。
2. manifest 声明的全部输入在 inputs.tar 和 results.tar 中都逐字节匹配哈希；原始远端退出、工程完成与 SDevice 完成标志均存在。
3. 原始 geometry 与新生成 geometry 字节一致；原始完整无粒子 device deck 在统一 CRLF/LF 后与新模板完全一致。
4. 原参数与自身模型契约相符，契约哈希正确；v2 的全套实际模型字段与原 schema 映射一致，且当前工况为非中性的 5 nm offline 信号。
5. 仅复制唯一、非空的 `cell_msh.tdr`、`charged_access_des.sav`、`charged_circuit_des.sav`，保存原归档、模型、输入以及复制内容哈希。不存在 D1 r4 恢复例外的通用豁免。

这些检查确认输入/状态来源，不替代父基准的完整物理审计。父状态加入粒子后的新运行仍必须审计初态、时间终点、源积分和守恒。

## 事件与源积分

事件路径只接受 v3 `data/geant4/<label>/event.json`；由同目录 `event_audit.validate_bytes(metadata, files, expected)` 验证元数据及两份 CSV。粒子种子、能量、方向和表面入口来自事件契约；同事件的 0/1 不更换事件。合法零沉积仍复制全部源证据，但不写 HeavyIon 物理源。

0°/30° 的方向为 `(-sinθ,cosθ,0)`，有限径迹使用事件已验证的硅内路径；记录出口边界和坐标。源保持 `LET=Q/track`、`source_normalization_factor=1`。真实积分仍相对 Geant4 总 `Q` 检查 ≤5%，没有把目标改为截断后的量。

`source_gaussian_diagnostic` 仅作事前几何诊断：假定横向核为 `exp(-(u/W)^2)/(sqrt(pi)*W)`、`W=0.03 µm` 且没有纵向尾部，在硅矩形中用 4096 区间 Simpson 积分估计横向保留比例。该字段明确标注 Sentaurus 核语义尚未独立确认，不影响 LET 或目标 Q。实际源积分失败时应保留失败并调查，不依据输出反调源参数。

## 已完成的纯构建检查

命令：

```powershell
python -m py_compile experiments/dram-see-v3/build_case.py
python local_runtime/dram-see-v3/builder-fixtures/verify_builder.py
```

2026-10-10 UTC 的验证退出 0，最终源码证据为 `local_runtime/dram-see-v3/builder-fixtures/run-20261010T094632776865Z/report.json`：46 个构建、21 个拒绝检查。覆盖八基准、四中性、八物理双支路、八真实 v2 父状态、4/6 nm、步长/网格与 0°/30°/零沉积。八份新基准的几何字节和完整设备 deck 均与对应真实 v2 归档相同。事件构建使用完整隔离的合成小仓库；合成事件不进入正式 `data/geant4`，不得列入真实响应数。第一次同样通过的记录保留；最终版本进一步避免加载旧源文件时写入旧目录的 `__pycache__`。

未执行真实 SDE/SDevice，未验证双 Device 解析、实际源积分、网格质量、收敛、参考一致性及数值容差。主代理统一冻结、提交与物理验收后，才可扩大正式矩阵。
