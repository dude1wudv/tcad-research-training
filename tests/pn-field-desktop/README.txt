PN 结电场：虚拟机桌面操作测试
==============================
本目录是实际运行的测试工程和截图，不是正式科研题目或校准结果。

本次完成
--------
1. 在运行中的 VM DISPLAY=:0 打开独立 xfce4-terminal。
2. 通过 X11 原生按键在终端输入 swb 并回车；Workbench W-2024.09 真实启动。
3. 复制 simulation/qualification/pn-diode 到本目录 model，原工程未修改。
4. 仅修改两个物理参数：
   - P 区 BoronActiveConcentration：1e16 -> 5e16 cm^-3。
   - anode 扫描终点：+0.5 -> -2.0 V，cathode 保持 0 V。
5. 用项目 runner 执行真实 SDE -> snmesh -> SDevice，单核，求解到 -2 V。
6. 在同一 VM 桌面启动 Sentaurus Visual，读取该次最终 diode_des.tdr。
7. 用原生 Tcl 显示 Abs(ElectricField-V)，导出 PNG；截图客户机整个 X11 桌面。
8. 回传模型、Tcl、桌面操作脚本、原生导出图、截图和证据哈希到本目录。

重要区别：这是桌面 GUI + 可追溯 CLI 的混合工作流。
swb 确实从桌面终端启动；本次求解由 scripts/tcad.py 调用原生工具，
不是点击 Workbench Run，也没有将普通 deck 冒充已运行的 Workbench 节点工程。
Visual 窗口确实显示此次 TDR 电场，桌面图不是合成界面或离线绘图替代品。

快速看图
--------
screenshots/01-swb-start.png              终端输入 swb 后的启动输出
screenshots/02-workbench-open.png         实际 Workbench 主窗口
screenshots/03-electric-field-desktop.png 实际 Visual 全桌面电场截图（2358x1357）
electric-field.png                       Visual 原生 export_view 导出图
result.json                              参数、运行结果、图件哈希

复现计算（Windows，仓库根目录）
--------------------------------
pwsh -File scripts/start-vm.ps1
python scripts/tcad.py run tests/pn-field-desktop/model

runner 输出 local_runtime/runs/<RUN_ID>；其 manifest 指明对应 VM 路径。
把 field.tcl 复制到该 VM run 目录（仅传此脚本，不重新生成或覆盖 TDR）。
在虚拟机桌面终端执行：
  swb
再开一个终端，在本次 run 目录执行：
  cd /home/tcad/research-training/runs/<RUN_ID>
  svisual -tcl -script field.tcl

Visual 成功加载后最大化窗口；确认右侧色标是 Abs(ElectricField-V)，单位 V/cm，
不是默认的 DopingConcentration。field.tcl 故意不 exit，便于人工检查和截图。
截图工具复制到 VM 后，用 tcad 图形登录用户执行：
  DISPLAY=:0 /usr/bin/python desktop.py capture /path/to/desktop.png
工具依赖镜像已有 Python 2、GI/Gdk3、X11/XTest，不需安装来源不明的插件。
桌面输入可用 desktop.py type --window <通过 xwininfo 核实的窗口ID> 'swb'，
再发送换行。click 的坐标必须来自最新截图，禁止复用旧窗口坐标。
通过已配置的严格 SSH/SCP 下载 PNG，不能关闭主机公钥验证。

实际结果
--------
run: 20260922T094811Z-pn-field-desktop-002679b5
工具：Sentaurus W-2024.09；验收：OpenAI Codex Astra medium。
SDE/mesh/SDevice 退出码均成功；561 网格点、1024 二维单元。
PLT 17 条完整有限数值记录；最终 anode=-2 V，cathode=0 V。
最终归一化误差 0.090775 < 1，Curve trace finished。
Visual 色标最大电场 79013.2 V/cm，峰值位于 PN 交界附近。
更轻掺杂的 N 区一侧耗尽区更宽，与当前非对称掺杂设置一致；
这里只做操作和数值输出检查，不声称网格无关性或实际器件校准完成。
电流是 2D PLT 原始数值，不在本测试中另作归一化解释。

完整原始 TDR/PLT/日志在 local_runtime/runs/<RUN_ID>/results.tar，按仓库规则不提交。
原生二维网格单元数与 Visual 显示的包含边界元素总数不同，不混用。
保留镜像遗留 locale/devtoolset/旧 contact API 警告，不压制失败。
