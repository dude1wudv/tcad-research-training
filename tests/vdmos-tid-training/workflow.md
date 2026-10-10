# 最简执行与复用流程

已有 VM、严格 SSH、单核串行求解、归档与桌面控制不另建一套工具链，直接复用[工作区流程](../../design-notes/workflow.md)、[tcad.py](../../scripts/tcad.py)和[desktop.py](../pn-field-desktop/desktop.py)。本训练已实测的是 **CLI 求解 + 真实 Visual GUI 读图**，不是 Workbench Run 按钮或节点工程。

## 1. 生成独立输入，再交给唯一 runner

以下在仓库根目录执行。`repeat-dose-060`是复用时的新名字示例，不是本次已执行的run；目录已经存在就换名，不覆盖冻结输入。

```powershell
python tests/vdmos-tid-training/build_case.py local_runtime/vdmos-tid-training/inputs/repeat-dose-060 --dose 60
python scripts/tcad.py run local_runtime/vdmos-tid-training/inputs/repeat-dose-060
```

更细网格/步长的输入同样通过生成器指定 `--mesh-scale 0.7 --step-scale 0.5`，然后单独运行。只改需要比较的数值设置，不在复验时改物理参数。保持SDE→IDVG→BV依赖顺序；SDE内部调用网格器，runner保持线程、affinity和锁。SSH断开后先核对该run及进程，不自动重新提交。

## 2. 整理归档而不是截取终端最后一行

本次已经核对的run对应关系见[run-index.json](run-index.json)。原始输入/归档在 `local_runtime/runs/<run_id>/`；完整 log、PLT、TDR不入库。复制新run到清单时，标明 `production` 或 `verification`，不能把更细网格的端点当成另一剂量正式曲线。

在独立venv中安装本次实际绘图依赖 `matplotlib==3.11.2`；本次Python为3.13，NumPy为2.5.3。PyMuPDF1.28.2仅用于阅读原PDF，不是电学解析的必需依赖。不要破坏全局受管理Python环境。

```powershell
local_runtime/vdmos-analysis-venv/Scripts/python.exe tests/vdmos-tid-training/analyze.py tests/vdmos-tid-training/run-index.json tests/vdmos-tid-training/data
python tests/vdmos-tid-training/test_analysis.py
```

后处理会核对归档哈希、退出码、完成标志、偏置终点、有限数据和端电流守恒；从原始两份PLT接入真实0 V栅压点，提取保存括区的Vth/BV；导出逐点CSV、summary、scalars、分辨率比较和5幅电学图。CSV保留实际样本与电流符号，曲线图显示绝对电流，不补造采样点或平滑掉低电流抖动。

`resolution-check.json`中的通过只表示满足冻结工程门槛，不等于严格网格独立；应另比较端点数值偏移与剂量效应的大小，不能以“误差小于5%”证明一个0.1%的BV变化可信。

## 3. 在真实客户机 GUI 加载同一次解

1. 从对应 `manifest.json` 读取 `remote_directory`，按既有严格SSH/SCP配置把本仓库的 `visualize.tcl` 传入该run；不在业务脚本硬编码IP或密钥路径，不关闭host-key校验。
2. 在已登录客户机桌面的终端进入该run，再执行 `svisual -tcl -script visualize.tcl`。如果已有本任务创建的Visual窗口，可在其Tcl控制台 `source` 对应脚本；先核对最新窗口/截图，不沿用旧坐标。
3. 查看真实净掺杂与 `Abs(ElectricField-V)`；确认变量、单位、真实run及内部漏压。标题中未自动写入内部电压时，从同run PLT/summary核对并注明，不从电源电压猜偏置。
4. 脚本输出原生 `structure.png`、`electric-field.png`、掺杂切线CSV、接口态切线CSV与 `visual-proof.txt`。证明文件包含真实字段列表和完成标记；仍要核对导出时间、图像及数据，键盘输入进程退出0不能代替GUI执行成功。
5. 用既有 `desktop.py capture` 保存真实桌面，再按严格SCP取回；先检查秘密与无关窗口。原生图不是桌面截图，二者分别记录run与SHA256。

接口切线可能包含相同坐标的两侧/边界样本，保留原始行，不擅自平均。接口输出字段可用于核对“存在、非零、位置正确”，不要仅凭一个显示字段反推模型输入的总面密度或校准占据率。全域场色标含氧化层，硅最大场另看半导体专用字段。

## 4. 收尾与复用边界

输入、逐点CSV、小型汇总、图件和哈希可提升到本训练目录；VM、密钥、许可证、受限工具手册、完整大结果仍在仓库外/被忽略目录。关闭窗口或清理时只针对自己创建且确认的对象，保留用户会话。

本次文献方法见[methods.md](methods.md)，参数与门槛见[plan.md](plan.md)，实际故障及修正见[lessons.md](lessons.md)。换器件或实测工艺后，先重新确认单位、剂量介质、缺陷系数、模型适用性和提取定义，再复用流程；不能直接搬用本训练结果作为实验数据。
