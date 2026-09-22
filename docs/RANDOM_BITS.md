# Jev 生成 0/1 的随机性试验

后续：[按用户要求再采集 800 次，累计 1,000 次](RANDOM_BITS_1000.md)。本文保留首批 200 次的独立记录。

后续：[按用户要求再采集 800 次，累计 1,000 次](RANDOM_BITS_1000.md)。本文保留首批 200 次的独立记录。

**本次 200 个返回值全部为 0。固定提示下直接使用 Jev 的 Choice 输出，不符合公平独立随机比特的假设。**

## 试验设计

- 时间：2026-09-22 09:48:42–09:50:20，Asia/Shanghai。
- 官方端点：`https://api.typesafe.ai/v1/systemone`；请求和实际返回均为 `jev-1.13.0`。
- 采样前固定数量为 200；每次 HTTP 请求仅问一个 Choice 问题，顺序执行。全部请求成功，没有失败重试或按结果提前停止。
- 所有请求使用相同正文，没有历史对话、递增编号、时间戳或本地随机种子进入模型输入。选项顺序固定为 0、1。
- 完整保存 API 的 `choice`，没有在本地按 probabilities 抽样或修改比特。计数与检验完全在本地执行。

实际提示与选项：

```json
{
  "model": "jev-1.13.0",
  "state": "No other information is provided.",
  "questions": {
    "bit": {
      "type": "choice",
      "instructions": "Generate one independent random bit. Choose 0 or 1 with equal probability, like a fair coin flip.",
      "criteria": {"0": null, "1": null}
    }
  }
}
```

## 实际统计

| 项目 | 结果 |
|---|---:|
| HTTP 成功 / 计划请求数 | 200 / 200 |
| 0 的数量与比例 | 200；100% |
| 1 的数量与比例 | 0；0% |
| 最长相同比特连续段 | 200 |
| 相邻转移 00 / 01 / 10 / 11 | 199 / 0 / 0 / 0 |
| 精确双侧二项检验 p 值 | 1.2446030555722283 × 10⁻⁶⁰ |
| API 返回 P(0) 范围 | 0.65–0.75 |
| API 返回 P(0) 均值 | 0.68875 |
| 请求端到端时延中位数 | 381.5 ms |

主检验的零假设是每个比特独立、且 P(1)=0.5。200 个全为 0 或全为 1 的总概率是 `2 / 2^200 = 2^-199`，即上面的双侧 p 值。结果强烈反对这个零假设；p 值不是“模型是真随机的概率”。

序列没有方差，因此相邻 Pearson 相关系数未定义，输出 `null`；游程检验的正态近似条件不满足，也不报告其 p 值。四个连续 50 样本区段全部是 0。

## 为什么会这样，以及结论边界

[官方 Choice 定义](https://docs.typesafe.ai/primitives/choice)明确说明 `choice` 是概率最大的选项。本次每次 P(0) 都高于 P(1)，与最终总选 0 一致。返回一个概率分布不等于从该分布抽样。

同一输入的 probabilities 实际有小幅变化，本试验没有定位其来源。因此不能据此断言模型内部完全确定、服务端没有任何随机过程，或所有提示都只会得到 0；能确认的是本次固定提示和接口用法没有生成公平随机比特。也没有用本地随机抽样把结果加工成 50/50。

即便某次试验得到 50/50，也不能证明真随机：确定的 `010101...` 同样符合该比例。这里的少量诊断不等同于完整 NIST 测试套件，更不能证明物理真随机或不可预测性；[NIST 对统计检验边界的说明](https://csrc.nist.gov/pubs/sp/800/22/r1/upd1/final)同样强调统计测试不能替代对生成器设计的分析。

## 文件与本地复算

- [纯 0/1 序列：每行一个值](../data/fixed-200/bits.txt)
- [CSV：每次输出、概率、时延与 token](../data/fixed-200/samples.csv)
- [原始响应 JSONL](../data/fixed-200/raw.jsonl)
- [本地统计 JSON](../data/fixed-200/statistics.json)
- [实际请求](../data/fixed-200/request.json)与[采集元数据](../data/fixed-200/metadata.json)
- [采集脚本](../jev_random_bits.py)与[离线统计脚本](../analyze_bits.py)

本地复算已有序列，不联网、不需要密钥：

```powershell
cd jev-random-bit-experiments
python -B .\analyze_bits.py .\data\fixed-200\bits.txt
```

再采集一组新的 1,000 个样本时：

```powershell
python -B .\jev_random_bits.py --n 1000
```

脚本读取进程环境变量 `TYPESAFE_API_KEY`，或在终端要求隐藏输入；密钥不写入文件。新采集会调用付费 API；本次 62,000 输入 token、6,200 输出 token，按[当日公开价格](https://docs.typesafe.ai/models)估算 0.002604 美元，未核验账单实扣。每次采集保存独立目录，保留已有结果。

## 验证与归档

已逐条核对 200 条原始响应、CSV 与 bits.txt 完全一致，且顺序为 1–200。离线统计脚本的 4 项单元测试通过，包含精确二项概率、常量序列、交替序列与非法输入；交替序列测试专门演示“比例均衡但存在确定模式”。

原始响应和导出文件保留在本工作目录；Agent Library 只保存本文的无凭据 Markdown 快照，状态为 draft / mixed。以上计数、返回分布与软件检查属于实测；接口定义和检验边界已对照一手来源，内部机制未核实。
