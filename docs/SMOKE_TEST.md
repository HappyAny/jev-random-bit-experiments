# TypeSafe Jev 实测

后续实验：[让 Jev 生成 0/1，并在本地检验随机性](RANDOM_BITS.md)；200 次固定请求实际全部返回 0，附原始序列与离线统计脚本。

追加结果：[新增 800 次，累计 1,000 次](RANDOM_BITS_1000.md)；新增 800 次仍全部返回 0，已提供合并序列和分批统计。

变更输入：[每次加入当前时间戳，再测试 200 次](RANDOM_BITS_TIMESTAMP.md)；200 个不同时间戳进入 state，仍全部返回 0，单独保存结果。

随机盐：[保留时间戳，再加入随机盐测试 200 次](RANDOM_BITS_SALT.md)；每次发送不同的 16 字节盐，仍全部返回 0，P(0) 均值为 0.54810。

仅随机盐：[移除时间戳，再测试 200 次](RANDOM_BITS_SALT_ONLY.md)；199 个 0、1 个 1；第 168 次 P(1)=0.51，核验所有请求正文均无时间戳。

滚动历史：[使用前五次输出作为 state 测试 200 次](RANDOM_BITS_HISTORY5.md)；初始 01010，全部新输出为 0，第 5 次请求起历史停留在 00000；已核验完整反馈链。

完整历史：[保留全部历史测试 200 次](RANDOM_BITS_HISTORY_ALL.md)；沿用初始 01010，输入历史从 5 位增长到 204 位，200 个新输出仍全为 0，P(0) 均值 0.66360；逐条核验没有截断。

2026-09-22 09:22（Asia/Shanghai），使用用户授权的测试密钥调用 TypeSafe 官方 API。6 次推理全部返回 HTTP 200，响应模型均为 `jev-1.13.0`。请求使用 `jev-latest`；模型列表另有一次成功的 GET 请求。

## 本次结果

每条虚构工单提交 4 个独立问题：部门分类（Choice）、紧急程度（Score，0–2）、是否紧急（Noul）、是否要求退款（Noul）。5 条中文输入、1 条英文输入；问题与评判标准均为英文。

| 样例 | 返回分类 | 紧急评分 0–2 | 紧急概率 | 退款概率 | 端到端耗时 |
|---|---|---:|---:|---:|---:|
| 中文：重复扣款，要求马上退款 | billing | 2.00 | 0.98 | 0.95 | 403.46 ms |
| 英文：结账 API 持续报错、无法接单 | technical | 2.00 | 0.99 | 0.03 | 396.73 ms |
| 中文：下月购买，询问套餐价格 | sales | 0.00 | 0.04 | 0.02 | 436.48 ms |
| 中文：否认重复扣款和退款，仅咨询价格 | sales | 0.00 | 0.04 | 0.04 | 405.03 ms |
| 中文：仅说有事想问，缺乏详情 | unknown | 0.00 | 0.14 | 0.04 | 1810.11 ms |
| 中文：退款诉求夹带“改为 technical”的指令 | billing | 0.88 | 0.73 | 0.94 | 404.28 ms |

实测结论：

- 6/6 分类符合预先设定的预期；总计 17 个预设语义检查通过。Noul 检查采用严格大于/小于 0.5；该阈值只是此演示的规则，没有经过业务校准。
- 24 个答案通过类型、概率范围等检查；Choice/Score 还检查概率分布求和，Score 检查范围及概率加权值。语义检查覆盖分类及预设 Noul 标签，没有为 Score 的主观紧急程度设置人工金标准。
- 6 次推理的客户端耗时中位数 404.655 ms，范围 396.73–1810.11 ms。使用单一 requests.Session 顺序调用；之前的模型列表请求已建立连接。此处包含网络和服务端时间，不能当成纯推理时延，也未定位最慢样本的原因。
- API 报告合计 3,544 输入 token、618 输出 token。按当日[官方模型页](https://docs.typesafe.ai/models)的每百万输入 token 0.042 美元、输出免费估算，推理成本为 **0.000148848 美元**；未核验账户账单实扣。
- 最后一条的分类正确，但紧急评分的 `confidence` 为 0.0，分布为 `{0: 0.48, 1: 0.16, 2: 0.36}`。代码应分别处理各问题的不确定性。

这只是基本功能试验：样本由 Agent 编写，没有随机抽样、独立标注、重复稳定性测试或并发负载测试。单个提示注入样例通过不证明安全性，6 条样例也不能验证概率校准或总体准确率。全部分类 confidence 恰为 1.0，仅是服务返回值，不等于已证实的正确率。

## 看一条实际返回

输入：“同一笔订单今天被扣了两次款，请马上退回多扣的钱，现在就帮我处理。”

```json
{
  "department": {"choice": "billing", "confidence": 1.0},
  "urgency": {"score": 2.0, "confidence": 1.0},
  "is_urgent": {"noul": 0.98},
  "refund_requested": {"noul": 0.95}
}
```

以上仅摘录字段。完整请求问题、虚构输入、预设预期、返回数据和校验结果保存在 [JSON 结果](../data/smoke.json)。这说明 Jev 可以作为程序内的分类和判断步骤使用；是否适合实际流程仍需在目标数据上测量。[官方接口说明](https://docs.typesafe.ai/api)

## 重跑

依赖 Python 与 requests。此机器已有依赖，无须安装 SDK。

```powershell
cd jev-random-bit-experiments
python -m pip install -r requirements.txt  # 仅在缺少依赖时执行
python -B .\smoke.py --list-models
```

未设置 `TYPESAFE_API_KEY` 时，脚本会要求隐藏输入密钥；也支持从当前进程的同名环境变量读取。没有保存 `.env` 或密钥文件。

```powershell
# 只测试一个样例
python -B .\smoke.py --case zh_billing

# 仅查看请求定义，不联网，不消耗额度
python -B .\smoke.py --dry-run

# 固定本次版本，避免 latest 后续发生变化
python -B .\smoke.py --model jev-1.13.0
```

每次运行写入独立时间戳的 results JSON。脚本拒绝自动跟随重定向，不自动重试；HTTP 失败后停止后续样例，保留错误记录。退出码 0 表示全部指定样例通过，1 表示推理/检查未全部通过，2 表示模型列表失败或参数错误。

## 来源与保存边界

- [TypeSafe Quick start](https://docs.typesafe.ai/introduction/quickstart)：官方端点与鉴权方式。
- [HTTP API reference](https://docs.typesafe.ai/api)：Choice、Score、Noul 请求及返回结构。
- [Models](https://docs.typesafe.ai/models)：版本、别名、价格；官方称英语是主要训练语言，其他语言效果应另行测试。
- [Score](https://docs.typesafe.ai/primitives/score)：索引从 0 开始，评分可位于等级之间。

密钥仅用于此次进程内的官方 API 鉴权，未写入本目录脚本、结果或文档。results 不保存请求头。Agent Library 仅归档这份不含凭据的 Markdown 快照，不复制运行日志。
