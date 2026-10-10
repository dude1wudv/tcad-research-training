# DRAM读出偏移诊断D1

已完成9/9冻结物理工况，生产与独立原始PLT复核通过；另保留1次未进入瞬态的解析失败。有效solver时间3548.78 s，Newton重试0。原v1/v2及索引归档536文件哈希不变，原pilot与2.5/5/10 mV判据未改。新增独立粒子事件为0。

入口：[结论与解释](interpretation.md)、[数值报告](report.md)、[操作与恢复](workflow.md)、[日志](journal.md)、[独立验收](validation/independent-final.json)、[交付索引](delivery-index.json)。

有效设计为[design-r4.json](design-r4.json)。r2仅修tag，r3仅修第二器件实例名；旧输入/源码/失败证据全部保留。r4仅规定最后同run的中断恢复证据：原执行SSH退出码未知，execution.log流副本缺末尾标记，完整器件日志/远端exit0/全部输出/原输入和runner哈希与原科学门槛通过。原run未重跑，原日志未补写。

全部九项已VERIFIED，不再次freeze或盲目重发。只需重建派生分析时，在仓库根目录执行：

```powershell
python -B experiments/dram-readout-offset-d1/curve_metrics.py
local_runtime/vdmos-analysis-venv/Scripts/python.exe -B experiments/dram-readout-offset-d1/report.py
```

report.py优先读取r4，图01–04保存PNG/SVG、CSV与来源哈希：SN传递/偏移、字线/端口电流/读出、四端积分/守恒、理想/离线/物理参考及原alpha曲线。原alpha为历史粒子证据，不计入本批九项。图件均为DATA PLOT，已目视核验。真实SVisual截图与native导出另存[本批native目录](figures/native/20261010T082741Z-rodiag1-matched-ref-r3-99f3de31/)，显示4 ns电场，不能冒充读出曲线。

完整raw输入、日志、PLT/TDR、归档与哈希可从delivery-index.json定位；运行索引为local_runtime/dram-readout-offset-d1/ledger.json。失败和收集恢复记录没有混入独立事件统计。模型未校准，不代表真实感放、实际写入、辐射截面或商业可靠性。
