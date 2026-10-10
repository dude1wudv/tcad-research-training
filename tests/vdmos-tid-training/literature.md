# 文献学习与参数来源矩阵

检索：VDMOS total ionizing dose TCAD oxide charge interface traps；VDMOS Sentaurus doping；VDMOS 总剂量 辐照 击穿。以下为实际打开并核对的材料，不虚构中英文各10篇已完成阅读。论文与工具教程分开计数，摘要不冒充全文。

| ID | 已核实来源、阅读范围 | 学到并采用的内容 | 不可直接迁移的内容 |
|---|---|---|---|
| R1 | 高博等，《国产星用VDMOS器件总剂量辐射损伤效应研究》，物理学报61(17),176107,2012，[DOI](https://doi.org/10.7498/aps.61.176107)，[全文](https://wulixb.iphy.ac.cn/cn/article/pdf/preview/10.7498/aps.61.176107.pdf)。原PDF中文提取乱码，实际渲染并检查第2–3页 | 第2页图1：上部P+body/N+source、栅、N-外延、底部N+；表3：BV在VGS=0按漏电流定义；第3页：正氧化电荷与界面电荷竞争，Vth可能回漂，BV不必明显变化 | 实验为400/500V型号、Co60、2000Gy(Si)及追加50%、栅偏12V/漏偏320或400V、100℃168h退火，不能当本次0–60krad(SiO2)校准；1mA整芯片BV条件不能直接当二维每µm电流 |
| R2 | Jim Schwank，Radiation Effects in MOS Oxides，SAND2007-3309C，[Sandia/OSTI原文](https://www.osti.gov/servlets/purl/1147853)。读取第1–6页机制和公式、场氧影响章节；报告编号证明2007，不能凭下载名认作2008 | 第3页Nh=f(Eox)g0D tox，g0=8.1e12 cm^-3/rad；俘获率工艺依赖；正电荷致NMOS负Vth漂移；上半带acceptor、下半带donor；场氧/终端同样重要 | 产额、俘获率、退火与偏置依赖不能用一个通用斜率预测所有VDMOS；本次用Y=0.6和f=0.1只是明确的训练选择 |
| R3 | Ali Khoshnoud、Javad Yavandhassani，Modeling of total ionizing dose (TID) effects on the nonuniform distribution of Si/SiO2 interface trap energy states in MOS devices，Scientific Reports15,17082,2025，[全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC12084595/)，[DOI](https://doi.org/10.1038/s41598-025-01325-3)。阅读Introduction、Modeling approach、表1–2；核对生成常数和Nh=G0DY原公式图 | TID/位移损伤/SEE必须区分；界面态能量非均匀、质子过程和俘获截面会影响结果；不能只设固定氧化电荷就声称完整辐照模型 | IRF620最高7.8Mrad与DCIV拟合不是本训练工艺；没有实现其QT/TE/TAT和EAD全模型，本次两离散能级是简化 |
| R4 | Mourad Bella、Mehdi Ghoumazi，I_V Characteristic of Vertical Double Diffused Metal Oxide Semiconductor (VDMOS) Power Transistor Using Silvaco-TCAD，European Journal of Electrical Engineering24(4):221–225,2022，[全文](https://www.iieta.org/download/file/fid/82487)，[DOI](https://doi.org/10.18280/ejee.240407)。读取全文 | 双扩散形成沟道、底部漏极、固定VDS扫描VGS；栅功函数/氧厚/沟道长度影响阈值，不能混进剂量单因素研究 | 使用Silvaco而非本版本Sentaurus；文中氧厚0.5–2nm及implant dose写cm^-3等表述不直接采信，需结合工艺/单位核实。本文不是完整可复现尺寸来源 |
| T1 | [Sentaurus Training SDE2](https://ghzphy.github.io/Sentaurus_Training/sde/sde_2.html)，阅读区域/布尔/接触；[SDE3](https://ghzphy.github.io/Sentaurus_Training/sde/sde_3.html)，阅读高斯掺杂定义；[SDE4](https://ghzphy.github.io/Sentaurus_Training/sde/sde_4.html)，阅读网格定义 | create-rectangle、set-contact、高斯PeakVal/ValueAtDepth/Depth/Factor、界面MaxLenInt和掺杂MaxTransDiff；按本训练几何重新实现 | 教程SOI横向MOS不是VDMOS，不能照抄结构或电极；版权工具资料仅链接/简要方法，不复制受限全文入库 |
| T2 | [Sentaurus Device13: Traps](https://ghzphy.github.io/Sentaurus_Training/sd/sd_13.html)，阅读13.1–13.3、13.5–13.9 | FixedCharge的Conc符号；Level接口Conc=cm^-2，分布态Conc=cm^-2eV^-1；Donor/Acceptor的充放电；输出e/hInterfaceTrappedCharge | 固定电荷没有复合，不能代替可充放电界面态；体等效界面字段与网格间距有关，不能据此反推面浓度；教程13.7注释与13.1类型描述冲突，以13.1及实际工具解析为准 |
| T3 | [Sentaurus Device11: Breakdown](https://ghzphy.github.io/Sentaurus_Training/sd/sd_11.html)，阅读方法比较、IIC、外接电阻和电流边界方法；核对安装版BVmethods/BV_des.cmd | 完整载流子雪崩+外接电阻、AvalDerivatives、BreakCriteria；作图/提取必须用InnerVoltage，不用电源电压 | ABA只是近似；不能把未收敛终点当BV；自选电流阈值须披露，不把上限当测得值 |

## 受限来源与失败证据

Raul Mendoza Macias，Design and Optimization of Superjunction Vertical DMOS Power Transistors using Sentaurus Device Simulation，UCF硕士论文2016，[馆藏页](https://stars.library.ucf.edu/etd/5137/)已读取摘要。全文下载接口返回HTTP403，未声称读过全文/尺寸表，不从摘要臆造掺杂。未采用其超结设计或26%降阻结论。

开放论文原件与渲染页仅保存在`local_runtime/vdmos-tid-training/references/`。R1 PDF SHA256=`060c35e833f8ee4cc4a75c59a188038cbcf5ef714346d5cf95ffaa88bfe17c10`；R2 PDF SHA256=`fa9efe50e0a85f06682ffd7ef86790f58e4c16ff6a977f43af4e6810d8e01c91`。没有上传商业工具手册、许可证或私钥。

## 可迁移的最小设计决策

1. 结构来源证明拓扑，不等于参数来源完整：本次几何/掺杂是可解释的训练假设。
2. 剂量介质+g0+氧厚+有效产额/俘获率→正电荷；接口态另用可充放电模型，数值斜率必须测量/校准或标假设。
3. 定义Vth、BV的测量偏置和电流归一化；把电源电压与器件内部电压区分。
4. 先做基线与数值检查，再仅改剂量；不能改多个结构参数以制造预想的辐照趋势。
5. 实际训练假设与实验定义见[plan.md](plan.md)，可复用方法按运行验证后更新，不将文献阅读本身写成工具已运行。
