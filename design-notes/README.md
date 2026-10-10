# TCAD 设计流程经验

用于复用本项目**实际执行过**的工程方法；不把操作测试写成物理模型已验证，也不代替具体实验记录。

## 从这里开始

- [长任务协作与交接](agent-workflow.md)：复杂任务的委派契约、单写者/单调度者、证据回传、主代理理解验收和压缩恢复；按需读取。
- [课程大纲](../docs/course-project-syllabus.md)：已下发题目原文、课程要求与评分。
- [实验方案](../experiments/plan.md)：DRAM 单粒子效应任务定义、冻结口径和可选 AI 对照。
- [实施路线](../experiments/roadmap.md)：Geant4→TCAD 最小闭环、多尺寸扫描、预测验证与近期任务。
- [报告提纲](../reports/outline.md)：项目设计报告、作品演示与证据要求；具体结构和参数待来源核实。
- [仿真与桌面操作经验](workflow.md)：流程、故障定位、证据标准、执行安全和Git授权；运行、取证及Git操作前读取。
- [工程操作入口](../README.txt)：工作区布局、连接方式和运行约束。
- [PN 电场桌面测试](../tests/pn-field-desktop/README.txt)：完整复现步骤与参数。
- [VDMOS 总剂量训练](../tests/vdmos-tid-training/README.md)：既有训练记录与方法边界，不能替代正式 DRAM 单粒子效应验证。
- [环境初始化记录](../records/initialization.txt)：镜像部署、SSH 和许可证维护事件。
- [混合模式瞬态取证](mixedmode-evidence.md)：第一版 DRAM 实测得到的输出命名、状态续算、离散守恒与源事件绑定经验；器件仍未校准。

## 直接复用现有实现

| 用途 | 唯一实现入口 |
|---|---|
| 启动 VM、发现地址、检查环境 | [start-vm.ps1](../scripts/start-vm.ps1) |
| 探测、SSH、顺序求解与结果归档 | [tcad.py](../scripts/tcad.py) |
| 首次配置客户机网络及 SSH | [guest-bootstrap.sh](../scripts/guest-bootstrap.sh) |
| 可复制的 PN 基准 | [qualification/pn-diode](../simulation/qualification/pn-diode/) |
| 两参数电场测试模型 | [测试模型](../tests/pn-field-desktop/model/) |
| 原生电场绘图 | [field.tcl](../tests/pn-field-desktop/field.tcl) |
| 客户机桌面输入与截图 | [desktop.py](../tests/pn-field-desktop/desktop.py) |

## 如何积累经验

每项新经验记录：**场景 → 可观察的问题 → 原因证据 → 处理 → 验证 → 适用边界**。

- 指向具体脚本、测试目录、run ID 或提交；不另存一份会失去同步的脚本。
- 明确区分已实测、推断、待验证；失败及恢复过程都保留。
- 通用方法放这里；某一次运行的数值和截图放对应测试/实验目录。
- 不保存密码、私钥、许可证或商业工具文档副本。
- 正式 DRAM 模型实测后，再加入该器件的物理假设、模型选择、校准和敏感性分析经验；设计草案仍放在 `experiments/`。
