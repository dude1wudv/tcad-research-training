# 独立实验环境与来源

使用原有私人 VM 的严格 SSH 连接，地址通过 VMware Tools 获取；账号、IP、密钥路径不写入本文。配置仍由忽略目录 `local_runtime/connection.json` 管理。未重启系统或修改现有 TCAD、许可证、默认编译器及系统包。

## 运行环境

- 现有 CentOS 7，8 vCPU，约 16 GiB RAM；TCAD 求解限定单核/单线程并复用项目锁。
- Sentaurus W-2024.09，通过真实 SDE、snmesh 和 SDevice 运行检查，版本显示不代替求解验证。
- GCC 10.2.0。Geant4 10.7.3 官方 CentOS7 二进制解到项目用户目录的 `dram-see-v1/software/Geant4-10.7.3-Linux`，仅在专用命令子 shell 设置动态库路径。
- G4EMLOW7.13 与 G4ENSDFSTATE2.3。电磁数据初次下载截断，经 HTTPS Range 恢复并通过完整 gzip 校验；只使用 `data-complete/G4EMLOW7.13`。旧的不完整目录保留作失败证据，未设为当前数据路径。
- 主机后处理使用现有 `local_runtime/vdmos-analysis-venv/Scripts/python.exe` 中 NumPy/Matplotlib；业务 CLI 和标准库分析使用本机 Python。客户机截图用 `/usr/bin/python` 的系统 Gdk 绑定，`python3` 不具备对应绑定，首次失败已记录。

## 包与编译指纹

| 内容 | SHA-256 |
|---|---|
| Geant4 10.7.3 官方 CentOS7 包 | `0dff8b779028ef2d729a6b005f1ede103802df992be0c3ec976226b2a4b0fdd7` |
| 完整 G4EMLOW7.13 包 | `374896b649be776c6c10fea80abe6cf32f9136df0b6ab7c7236d571d49fb8c69` |
| G4ENSDFSTATE2.3 包 | `9444c5e0820791abd3ccaace105b0e47790fadce286e11149834e79c4a8e9203` |
| 本实验 C++ 源码 | `8f3ec870dad0905be7516bf657ed033d8cf5c5ade7cef938a941622b2f483ce2` |
| VM 中输运可执行文件 | `830cd8480bc11a27b243f6662d0e64a71d5b382a45bfd1e80f8e199bfdfdb67f` |

用同一源码和记录的编译命令重新构建到 `transport-verification`，与运行版本 `cmp` 相同，退出码 0。完整命令、stdout/stderr 和时间记录见 `local_runtime/dram-see-v1/operations/binary-provenance/`。有效语言选项由 `geant4-config --cflags` 给出（包含 `-std=c++11`，覆盖它前面的 `-std=c++17`）。这些指纹绑定本次环境，不承诺跨编译器二进制相同。

## 独立事件验收

验证 worker 按以下命令原样运行（仓库根目录）：

```powershell
python experiments/dram-see-v1/transport.py validation-alpha5-l025-a0 --length 0.25 --particle alpha --energy 5 --angle 0
```

退出码 0。与 pilot 同一随机种子的 `steps.csv`、`events.csv` 逐字节一致；逐步电离沉积总和与事件汇总相对误差约 1.29e-15，得到 Q=7.659403595125654 fC。独立验收仅证明该程序/环境及确定性事件可复现，不证明 EM 模型在全部工况适用、统计充分或与实测一致。

目录不可覆盖。复现时将上述标签替换为新的小写字母/数字/连字符标签，其余参数保持一致；新输出会进入独立数据目录。正式 TCAD 调度只走 `scripts/tcad.py`，不能用 `operate.py` 绕过其输入冻结、锁和归档。

`env-spec.json` 是安装前冻结的候选规格，保留原始哈希与当时状态；实际观察结果见 [environment-observed.json](data/environment-observed.json)。两者分别表示计划和运行证据，不通过修改原规格制造事前已验证的记录。

后处理实测为 Python 3.13.15、NumPy 2.5.3、Matplotlib 3.11.2（Agg），版本指纹见 [analysis-environment.json](data/analysis-environment.json)，最小依赖记录见 [analysis-requirements.txt](analysis-requirements.txt)。本轮复用既有环境，没有另建干净环境做安装复验。
