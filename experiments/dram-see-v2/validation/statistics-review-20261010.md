# 汇总、统计与绘图独立审阅

范围：summarize.py、statistics.py、plot_results.py、run_stage.py。执行 `python -B experiments/dram-see-v2/validation/check_statistics.py`，退出 0，101 项纯分析检查通过。仅 AST 加载纯函数，避免导入绘图/汇总入口的目录创建、重导出或运行器副作用。测试类别是明确的合成测试输入，不是实验结果。没有运行 solver、读取活动会话或改动业务源码；仅写 validation。

## 必须修正的绘图问题

`statistics.wilson(0,6)` 返回下界 `2.7755575615628914e-17`、上界 `0.3903342879021653`。plot_results.statistics 以 `v-lo` 构造误差条，此时 v=0，得到负长度 `−2.7755575615628914e-17`，不满足 Matplotlib errorbar 的非负误差长度要求。零误读是计划中的正常结果，不能依赖它不出现。建议 Wilson 的 k=0 下界显式置 0、k=n 上界显式置 1，或只对舍入量级的负 yerr 截零。数学公式本身正确；本次没有实际运行 Matplotlib 渲染，因此这是由实测数值和绘图调用契约共同定位的阻断，不冒称已做图形回归。

## 已核实的分母语义

- summarize 在设计入口拒绝重复 particle/seed，且进一步要求全设计 seed 唯一；当前 freeze_design 的 alpha/proton seed 区间不重叠。
- 每个设计事件只生成一条 events 行；各位分别取一次分类，paired_any 只在同事件两位齐备时生成一个分类。因此配对不会被当成两次独立入射。
- 未审计成功的运行没有分类，不会默认成为正确或零沉积；paired_any 缺少一位时整对记作缺失。即使已完成一位为误读，整对仍保守标为缺失，这会损失部分已知信息，但不会制造乐观区间。
- denominator([],6) 输出 missing=6、确定性范围 [0,1]，所有概率区间为 null。0至5个已完成/计划6个的测试全部确认不输出 Wilson/exact。
- 完整6个且零误读时 exact 单侧95%上界为 0.39303776899708276；并非“误读率为零”的总体结论。
- 完整组对 definite 与 flip-or-uncertain 分别给区间；临界值 M=±epsilon 分类为 uncertain，三阈值边界纯测试通过。
- summarize 使用实际审计的匹配基准 margin，要求所有设计阈值均正确后才纳入粒子响应。freeze_design 也要求明确四栅长×两位八个组合，且在三个阈值全部合格。
- 绘图对不完整分层显示 completed/planned、missing 和 No probability interval，没有画伪造的0误读点。

## 批量与汇总契约剩余问题

1. **中高：汇总缺少事件内容的交叉绑定。** summarize 分别验证当前 event.json 与归档内源，但未比较当前 event.json/steps/events 哈希与对应 TCAD 的 source_evidence_sha256。同 seed/条件下当前源文件被替换时，event-index 的 Q/源哈希可与 responses 对应归档不一致。应明确要求元数据和两CSV摘要与归档冻结源一致；不能只比较 seed/particle/bit/parent。

2. **中：设计总数一致性缺少断言。** 统计分母取 len(group)，没有断言它等于设计 n_per_particle、independent_event_count/2；也未检查 label 唯一、每个 paired_bits==[0,1]、两粒子组完整、固定 L/E/angle 等全部条件。当前 freeze_design 会生成正确清单，但独立汇总应拒绝缺项清单，防止 n=6 声明与更小实际分母同时存在而仍被称为完整。设计摘要被记录，但没有单独冻结摘要锚点来判断设计是否改写。

3. **中：summarize 不验证响应/基准生成器等于冻结设计。** run_stage particles 做了当前/基准生成器检查，但独立汇总只依赖恢复 contract 和 ledger 命名。建议再核对归档 generator-sha256、design.baseline_run_ids、合同版本，尤其旧 VERIFIED 标签复用的路径。正常当前控制流程可降低风险，不能替代独立汇总的输入契约。

4. **低：阈值图的“预登记事件索引”会压缩缺失。** 图中按 completed group 排序后用 arange(len(group))；若中间事件未完成，后续事件的横轴位置被前移。应使用冻结设计 replicate/index，或将横轴改称已完成样本序号，并显示 seed，以免不完整数据看似连续完成。

5. **低：denominator 对未完成组没有核验类别集合。** 完整时 summarize_classes 会拒绝非法类别；部分组中未知类别会增加 completed_n 而不进入任何计数。当前 classification 只产生合法枚举，因此未造成已知真实结果问题；建议在 denominator 入口始终验证枚举，使 completed==correct+flip+uncertain 成为可观察契约。

6. **范围提醒：图与数据尚未做真实产物验收。** plot_results 读取派生 CSV，没有重新绑定 CSV 哈希到归档；figure-evidence 记录归档/PNG，但不记录所读 CSV/statistics.json 摘要。可在出图时补记所有实际输入摘要。零沉积事件的 generated/source error 默认0应说明“未施加源”，不应解读为测得的辐射积分零误差。当前未完成正式8基准和粒子组，不在本记录中宣称三项目标完成。

## 可复核结果

`check_statistics.py` 使用 Wilson score 二次方程根独立核对 n=1..6 全部 k/u 合法组合，检查 exact 的 `(1-upper)**n=0.05`，并检查缺失组和三阈值边界。结果和源码摘要见 `check_statistics.json`。

```text
summarize.py 006f86eaa0f898c967d311ba0d8c995346de7b0b4ec7f28b234f4a24b12f693e
statistics.py ce11c19c21dbcaf5cfd4dc8fe740965ab1f4207a7f84871b3a3cecc4de7580a1
plot_results.py 9bbccbee06685df50efc70b6fa6d8dcc128a2b3f32d24b248938a222e81dd4e6
run_stage.py 95e9a4ca6f4e9843c8e587fc0177cb72866ed4a5ec4b8e21b0a94ed777184a48
```

模型请求为 gpt-6-astra medium；运行时与 OAuth 路由未取得独立证明。现阶段结论为统计纯函数和主要分母行为通过审阅，存在上述绘图及绑定问题，尚非完整端到端统计验收。
