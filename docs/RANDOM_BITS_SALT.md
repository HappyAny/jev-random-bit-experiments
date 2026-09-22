# Jev 0/1：保留时间戳，再加入随机盐

**200 次全部返回 0；200 个不同的随机盐与时间戳均已实际进入模型 state。**

| 条件 | 次数 | 0 / 1 次数 | P(0) 均值 | P(0) 范围 |
|---|---:|---:|---:|---:|
| 固定输入 | 1,000 | 1,000 / 0 | 0.68805 | 0.63–0.75 |
| 每次加入时间戳 | 200 | 200 / 0 | 0.64365 | 0.60–0.69 |
| 时间戳 + 每次重新生成随机盐 | 200 | 200 / 0 | 0.54810 | 0.51–0.60 |

本轮时间为 2026-09-22 10:42:12–10:44:06（Asia/Shanghai）。模型固定为 `jev-1.13.0`，200 次全部 HTTP 200，没有失败重试或根据输出提前停止。

## 输入方法

沿用上一轮的微秒时间戳，在 state 末尾再追加 `Random salt: ...`。每次调用 `secrets.token_hex(16)`，以本机操作系统提供的随机源生成 16 字节，再编码为 32 个十六进制字符。模型、原始提示、Choice 选项及其 0、1 顺序保持不变。

```text
No other information is provided.
Request timestamp: <每次请求的实际 ISO 8601 时间戳，+08:00>
Random salt: <每次生成的 32 位十六进制盐>
```

这是“时间戳 + 盐”条件，本轮没有另做“仅盐”条件。盐仅作为模型输入；输出比特直接读取 API 的 `choice`，没有用本地随机数、盐的奇偶性或 probabilities 再抽样。每次实际请求与盐都保存于 raw.jsonl；CSV 另有 salt 列。

## 结论与边界

本组 P(0) 比前两组更接近 0.5，但最低仍是 0.51，所有 choice 仍为 0。[官方 Choice 定义](https://docs.typesafe.ai/primitives/choice)是选择最大概率的选项，这与观察一致。200 次结果未表现成公平随机比特：0 占 100%，1 占 0%。

本组在 iid Bernoulli(0.5) 假设下的精确双侧频数检验 p≈1.2446×10⁻⁶⁰；相同比特最长连续段为 200。所有输出相同，因此 Pearson 相邻相关系数未定义，游程检验的正态近似不适用。

三组按时间先后采集，没有随机交错，概率均值差异只作描述，不作严格因果估计。该测试不能推断所有盐格式或其他提示的行为。即使盐驱动的输出将来表现均衡，也不能由此证明模型内部有真随机过程，因为输入已经包含本地随机源提供的随机性。

## 数据与复算

- [本轮 200 位序列](../data/timestamp-salt-200/bits.txt)
- [CSV：盐、时间戳、输出与概率](../data/timestamp-salt-200/samples.csv)
- [逐次实际请求与原始响应](../data/timestamp-salt-200/raw.jsonl)
- [独立统计](../data/timestamp-salt-200/statistics.json)与[输入唯一性、文件一致性核验](../data/timestamp-salt-200/audit.json)

离线复算，不联网：

```powershell
cd jev-random-bit-experiments
python -B .\analyze_bits.py .\data\timestamp-salt-200\bits.txt
```

重新调用 API 采集同一条件：

```powershell
python -B .\jev_random_bits.py --timestamp --salt --n 200
```

## 验证与保存

核验结果：200 个盐均为 32 位十六进制且各不相同；200 个时间戳及 state 也各不相同；除时间戳和盐以外，模型、问题、选项顺序与基线一致。原始响应、CSV、bits.txt 的顺序及输出逐条一致，CSV 概率与响应一致，纯序列 SHA-256 与采集记录一致。

运行前完成 dry-run：原固定模式与时间戳模式保持兼容，盐真实进入 state。统计代码沿用此前已通过 4 项单元测试的版本。原始各组独立保留，不与固定条件的 1,000 位文件混合。

本轮 API 报告输入 75,778 token、输出 6,200 token；按同日核对的[公开价格](https://docs.typesafe.ai/models)估算 0.003182676 美元，未核对实扣。客户端请求中位数约 460.20 ms，包含网络与服务端时间。

密钥未写入代码、请求正文、数据或文档；盐是公开实验输入，不是 API 密钥。仅归档本文无凭据 Markdown 快照，原始数据留在工作目录，draft / mixed；内部随机机制仍未核实。
