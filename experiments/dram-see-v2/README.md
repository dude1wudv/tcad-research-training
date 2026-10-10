# DRAM SEE v2

状态：8个无粒子基准、8个独立事件的16个0/1响应、完整/续算等价性和匹配控制时间步减半均已完成并通过各自检查。最终独立复核27份正式及数值验证归档通过，退出码0；详见[实际报告](report.md)及所链接证据。仍为未校准小样本pilot。

入口：[冻结计划](plan.md)、[操作流程](workflow.md)、[调试日志](journal.md)、`validation/` 独立审查。实际完成程度以原始 manifest、数据审计和最终 report.md 为准。不得把计划或生成 deck 当成已经运行。

模型沿用未校准二维 NMOS+10 fF 理想电容；受控 SN 初始化、100 fF 位线/参考和5 mV裕量是假设，不是真实 DRAM 校准或持久位翻转。0/1同事件配对，不能翻倍独立事件数。v1数据保持原样，未提交/推送。

可复现源：build_case.py、transport.py、event_audit.py、audit.py、run_stage.py、statistics.py。八个正式基准已完成并审计通过；[独立事件设计](stats-design.json)已在首个粒子TCAD响应提交前冻结，每粒子4个种子、每事件配对0/1。完整TCAD归档位于仓库`local_runtime/runs/<run-id>/`，由唯一`scripts/tcad.py`保存；完整操作记录和批日志位于`local_runtime/dram-see-v2/`。本版本中保存CSV/JSON、小型图表和[全部交付材料及归档哈希导航](data/summary/delivery-index.json)，商业原始数据不上传。

5 mV主判据下：alpha存储1为1正确、3临界，存储0全部正确；proton两初态全部正确。每种粒子明确误读均0/4，但零次观察的单侧95%上界仍为52.7%，且alpha临界不能算作正确。详见[完整统计](data/summary/statistics.csv)。已有7套PNG/SVG数据图和2组真实Sentaurus Visual窗口截图；两种图件明确分开标注。
# 接续入口

当前接续事实与恢复步骤见 [takeover.md](takeover.md)，完整操作入口见 [workflow.md](workflow.md)。原有运行、失败证据和未提交改动均保留；以运行索引和原始归档审计为准，不将后台启动或 `COLLECTED` 等同于科研验收。

