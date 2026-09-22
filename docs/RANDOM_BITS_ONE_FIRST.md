# Jev 固定输入：把选项 1 放在 0 前面

**新增 200 次请求仍全部返回 0，返回 1 的次数为 0。** 把发出的 `criteria` JSON 键顺序改为 `1, 0`，本轮没有出现偏向第一个选项 `1` 的现象。

## 只改了什么

原顺序与本轮顺序：

```json
{"0": null, "1": null}
{"1": null, "0": null}
```

模型保持 `jev-1.13.0`，state 仍为 `No other information is provided.`，提示仍为：

```text
Generate one independent random bit. Choose 0 or 1 with equal probability, like a fair coin flip.
```

提示中的 `0 or 1` 没有改为 `1 or 0`，因此这次只测选项映射的序列化顺序，没有同时改变文字顺序。输入不含时间戳、盐或历史。200 条实际送入 HTTP 适配器的 JSON 正文全部相同，并逐条确认 `criteria` 的键为 `1` 在前、`0` 在后；未保存认证头。

## 结果与固定输入基线

| 条件 | 请求数 | 返回 0 | 返回 1 | P(0) 均值 | P(0) 范围 |
|---|---:|---:|---:|---:|---:|
| 先前固定输入，0 在前 | 1,000（200 + 800） | 1,000 | 0 | 0.68805 | 0.63–0.75 |
| 本轮固定输入，1 在前 | 200 | 200 | 0 | 0.68140 | 0.64–0.72 |

本轮采集于 2026-09-22 17:01:15–17:03:01（Asia/Shanghai）。200/200 HTTP 200，响应模型均为 `jev-1.13.0`，choice 均为报告概率较高的 0。最长连续 0 为 200。在公平独立比特假设下，精确双侧二项检验 p≈1.2446×10⁻⁶⁰。

请求数在开始前固定为 200；串行调用，无自动重试、本地抽样或按结果提前停止。本轮报告 62,000 输入 token、6,200 输出 token，端到端耗时中位数约 433.305 ms。

## 可以得出的结论

在这 200 次调用中，**把发出的选项顺序反过来，没有把输出从 0 翻转成 1**。结果不支持“只要把 1 放在发出的 JSON 最前面，服务就会始终选 1”的解释。

服务内部是否重新排序、模型最终看到什么顺序，无法由客户端记录确认。原提示仍先写 0，两个顺序也没有在同一时段随机交错，因此不能证明顺序对所有请求都无影响，不能把 P(0) 均值的微小差异归因于顺序本身。没有由此确认模型内部的随机机制。

这轮是首轮 2,000 次之后追加的独立对照。当前所有比特请求的描述性合计为 **2,200 次，2,199 个 0、1 个 1**；不把不同条件合并成一个预先设计的同分布试验。首轮 2,000 次的报告和配图仍保留为当时的快照。

## 原始记录与复核

- [本轮 200 个比特](../followups/fixed-one-first-200/bits.txt)
- [CSV 输出、概率与时延](../followups/fixed-one-first-200/samples.csv)
- [逐条原始响应与序列化请求正文](../followups/fixed-one-first-200/raw.jsonl)
- [完整核验与统计](../followups/fixed-one-first-200/audit.json)

离线核验，不调用 API：

```powershell
cd jev-random-bit-experiments
python -B .\verify_one_first.py --run .\followups\fixed-one-first-200 --baseline .\data\fixed-200\request.json
```

从相同定义重新调用 API：

```powershell
python -B .\jev_random_bits.py --one-first --n 200
```

运行前通过 dry-run 和离线 HTTP 适配器检查，确认默认请求仍与基线一致，反向模式只改变 `criteria` 的键顺序。运行后核验全部 200 条请求正文、原始响应、CSV、比特序列、顺序、模型、概率、时延、token 合计及序列哈希。

原始本地数据保留。无凭据公开副本作为追加试验进入 GitHub；仅归档本文 Markdown，draft / mixed，保留上述解释边界。
