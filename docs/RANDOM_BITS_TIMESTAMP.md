# Jev 0/1：每次加入时间戳，测试 200 次

**200 个不同时间戳实际进入模型输入，200 次全部返回 0。**

| 条件 | 次数 | 返回 0 | 返回 1 | P(0) 均值 |
|---|---:|---:|---:|---:|
| 此前固定输入，两批累计 | 1,000 | 1,000（100%） | 0（0%） | 0.68805 |
| 本次每次添加当前时间戳 | 200 | 200（100%） | 0（0%） | 0.64365 |

本次采集时间为 2026-09-22 10:35:10–10:36:26（Asia/Shanghai）。全部 HTTP 200，模型均为 `jev-1.13.0`。

## 时间戳如何加入

保留原来的模型、问题、选项与顺序，每次在 `state` 字符串末尾追加当前时间，格式为 ISO 8601、微秒精度、`+08:00` 时区。时间戳确实随 JSON 正文发送，不是只记录在本地日志或 HTTP 头中。

第一条实际 state：

```text
No other information is provided.
Request timestamp: 2026-09-22T10:35:10.271503+08:00
```

最后一条使用 `2026-09-22T10:36:26.275299+08:00`。200 个输入时间戳与 200 个 state 均各不相同；每条实际请求都保存在 raw.jsonl 的 `request` 字段中。没有按时间戳奇偶或其他本地规则计算输出，也没有做本地概率抽样。

## 实际结果与边界

- 输出仍全部是 0；最长同值段为 200，相邻转移全部为 00，共 199 次。
- P(0) 范围为 0.60–0.69，均值 0.64365；每条 P(0) 仍高于 P(1)。[官方 Choice 定义](https://docs.typesafe.ai/primitives/choice)是选择最大概率的选项，与实际行为一致。
- 本组精确双侧频数检验，在 iid Bernoulli(0.5) 零假设下 p≈1.2446×10⁻⁶⁰，强烈反对公平独立比特假设。由于所有值相同，Pearson 相关系数未定义，不报告游程检验的正态近似 p 值。
- 本次添加时间戳没有使输出呈现公平随机性；这不证明所有时间戳写法或其他提示都无效，也不确定模型内部是否存在随机过程。
- 概率均值低于此前固定输入，但两种条件在不同时间段采集，未随机交错，所以此差异只作描述，不当成严格的因果估计。保留独立结果，不混入此前 1,000 次的同条件合并文件。

## 数据与复算

- [本次 200 个值，每行一个](../data/timestamp-200/bits.txt)
- [CSV：时间戳、选择、概率和时延](../data/timestamp-200/samples.csv)
- [每次实际请求与响应](../data/timestamp-200/raw.jsonl)
- [独立统计](../data/timestamp-200/statistics.json)与[输入及文件核验](../data/timestamp-200/audit.json)

离线复算，不需要密钥、不联网：

```powershell
cd jev-random-bit-experiments
python -B .\analyze_bits.py .\data\timestamp-200\bits.txt
```

重跑相同条件会发起新 API 调用：

```powershell
python -B .\jev_random_bits.py --timestamp --n 200
```

省略 `--timestamp` 仍是原来的固定输入模式。`--dry-run --timestamp` 仅展示带时间戳的输入；`request_template.json` 中的占位符用于说明格式，每次真正发送的时间值以 raw.jsonl 为准。

## 验证与保存

已核对 200 条请求：仅 state 的时间戳变化，model、questions 与选项顺序和基线一致；全部有效响应与 CSV、bits.txt 顺序和值一致，纯序列 SHA-256 与采集元数据一致。运行前也通过 dry-run 验证默认请求未变。统计脚本沿用此前经过 4 项单元测试的版本。

本次报告输入 69,200 token、输出 6,200 token。按同日核对的[公开价格](https://docs.typesafe.ai/models)估算 0.0029064 美元，未查账单实扣。端到端请求时延中位数约 374.08 ms，包含网络。

密钥没有写入脚本、请求正文、结果或文档。保留本地原始数据，只将此 Markdown 作为无凭据快照归档到 Agent Library，draft / mixed；内部机制未核实。
