# v3 粒子输运接口与坐标契约

状态：2026-10-10 完成接口实现与本地 fixture 验证；本文不证明任何新版 Geant4 或 TCAD 已运行。真实事件只能由主代理在确认唯一调度者、活动进程与队列后串行提交。

## 接口与固定设计

- `transport.run(label, length, particle, seed, angle=0)` 返回一个事件元数据字典；CLI 参数为标签、`--length`、`--particle`、`--seed`、`--angle`。
- `event_audit.validate_bytes(metadata_bytes, files, expected=None)` 保留 v2 的调用形式；`files` 必须恰为 `events.csv`、`steps.csv` 的字节内容。`expected` 可传尺寸、粒子、能量、角度、种子等精确条件。另有 `validate_event(path, expected=None)` 与纯函数 `geometry(length, angle)`。
- 只接受栅长 0.18/0.25/0.35/0.45 µm、alpha/proton、5 MeV、0°/30°、单事件。种子强制满足 `202610300+10c+r`、`c=4*尺寸索引+2*粒子索引+方向索引`、`r=1..4`。本次 fixture 核查 64 个种子互异，且不与本地 v1/v2 归档事件种子重合。
- 事件输出只写 `experiments/dram-see-v3/data/geant4/<label>/`；操作命令、原始 stdout/stderr、收集 tar 和操作状态只写 `local_runtime/dram-see-v3/operations/g4-<label>/`。已有 v1/v2/D1 不写入。
- 复用 `scripts/tcad.py` 的 `connection()`（VMware Tools 发现地址、专用密钥与严格主机验证）；不导入会把日志写到 v2 的 `operate.py`。导入此模块或验证事件不会连接 VM。

## 已安装二进制与来源证据

现有源码为 `experiments/dram-see-v1/geant4_transport.cc`，SHA-256：

```text
8f3ec870dad0905be7516bf657ed033d8cf5c5ade7cef938a941622b2f483ce2
```

现有二进制的冻结 SHA-256：

```text
830cd8480bc11a27b243f6662d0e64a71d5b382a45bfd1e80f8e199bfdfdb67f
```

历史依据是 `local_runtime/dram-see-v1/operations/binary-provenance/command.sh`、`stdout.txt`、`operation.json`：操作退出 0，源码哈希吻合，旧二进制与当时重编译的验证二进制逐字节一致，输出 `REPRODUCIBLE_BINARY_MATCH`。这属于历史来源证明。本次实现没有重编译、安装、SSH 或实际输运。真实 `run()` 每次提交前核对本地源码，并在远端只读核对 `${remote_root}/dram-see-v1/build/{geant4_transport.cc,transport}` 的哈希；变化即失败。

该源码已支持 0–45° 参数、指定的方向与真空发射位置补偿，因此 v3 的 30° 不需要新编译。几何只有硅与真空，没有栅氧层、互连或封装；氧化层扩展复用同一个硅入口事件。

## 坐标、径迹与转换

硅矩形为 `0≤x≤L+0.6`、`0≤y≤1.2` µm，三维输运厚度为 `−0.5≤z≤0.5` µm。以弧度 `θ` 计算：

```text
surface = (L+0.45, 0, 0)
launch  = (L+0.45+0.001*tan(theta), -0.001, 0)
direction = (-sin(theta), cos(theta), 0)
track = 1.2                                      if theta == 0
track = min(1.2/cos(theta), (L+0.45)/sin(theta))  otherwise
exit = surface + track*direction
```

发射点沿直线传播至 `y=0` 恰好落在冻结表面位置。0.18 µm/30° 径迹长为 1.26 µm，从左侧退出；0.25 µm/30° 在底边退出，出口 `x≈0.007179677 µm`，接近左下角。其余 30° 从底边退出。元数据保存表面、发射点、方向、出口与出口边界，验证时重算。

电离能量为各硅内步的 `max(0, edep−niel)` 之和，转换保持：

```text
Q[pC] = Eion[MeV] * 1e6 / 3.6 * 1.602176634e-19 * 1e12
LET[pC/um] = Q / track
```

`converted[0]` 保留 `event`、`ionizing_MeV`、`charge_pc`、`track_length_um`、`let_pc_per_um`。几何径迹只是二维等效直径迹；真实散射后的 `primary_path_um` 可不同，不能用相等检查拒绝真实事件。Geant4 只写总沉积能量为正的步，故记录主粒子步长之和可小于完整主粒子路程。真实步 CSV 的空间与时间分布保留作原始证据，不声称逐步映射到了 TCAD。

## 高斯截断的输入前诊断

主代理已冻结：保留 `LET=Q/track`、`source_normalization_factor=1`；真实 TCAD 源积分继续以原始 Geant4 总 `Q` 为目标，误差门槛仍为 5%。不得把目标改成 `Q*F`，也不得根据已求解的积分反调源、门槛或种子。截断估计只用于解释风险。实际积分失败时保留失败并暂停相关扩大步骤调查。

输入 builder 可按以下确定的几何计算诊断量，且必须标明核假设。假设横向 Gaussian 为 `exp(-(u/W)^2)/(sqrt(pi)*W)`、`W=0.03 µm`，纵向在 `0≤s≤track` 均匀、两端硬截断。坐标变换为：

```text
x(s,u) = impact - s*sin(theta) + u*cos(theta)
y(s,u) = s*cos(theta) + u*sin(theta)
```

令宽 `B=L+0.6`、深 `H=1.2`。30° 时：

```text
u_lo(s) = max((-impact+s*sin(theta))/cos(theta), -s*cos(theta)/sin(theta))
u_hi(s) = min((B-impact+s*sin(theta))/cos(theta), (H-s*cos(theta))/sin(theta))
F = integral_0^track [erf(u_hi/W)-erf(u_lo/W)]/2 ds / track
```

0° 分支避免除零：`u_lo=-impact`、`u_hi=B-impact`，只要 `0≤s≤H`。对空区间积分取零。builder 应冻结积分方法、精度、核假设和计算结果，不能使用粒子响应选择方法。这个二维高斯估计没有重新定义 Sentaurus 模型；真实求解的 `HeavyIonGeneration(Integrate(Semiconductor))` 时空积分仍是验收证据。`F` 既不改 Geant4 事件的原始 Q，也不改变独立事件数。

## 审计与不可重复提交

事件审计核对：schema、条件与登记种子、来源哈希、CSV 哈希、退出状态、事件/操作身份、坐标契约、能量守恒、逐步电离/非电离分解、有限数、非负物理量、硅范围、父子轨迹编号、转换 Q 与 LET。损坏字节会被哈希拒绝；即使重写哈希，语义错误也被拒绝。

零电离沉积是合法结果。空步表配合零事件沉积可以通过；保留事件元数据、种子和所有原始文件，不能替换种子或把它当缺失。零电荷不等于没有发生粒子事件。

本地按种子原子建目录预约；事件标签、已成功事件种子、已有操作请求、已有输出目录均拒绝重用。远端同样使用不可覆盖事件目录与种子目录。任何异常都把操作标为 `REQUIRES_READ_ONLY_RECONCILIATION`，保留请求和可能部分生成的 tar；不自动清理、不重试，不据 SSH 断开判断输运已停止。主代理应先读远端进程、事件目录、`transport-exit-code.txt` 和 CSV，再决定收集恢复。

## 已做验证与边界

命令（退出码 0）：

```powershell
python -B local_runtime/dram-see-v3/transport-fixtures/test_transport_contract.py
```

9 项测试全部通过。覆盖全部 8 组尺寸/方向几何、侧退出、真空发射补偿、64 个唯一种子与旧种子无交集、合法零沉积、元数据/CSV/哈希损坏及条件错误拒绝、16 份旧真实 CSV 的严格解析兼容，以及全链路 mock 运行、重复标签/种子拒绝和失败后的禁止自动重发。旧 CSV 测试只在内存使用明确合成的元数据，没有生成新版真实事件或改写旧材料。

完整测试文件与日志：`local_runtime/dram-see-v3/transport-fixtures/test_transport_contract.py`、`test-output.txt`。mock 完全替代 `connection()` 和 `subprocess.run()`，临时文件局限于 fixture 子目录。本次未验证新的远端运行状态、许可证、真实 30° 事件或 TCAD 源积分；这些由主代理实际串行执行后据原始证据验收。
