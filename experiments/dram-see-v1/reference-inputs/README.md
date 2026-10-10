# 代表点冻结输入

这些文件逐字节提取自成功完整运行的 inputs.tar，复制前与 runner manifest 的输入哈希一致，来源见 [provenance.json](provenance.json)。便于直接审阅 SDE 几何与 SDevice mixed-mode deck，不是重新生成后冒充历史输入。

- coarse-full：原始完整 pilot，mesh=1、step=1；当时没有内嵌事件 CSV，保留其真实历史格式。
- fine-full：同物理条件的细化完整运行，mesh=0.7、step=0.5；内嵌实际事件 JSON/CSV。

目录包含自编文本输入，不含受限手册、TDR、PLT、许可证或商业软件。生成器当前版本哈希可能与早期 pilot 的版本不同；以各归档内 generator-sha256.txt 为历史依据。复现条件和参数说明见 [workflow.md](../workflow.md)，真实结果以对应 run ID 为准。
