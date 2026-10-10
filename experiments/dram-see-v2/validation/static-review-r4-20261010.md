# r4 定向静态复审

2026-10-10。范围为 build_case.py、audit.py、event_audit.py、transport.py、run_stage.py、statistics.py。本 worker 只读取源码并写本记录；未执行 solver、远程连接或动态验收。父代理告知 r4 pilot `20261010T013752Z-v2-pilot-control-l025-b1-r4-6f25f848` 在运行；本记录不判断其结果。请求配置为 gpt-6-astra medium，无独立运行时/OAuth 证明。

## 已落实的修正

- build_case 使用 2.8–2.9 ns 有限斜率 vpre，经 100 ohm rpre 充电，3 ns 将电阻改为 1e20 ohm；不再对 BL 施加 0.5 V 瞬时 Set 或插入 DC 重平衡。WL 初态为 0，SN 于 0.6 ns 释放。
- audit.py:30–35 将 manifest 列出的全部输入分别与 inputs.tar、results.tar 逐文件绑定，覆盖 parameters/deck/源证据/恢复文件等实际列入 manifest 的输入。上一轮“结果参数未绑定输入”的问题已在源码层面修正。
- clean() 拒绝同时间节点电压相差超过 1 µV，导出 circuit-raw.csv 保留原始样点；读出 BL 的 KCL/BE 平衡包含 rpre 电流。
- particles() 重新审计基准，并要求主阈值下正确才运行对应粒子；设计元数据明确同事件两存储位配对、n=6 为小样本 pilot，预登记 2.5/5/10 mV。

## 仍需优先修正

1. **高：批量入口未把复用身份和冻结版本绑定。** run_stage.py:36–38 对任一已有 VERIFIED tag 直接返回旧运行，没有比较本次请求的 length/bit/event/parent/step/mesh。:46 对已有输入目录的比较漏掉 event/source hash。设计虽然在 :106 保存 generator_sha256，particles() 没有强制验证此摘要，也没有核对基准属于相同冻结配置。因此源事件或生成器变化后，旧标签/旧输入可被静默复用。应在返回前比较全部请求身份及事件内容摘要，并核对设计的模型/生成器配置摘要；完整运行与恢复 deck 本来不同，不应直接要求整个 deck 字节相同，而应使用共同物理/电路/初始化配置摘要。发现不同版本时创建新阶段/标签并保持旧记录。

2. **高：恢复兼容性仍不足。** build_case.py:104 的兼容键仍仅含 schema、L、bit、mesh/step、目标电压、Cbl、阈值。Cstore、Cref、温度、有效厚度、预充电阻/时序、初始 WL、模型/电路版本未绑定。旧版但成功的 v2 父运行可通过这些键。建议生成明确的初始化兼容摘要，并保留父输入生成器与几何生成器摘要；恢复时要求一致。audit.py:89 仅比较父 manifest 中摘要字符串；应实际计算父 results.tar 哈希、确认父状态/无粒子/非链式恢复，并要求 copied_sha256 的集合恰好为网格与两份 save。lineage 的 parent_run、time_s 也应与参数和预定保存时刻一致。创建时有部分更强检查，但独立审计不应只依赖历史创建动作。

3. **中：freeze_design() 对八个基准只数 VERIFIED 标签。** :93 不重新审计、未要求具体四栅长×两位组合各一次、未检查八个都正确读出。particles() 的后续对照门槛能保护实际主阈值粒子运行，但“设计冻结时八基准可读且统一”这一宣称仍需由 freeze 阶段实测并检查，而不能从标签计数推出。

4. **中：预充阶段守恒仍缺。** audit 保持积分止于 2.8 ns，读出积分始于 3 ns；现在 SN/BL 在此间的物理变化已可连续求解，应补上预充段 SN KCL/BE 平衡和含 rpre 的 BL 平衡。这不应计入辐射保持损失。重复电压断言已改进，但切换时电流可合法变化，必须审查原始样点，确认 BE 每个非零区间取正确收敛终点。仍需实际完整/恢复对比验证 Load 后 SN 未被钳位、rpre 状态正确及 0.95 ns 各节点一致。

5. **中：源契约与统计汇总仍需落实剩余检查。** event_audit/transport 与首轮摘要相同：conversion_eV_per_pair、schema、converted event ID、launch_position 尚未核验；本地 source_sha256 与安装二进制的编译来源仍需现有构建记录绑定。audit 对正 Q 应显式要求源证据。statistics 仍仅接收类别列表，最终汇总器必须校验设计事件唯一性、成功审计及每位分母，并在各阈值分别核验匹配对照可读；主阈值正确不保证 10 mV 阈值正确。失败/未完成样本单列，n=6 仅称 pilot，不能把同事件两位当成 12 个独立事件。

6. **低：decoded_bit 仍硬编码 5 mV。** 当前主阈值一致；阈值敏感性报告必须从 D/M 重新分类，不能复用该字段。电容/时刻等硬编码应与冻结参数一致或显式验证。

## 验收边界

这些是批量和审计入口契约问题，不要求因此打断正在运行的独立完整 r4 pilot。单次 pilot 成功仍不证明四栅长统一初态、两位读出矩阵或独立事件统计全部完成。动态复验待原始成功归档后进行；文档、数据图、真实截图和阈值敏感性产物不在本次源码审阅中验收。

## 本次源码摘要

```text
build_case.py 4e7298a2d06aedc792055bc48243980228772b97f9416a395f4c33095b50ff2f
audit.py 46e654040139b9f37139a7bad6d2083fa785e61ce8b6bde9987c8fbd0a2964b5
event_audit.py d586ca18827148acbd99cfdc0616b963329949f540b74789ff28ac24160724ca
transport.py 5dcb7adcc8bd19c3fdd7ff0f087f1a9d97a13e6810991b3082e33219eb9b7ecb
run_stage.py a2dec01e7662fb853ae84a9e02f47bdaab3db0f24635961dd479317accee1318
statistics.py ce11c19c21dbcaf5cfd4dc8fe740965ab1f4207a7f84871b3a3cecc4de7580a1
```
