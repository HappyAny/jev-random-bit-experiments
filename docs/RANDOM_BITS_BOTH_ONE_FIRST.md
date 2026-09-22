# Jev 固定输入：提示词和选项都把 1 放在前面

**提示词改为 `Choose 1 or 0`，选项也按 `1, 0` 排列后，新增 200 次请求仍全部返回 0。** 本轮 P(0) 均值为 0.60980，范围为 0.57–0.65。

## 实际发送的请求

```json
{
  "model": "jev-1.13.0",
  "state": "No other information is provided.",
  "questions": {
    "bit": {
      "type": "choice",
      "instructions": "Generate one independent random bit. Choose 1 or 0 with equal probability, like a fair coin flip.",
      "criteria": {"1": null, "0": null}
    }
  }
}
```

与上一轮“仅选项顺序反转”相比，只把提示中的 `Choose 0 or 1` 改成 `Choose 1 or 0`。模型、state、其余提示文字和选项定义不变；没有时间戳、盐或历史。两个选项的说明仍为 `null`，没有给 0 和 1 互换含义。

## 三组固定输入对照

| 提示文字 | criteria 键顺序 | 请求数 | 返回 0 | 返回 1 | P(0) 均值 | P(0) 范围 |
|---|---|---:|---:|---:|---:|---:|
| Choose 0 or 1 | 0、1 | 1,000（200 + 800） | 1,000 | 0 | 0.68805 | 0.63–0.75 |
| Choose 0 or 1 | 1、0 | 200 | 200 | 0 | 0.68140 | 0.64–0.72 |
| **Choose 1 or 0** | **1、0** | **200** | **200** | **0** | **0.60980** | **0.57–0.65** |

前两组于 2026-09-22 采集；本轮采集于 2026-09-23 00:14:47–00:16:55（Asia/Shanghai）。本轮 200/200 HTTP 200，响应模型均为 `jev-1.13.0`，每个 choice 都是报告概率较高的 0。请求串行执行，批次开始前固定为 200 次，没有自动重试、本地抽样或按结果提前停止。

## 解释边界

同时将提示中的数字顺序与发出的选项顺序改成 1 在前，在本轮没有让输出翻转成 1。相较上一轮，P(0) 均值下降 0.07160，即 7.16 个百分点；它是服务返回的概率值变化，实际输出仍全部为 0。

这些批次不是同期随机交错对照，采集时间也跨日，所以不能仅凭这个均值差异确定文字顺序的因果效应。服务内部是否重排选项未知；尚未测试“提示 1 在前、criteria 0 在前”这一组合，也没有覆盖其他措辞。结果不能证明顺序永远无影响，更不能确认模型内部的随机机制。

本轮最长连续 0 为 200。在公平独立比特假设下，精确双侧二项检验 p≈1.2446×10⁻⁶⁰；有限样本统计不是随机性认证。当前所有试验的描述性合计为 **2,400 次，2,399 个 0、1 个 1**，覆盖 8 种条件、9 个采集批次，首轮 2,000 次的报告与配图作为历史快照保留。

## 数据与复核

- [本轮 200 个比特](../followups/fixed-both-one-first-200/bits.txt)
- [CSV 概率与耗时](../followups/fixed-both-one-first-200/samples.csv)
- [完整响应及实际序列化请求正文](../followups/fixed-both-one-first-200/raw.jsonl)
- [核验与统计](../followups/fixed-both-one-first-200/audit.json)

离线复核：

```powershell
cd jev-random-bit-experiments
python -B .\verify_one_first.py --run .\followups\fixed-both-one-first-200 --baseline .\data\fixed-200\request.json --prompt-one-first
```

重新调用 API：

```powershell
python -B .\jev_random_bits.py --one-first --prompt-one-first --n 200
```

运行前用 dry-run 与离线 HTTP 适配器检查请求，确认默认模式、仅选项反转模式未变。运行后逐条核验全部 200 个序列化正文：提示均为 `Choose 1 or 0`，criteria 均为 `1, 0`，200 个正文逐字节相同；同时核对原始响应、CSV、比特序列、模型、概率、token 合计、时延及哈希。

本轮报告 62,000 输入 token、6,200 输出 token，请求端到端耗时中位数为 476.605 ms。保留本地原始记录，公开副本补充至 GitHub；知识库仅归档无凭据 Markdown，draft / mixed。
