TCAD 科研训练工作区
===================
研究主线：AI 辅助 Geant4/TCAD 多特征尺寸 DRAM 单粒子效应评估、拟合、外推与验证。
项目设计题目：AI辅助下的存储器单粒子效应评估（指导教师：李洋）。
题目原文提取稿：docs/course-project-syllabus.md；题目要点与任务卡：experiments/plan.md 第 0.1、10 节。
实施路线与近期任务：experiments/roadmap.md；报告与作品演示：reports/outline.md。
“多特征尺寸”来自大纲文件名及基本要求；封面最终题名由指导教师确认。
不默认采用 PN 结，不继承旧项目的器件、辐照剂量或结论。
私有仓库：https://github.com/dude1wudv/tcad-research-training
实验方案：experiments/plan.md；报告提纲：reports/outline.md。

当前状态（2026-10-09）
---------------------
课程题目已接入；用户授权的第一版探索实验已完成真实 Geant4→TCAD 16 点矩阵，
含四种栅长、两种粒子、两个方向、匹配无粒子对照及域内/域外预测验证。
报告、图表、失败复盘与复现入口：experiments/dram-see-v1/README.md。
代表点网格/时间步细化已通过；最终数值状态以该实验报告为准。
模型是未校准二维 NMOS + 理想电容的 1T1C，不能当成实验室 DRAM 模型或商业工艺节点。
仍需实验室模型/参数来源、物理校准、独立事件统计及课程审核与正式交付；
已有 PN/VDMOS 材料仅复用操作经验，没有混入本次数据。
项目设计评分：导师评价20%、项目报告20%、答辩或作品演示60%；
原“科研训练”课程的字数、阅读量及60%/40%评分要求单列，仅在确认兼报时适用。

设计参考：
https://github.com/dude1wudv/vdmos-tid-research
https://github.com/dude1wudv/st-tid-data-simulation
沿用真实 Sentaurus deck、原始结果与报告分离、来源哈希、单核求解和串行依赖；
不复制旧项目数据、许可证、机器地址或自动调参策略。

工作区分层
----------
E:/TCAD-Workspace/tcad-research-training/  Git 工程源文件
E:/TCAD-Workspace/machines/sentaurus/     独立 VM，绝不入库
E:/TCAD-Workspace/local/                 本机部署材料，绝不入库
原始 E:/T2024-09/ 镜像保留，不直接启动或写入。
为保持原有 TCAD 环境兼容性，保留 VM 硬件身份；禁止同时启动源镜像与此副本。

仓库结构
--------
AGENTS.md                             仓库级 Agent 操作、验收和安全规范
docs/course-project-syllabus.md       项目设计课程大纲原文提取及来源指纹
scripts/tcad.py                        Python 标准库运行器
simulation/qualification/pn-diode/      实际 SDE/SDevice 环境基准
config/connection.example.json         无秘密的连接配置示例
records/                               人工审核后的环境及实验记录
design-notes/                          可复用设计流程、排障经验及验证边界（入口 README.md）
experiments/                           已下发题目的执行方案及冻结定义
experiments/roadmap.md                 核心需求映射、阶段安排与近期任务
reports/                               报告提纲及后续正式报告
local_runtime/                         被忽略的连接配置、主机公钥、日志和原始结果

日常操作（Windows PowerShell）
------------------------------
1. cd E:/TCAD-Workspace/tcad-research-training
2. pwsh -File scripts/start-vm.ps1
3. python scripts/tcad.py doctor
4. python scripts/tcad.py shell
5. python scripts/tcad.py run simulation/qualification/pn-diode
首次启动服务若权限不足，仅以管理员 PowerShell 重试 start-vm.ps1。
也可直接在 VMware 打开 machines/sentaurus/Sentaurus2019.vmx；不要打开源镜像。
guest-bootstrap.sh 针对此镜像的 ens33，由 root 在可信控制台执行：
bash guest-bootstrap.sh tcad /path/to/public-key.pub
它只安装公钥、启用自动网络/SSH 和设置科研目录，不保存密码或授予 sudo。

连接不依赖猜测 IP：每次通过该 VM 的 VMware Tools 查询当前私网地址。
SSH 仅使用专用密钥，严格核验固定 HostKeyAlias 的公钥；连接保活 15 秒。
更换 VM 必须通过可信 VMware 控制台重新核实主机指纹，禁止关闭主机校验。
CentOS 7 已停止维护：仅限隔离科研环境、NAT，不配置公网端口转发。
不将 VM 用作互联网服务，不升级其中 TCAD/系统包以免破坏兼容性。
Sentaurus 版本探测不等于许可证有效；只有实际求解成功才证明当次 checkout 可用。

真实工程流程
------------
题目/文献与单位约定 -> 器件结构与接触 -> 掺杂/网格 -> 平衡解 -> 偏压 ramp
-> 基线标定 -> 网格/步长敏感性 -> 单因素扫描 -> 参数提取 -> 图件与科研报告。
题目范围与器件定义冻结后再建立正式工程，不以环境二极管冒充作业结果。
正式 Workbench 工程需保留原生项目文件、参数表、节点关系和对应 deck；
运行器只接受已解析的命令文件，不自行替换 @node@ 等 Workbench 占位符。

每次运行冻结全部项目输入并记录 SHA-256、Git commit、准确工具参数、UTC run ID。
远端独立目录禁止覆盖；项目范围 flock 独占锁防止误发并行求解；
SDevice --threads 1 --exit-on-failure，CPU affinity 固定，OpenMP/BLAS 单线程。
该锁只协调本仓库运行器，不声称约束手工启动或其他仓库的求解器。
按步骤顺序执行并核验产物，失败立即停止，保留日志、退出码及可获取的输出。
SSH 断开后禁止自动重复提交；先检查远端目录与进程，避免重复计算。
manifest.json 的 COLLECTED 只代表执行及归档成功，不代表科学有效。
正式数据须人工检查：收敛、端偏压、接触符号、单位、温度、守恒、网格依赖、模型范围。
不得把未收敛结果、插值/合成曲线或未知结构参数表述为真实实验结果。

安全与协作
----------
connection.json 只保存在 local_runtime，按 config/connection.example.json 配置。
不提交密码、私钥、许可证、VM、大型 .tdr/.plt 或第三方受限安装文件。
私钥位于 Windows 用户 .ssh，不复制给 VM；VM 只安装公钥。
仅将审核后的小型汇总、图表与来源清单提升到版本控制。
不安装不明来源 AI 插件；优先标准 CLI 和版本化脚本，所有物理参数由人确认。

初始化验收
----------
records/environment-qualification.json 保存已审核的环境基线和证据哈希。
真实 PN 基准已经完成 SDE -> snmesh -> SDevice，0.5 V 偏压收敛，单线程求解，
运行与归档退出码均为 0；原始结果仅保存在 local_runtime。
验收由 openai-codex/gpt-6-astra:medium 执行，不以环境基准作科研结论。
镜像遗留的 locale、缺失 devtoolset profile 和旧 contact API 警告如实记录，
本次未通过修改商业工具/许可或压制日志掩盖警告。
