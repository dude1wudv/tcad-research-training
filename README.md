# TCAD 科研训练与 DRAM 单粒子效应评估

[![Repository](https://img.shields.io/badge/repository-private-lightgrey)](https://github.com/dude1wudv/tcad-research-training)
[![Branch](https://img.shields.io/badge/branch-main-1f883d)](https://github.com/dude1wudv/tcad-research-training/tree/main)

> 私有仓库：<https://github.com/dude1wudv/tcad-research-training>

本仓库是一个面向 TCAD 科研训练和课程项目的可追溯工程工作区，主线为：

> **AI 辅助 Geant4/TCAD 多特征尺寸 DRAM 单粒子效应评估、拟合、外推与验证。**

项目设计题目为《AI辅助下的存储器单粒子效应评估》，指导教师为李洋。仓库同时保留环境资格测试、操作经验、失败复盘、实验脚本、审核后的结果摘要和报告材料。所有科研结论都必须以对应实验的冻结计划、原始证据和适用边界为准。

## 仓库简介

仓库解决的问题不是“运行一个脚本并生成一张图”，而是建立一条可检查、可恢复、可复现的 TCAD 研究流程：

1. 记录课程要求、研究问题、模型假设和冻结参数；
2. 用 Geant4 生成粒子输运/能量沉积信息，并记录事件、种子和输入哈希；
3. 将经过检查的事件信息传递到 TCAD，执行器件或混合模式求解；
4. 从端电流、节点电压、收集电荷等定义明确的观测量中提取指标；
5. 保存运行索引、源文件哈希、图表、统计、失败记录和验证边界；
6. 在完成真实数据和独立验证后，再讨论拟合、外推或 AI 辅助效率。

AI 在本项目中用于受约束的参数整理、工况生成、分析和交互辅助；它不能替代物理建模、单位检查、教师审核、数值收敛判断或科研结论验收。

## 当前状态

- 课程题目已经接入，课程大纲提取稿位于 [`docs/course-project-syllabus.md`](docs/course-project-syllabus.md)。
- 课程执行方案和任务卡位于 [`experiments/plan.md`](experiments/plan.md)，阶段路线位于 [`experiments/roadmap.md`](experiments/roadmap.md)。
- [`experiments/dram-see-v1/`](experiments/dram-see-v1/) 已完成第一版探索性 Geant4→TCAD 链路、16 点工况矩阵和限定条件下的域内/域外预测验证。
- [`experiments/dram-see-v2/`](experiments/dram-see-v2/) 已保存 0/1 配对响应、基准和续算等价性、匹配控制时间步检查及独立复核材料。
- [`experiments/dram-readout-offset-d1/`](experiments/dram-readout-offset-d1/) 保存读出偏移诊断、参考支路和恢复证据。
- [`tests/vdmos-tid-training/`](tests/vdmos-tid-training/) 是独立的 VDMOS 总剂量训练工程，仅用于方法训练，不能替代 DRAM 单粒子效应课程成果。
- 当前模型和探索结果仍是**未校准的小样本工程验证**：不能直接代表实验室提供的 DRAM 模型、商业工艺节点、真实位翻转率、辐射截面或器件可靠性。
- 正式课程交付仍依赖实验室模型与参数来源、物理校准、统计重复、实际成员分工、教师审核和最终报告/演示。

## 快速开始

### 获取仓库

这是私有 GitHub 仓库，克隆或拉取需要已获授权的 GitHub 身份验证。推荐使用 HTTPS：

```bash
git clone https://github.com/dude1wudv/tcad-research-training.git
cd tcad-research-training
git status
```

也可以在已有工作区中更新：

```bash
git pull --ff-only origin main
```

不要把密码、访问令牌、私钥、许可证文件或 `local_runtime/` 中的连接配置提交到仓库。

### 环境前提

- Windows 主机用于工程管理、Git 和 VMware；
- 隔离的 Sentaurus VM 用于 Linux 原生求解；
- Geant4、Sentaurus、VMware 及服务器资源按实际授权和实验计划提供；
- Python 脚本优先使用标准库，具体分析脚本的额外依赖以目标实验文档为准；
- `local_runtime/`、VM、完整 TDR/PLT、许可证和受限商业资料不入库。

### 日常运行入口

在 Windows PowerShell 中从仓库根目录执行：

```powershell
cd E:/TCAD-Workspace/tcad-research-training
pwsh -File scripts/start-vm.ps1
python scripts/tcad.py doctor
python scripts/tcad.py shell
python scripts/tcad.py run simulation/qualification/pn-diode
```

其中 PN diode 只是环境资格测试，不是课程的 DRAM 结果。首次启动服务若权限不足，只对 `start-vm.ps1` 使用管理员 PowerShell 重试；不要修改许可证、关闭主机校验或把隔离 VM 暴露为公网服务。

### 按实验复现

每个实验目录都有独立的计划、流程、运行索引和验证边界。建议按以下顺序阅读：

1. 先读实验目录的 `README.md`、`plan.md` 和 `workflow.md`；
2. 核对当前 Git commit、输入版本、源文件哈希、运行索引和是否存在活动作业；
3. 只使用目标实验指定的入口和现有唯一 runner，不盲目重新提交已完成或状态不明的运行；
4. 运行后检查退出码、日志、manifest、收敛、单位、偏置、守恒和图件来源；
5. 分析脚本只能读取已完成的固定归档，失败、缺失、临界和未验证项必须单独保留。

DRAM 实验的入口如下：

- [第一版探索实验](experiments/dram-see-v1/README.md)
- [第二版配对事件实验](experiments/dram-see-v2/README.md)
- [读出偏移诊断实验](experiments/dram-readout-offset-d1/README.md)

## 研究与文档入口

| 入口 | 内容 |
|---|---|
| [课程大纲](docs/course-project-syllabus.md) | 项目设计题目、课程要求、资源说明和评分比例 |
| [实验方案](experiments/plan.md) | 研究问题、冻结口径、质量门槛、课程任务卡和交付路线 |
| [实施路线](experiments/roadmap.md) | R1–R8 要求映射、Geant4→TCAD 接口草案和当前缺口 |
| [报告提纲](reports/outline.md) | 报告章节、证据分配、拟合/外推验证和答辩材料规划 |
| [设计流程](design-notes/README.md) | 工作流、取证、协作、故障定位和安全边界 |
| [第一版实验报告](experiments/dram-see-v1/report.md) | 第一版方法、结果、限制和下一版顺序 |
| [第二版实验报告](experiments/dram-see-v2/report.md) | 配对事件、统计、验证和当前解释边界 |
| [VDMOS 训练工程](tests/vdmos-tid-training/README.md) | 独立的总剂量训练材料和可迁移方法 |
| [环境记录](records/environment-qualification.json) | 已审核的环境基线和证据哈希 |
| [TCAD runner](scripts/tcad.py) | 受约束的远程执行、归档和结果收集入口 |

## 仓库结构

```text
AGENTS.md                         仓库级协作、验收和安全规范
docs/                             课程大纲及来源指纹
config/                           无秘密的连接配置示例
design-notes/                     流程、排障、协作和取证经验
experiments/                      课程方案、DRAM 实验和审核后的结果
reports/                          报告提纲及正式报告规划
records/                          环境与初始化记录
scripts/tcad.py                   TCAD 唯一执行与归档入口
simulation/qualification/        PN 环境资格测试
tests/                            PN/VDMOS 训练工程和回归材料
local_runtime/                    被忽略的连接配置、日志和原始运行结果
```

`local_runtime/`、VM 和本机部署材料位于仓库外或被 Git 忽略。仓库只保存可以审阅、共享和追溯的输入、脚本、小型汇总、图件、来源哈希和报告材料。

## 复现与证据原则

- 每次运行冻结输入，记录 Git commit、UTC run ID、源文件/参数哈希、工具版本、命令、退出码和原始输出位置。
- `COLLECTED` 或归档成功只表示执行/回传完成，不等于物理有效、数值收敛或科学结论成立。
- 真实结果、人工样例、合成数据、计划参数和未验证预测必须明确区分。
- 同一粒子事件的 0/1 配对响应不增加独立事件数；失败、临界或缺失样本不能静默计入正确结果。
- 不能把二维简化模型、理想电容或单次/小样本仿真外推为商业 DRAM 性能、真实辐射截面或抗辐射等级。
- 发生 SSH 断开、超时或状态不明时，先只读检查远端目录、进程、锁、manifest 和日志，再决定是否恢复；禁止盲目重发或覆盖。

## Release 与版本发布

### 当前发布状态

截至当前 `main` 分支快照，仓库**尚未声明正式的稳定版或课程交付版 GitHub Release**。探索实验、训练工程和课程文档可以随提交演进；具体结果应引用对应 commit、实验 run ID 和证据索引，而不是只引用 `main`。

- [GitHub Releases](https://github.com/dude1wudv/tcad-research-training/releases)：查看已发布版本；
- [main 分支](https://github.com/dude1wudv/tcad-research-training/tree/main)：查看当前开发快照；
- [提交记录](https://github.com/dude1wudv/tcad-research-training/commits/main)：查看文档、脚本和证据的变更历史。

### 版本命名建议

正式发布时使用语义化版本标签：

```text
v<主版本>.<次版本>.<修订版本>
```

建议约定：

- `v0.x.y`：研究开发快照、探索实验或尚未完成课程审核的可复现归档；
- `v1.0.0`：经过教师确认、模型/参数来源明确、核心实验和独立验证完成的首个课程交付版本；
- 修订版只修正文档、索引或不改变实验输入/结论的归档问题；改变模型、参数、判据、数据划分或结果时提升版本并保留旧版本。

### 发布前检查

创建 GitHub Release 前至少确认：

1. 工作区干净，提交已推送，发布标签指向明确 commit；
2. `README.md`、实验 `README.md`、计划、报告和证据索引中的状态互相一致；
3. 输入、源代码、运行 ID、哈希、图件和报告可以相互追溯；
4. 失败、未验证项、模型校准缺口和适用边界没有被隐藏；
5. 不包含秘密、私钥、许可证、受限工具资料、VM 镜像或未经审核的大型原始归档；
6. Release notes 写清变更、验证命令、已知限制和不应推出的结论。

示例命令（仅在完成审核并获得发布授权后执行）：

```bash
git switch main
git pull --ff-only origin main
git tag -a v0.1.0 -m "Research snapshot v0.1.0"
git push origin v0.1.0
```

GitHub Release 页面中的说明应链接到对应实验报告、交付索引、运行索引和验证记录。不要把创建 tag 或 Release 本身表述为实验通过或教师批准。

## 协作与安全

- 复杂任务先阅读 [`design-notes/agent-workflow.md`](design-notes/agent-workflow.md)；运行、取证和 Git 操作先阅读 [`design-notes/workflow.md`](design-notes/workflow.md)。
- 每个文件同时只有一个写入者；共享求解器、队列和运行索引必须有唯一调度者。
- 连接配置只按 [`config/connection.example.json`](config/connection.example.json) 在本机 `local_runtime/` 中配置，不提交真实地址、密码或密钥。
- 不安装来源不明的 AI 插件，不读取或修改许可证绕过授权，不关闭 SSH 主机校验。
- 本仓库目前没有声明开源许可证，且为私有仓库；未经授权不得公开转载、再分发或将结果用于商业器件声明。

## 参考仓库

以下仓库仅用于比较工程组织和方法记录，不复制其中的数据、许可证、机器地址或自动调参策略：

- <https://github.com/dude1wudv/vdmos-tid-research>
- <https://github.com/dude1wudv/st-tid-data-simulation>
