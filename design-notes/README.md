# TCAD 设计流程经验

用于复用本项目**实际执行过**的工程方法；不把操作测试写成物理模型已验证，也不代替具体实验记录。

## 从这里开始

- [实验方案](../experiments/plan.md)：不绑定器件的对照、迭代、评价指标和题目接入流程。
- [报告提纲](../reports/outline.md)：章节与证据要求；正式器件内容等老师下发题目后确定。
- [仿真与桌面操作经验](workflow.md)：流程、故障定位、证据标准和新任务检查表。
- [工程操作入口](../README.txt)：工作区布局、连接方式和运行约束。
- [PN 电场桌面测试](../tests/pn-field-desktop/README.txt)：完整复现步骤与参数。
- [环境初始化记录](../records/initialization.txt)：镜像部署、SSH 和许可证维护事件。

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
- 题目确定后，再加入该器件的物理假设、模型选择、校准和敏感性分析经验。
