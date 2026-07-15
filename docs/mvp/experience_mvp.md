一句话结论：**experience MVP 冻结为 8 个字段，够分池，不再扩。**

---

# 0. 冻结版字段

`data/clean/YYYY-MM-DD_jobs.jsonl` 里只放这 8 个：

```text
experience_min_years
experience_max_years
experience_years_bucket
experience_requirement_type
experience_required_tags
experience_prefer_tags
experience_parse_status
experience_source
```

不要再加：

```text
experience_barrier
experience_prefer
experience_confidence
experience_original_sentence
experience_management_years
experience_industry_years
experience_exact_text
```

这些先留在 review/evidence，不进 MVP clean。

---

## 0.1 Clean JSONL 数据类型规则

`data/clean/YYYY-MM-DD_jobs.jsonl` 使用 JSON 原生类型。

以下字段必须写成真正的 JSON array：

- `experience_required_tags`
- `experience_prefer_tags`

正确：

```json
{
  "experience_required_tags": ["ai", "testing", "data"],
  "experience_prefer_tags": []
}
```

禁止在 clean JSONL 中写成：

```json
{
  "experience_required_tags": "ai;testing;data",
  "experience_prefer_tags": null
}
```

规则：

- 有值：使用 JSON array。
- 无值：使用空数组 []。
- 不使用分号字符串保存 list。
- 不使用 null、None、nan 表示空列表。

---

# 1. 字段总表

| 字段                            | 数据类型             | 例子                               | 必须/延后 | 作用                |
| ----------------------------- | ---------------- | -------------------------------- | ----- | ----------------- |
| `experience_min_years`        | `number \| null` | `3`、`5`、`0`、`null`               | 必须    | 判断最低年限门槛          |
| `experience_max_years`        | `number \| null` | `5`、`2`、`null`                   | 必须    | 处理 `3-5年`、`0-2年`  |
| `experience_years_bucket`     | `string enum`    | `3_5`                            | 必须    | 统计和粗筛             |
| `experience_requirement_type` | `string enum`    | `hard_min`、`range`、`prefer_only` | 必须    | 区分硬要求/范围/优先       |
| `experience_required_tags`    | `list[string]`   | `["game", "operations"]`         | 必须    | 表示硬性经验方向          |
| `experience_prefer_tags`      | `list[string]`   | `["overseas"]`                   | 必须    | 表示优先经验，不用于 reject |
| `experience_parse_status`     | `string enum`    | `ok`、`partial`、`unknown`         | 必须    | 判断解析结果能不能用        |
| `experience_source`           | `object`         | `{"years":"text_rule"}`          | 必须    | 追踪来源，避免回查 review  |

---

# 2. `experience_min_years`

## 含义

岗位**硬性要求**的最低工作年限。

## 数据类型

```text
number | null
```

## 判断规则

| sentence              |     输出 |
| --------------------- | -----: |
| `3年以上游戏服务端开发经验`       |    `3` |
| `至少5年游戏运营经验`          |    `5` |
| `3-5年游戏行业工作经验`        |    `3` |
| `0-2年商务、运营、市场或相关工作经验` |    `0` |
| `经验不限`                |    `0` |
| `有海外发行经验者优先`          | `null` |
| `有丰富经验`               | `null` |

## 关键规则

只从**硬要求部分**取年限。

例如：

```text
3年以上游戏运营经验，有海外发行经验者优先
```

输出：

```json
{
  "experience_min_years": 3
}
```

不要因为“海外发行经验者优先”再改 min_years。

---

# 3. `experience_max_years`

## 含义

岗位明确写了年限范围时的上限。

## 数据类型

```text
number | null
```

## 判断规则

| sentence           |     输出 |
| ------------------ | -----: |
| `3-5年游戏行业工作经验`     |    `5` |
| `2~3年相关经验`         |    `3` |
| `0-2年商务、运营、市场相关经验` |    `2` |
| `3年以上游戏运营经验`       | `null` |
| `5年及以上经验`          | `null` |

## 注意

`max_years` 不是 reject 主字段。
主判断字段仍然是 `experience_min_years`。

---

# 4. `experience_years_bucket`

## 含义

把最低年限归到几个粗桶里。

## 数据类型

```text
string enum
```

建议枚举：

```text
none
0_1
1_3
3_5
5_8
8_plus
unknown
```

## 判断规则

| min_years | bucket    |
| --------: | --------- |
|       `0` | `none`    |
|     `0.5` | `0_1`     |
|       `1` | `1_3`     |
|       `2` | `1_3`     |
|       `3` | `3_5`     |
|       `5` | `5_8`     |
|       `8` | `8_plus`  |
|    `null` | `unknown` |

## 例子

```text
3年以上游戏行业用户研究经验
```

输出：

```json
{
  "experience_min_years": 3,
  "experience_years_bucket": "3_5"
}
```

---

# 5. `experience_requirement_type`

## 含义

这句话里的 experience 要求属于哪种类型。

## 数据类型

```text
string enum
```

建议枚举：

```text
hard_min
range
prefer_only
none
mixed
unknown
```

---

## 判断规则

| 类型            | 判断标准            | 例子                  |
| ------------- | --------------- | ------------------- |
| `hard_min`    | 明确最低年限硬要求       | `3年以上游戏运营经验`        |
| `range`       | 明确年限范围          | `3-5年游戏行业经验`        |
| `prefer_only` | 只有优先经验，没有硬年限    | `有海外发行经验者优先`        |
| `none`        | 明确经验不限          | `经验不限`              |
| `mixed`       | 多个硬性年限/多个层级要求   | `8年以上游戏经验，3年以上管理经验` |
| `unknown`     | 有经验词，但无法转成结构化字段 | `有丰富经验`             |

---

## 特别重要：多数字怎么处理

例子：

```text
行业经验：8年以上游戏开发从业经验，3年以上制作人/主策/产品负责人角色经验
```

输出建议：

```json
{
  "experience_min_years": 8,
  "experience_max_years": null,
  "experience_years_bucket": "8_plus",
  "experience_requirement_type": "mixed",
  "experience_required_tags": ["game", "development", "management"],
  "experience_parse_status": "partial"
}
```

原因：

```text
8年以上游戏开发经验 = 总体硬门槛
3年以上制作人/负责人经验 = 子门槛
```

MVP 不单独建 `management_years`。
先用 `mixed + partial` 标记，analysis 可把它放 grey。

---

# 6. `experience_required_tags`

## 含义

硬性要求里的经验方向。

## 数据类型

```text
list[string]
```

## 建议枚举

先只保留这些，不要扩太细：

```text
game
ecommerce
ai
data
backend
frontend
testing
operations
product
marketing
bd
strategy
research
security
management
overseas
content
design
unknown
```

---

## 判断规则

只从**硬要求部分**抽取。

| sentence              | required_tags                                  |
| --------------------- | ---------------------------------------------- |
| `3年以上游戏服务端开发经验`       | `["game", "backend"]`                          |
| `5年以上游戏商业化策划经验`       | `["game", "product"]` 或 `["game", "strategy"]` |
| `3年以上数据科学、机器学习算法相关经验` | `["data", "ai"]`                               |
| `7年以上信息安全或SOC经验`      | `["security"]`                                 |
| `3年及以上游戏策划经验`         | `["game", "product"]`                          |
| `有丰富项目经验`             | `["unknown"]`                                  |

---

## 你的 MVP 里不要做的事

不要把每个具体词都建成标签：

```text
Gameplay
MENA
MOBA
SLG
ACG
UGC
PGC
SOC
IAA
```

这些先不进 clean。
后续如果你发现 AI 评测岗位里某些词很关键，再单独加。

---

# 7. `experience_prefer_tags`

## 含义

“优先 / 加分 / 更佳 / 尤佳 / 者优先”里的经验方向。

## 数据类型

```text
list[string]
```

## 判断规则

只从偏好部分抽取。

| sentence           | prefer_tags                   |
| ------------------ | ----------------------------- |
| `有海外发行案例者优先`       | `["overseas"]`                |
| `有游戏行业经验者优先`       | `["game"]`                    |
| `有AI Agent研发经验者优先` | `["ai"]`                      |
| `有长线游戏运营经验者加分`     | `["game", "operations"]`      |
| `有互联网产品合规工作经验者尤佳`  | `["product"]` 或 `["unknown"]` |

---

## 例子

```text
本科及以上学历，2年及以上游戏发行或互联网整合营销经验，有海外发行案例者优先；
```

输出：

```json
{
  "experience_min_years": 2,
  "experience_requirement_type": "hard_min",
  "experience_required_tags": ["game", "marketing"],
  "experience_prefer_tags": ["overseas"]
}
```

核心原则：

```text
required_tags 影响 pass/reject/grey
prefer_tags 不直接 reject
```

---

# 8. `experience_parse_status`

## 含义

一个岗位聚合 API experience、requirements 和 description 后，
experience 信息是否能够稳定写入 clean。

`experience_parse_status` 是岗位级状态，不是单条 evidence 的审核状态。

## 数据类型

```text
string enum
```

建议枚举：

```text
ok
partial
unknown
conflict
not_experience
```

---

## 判断规则

| 状态 | 判断标准 | 例子 |
|---|---|---|
| `ok` | 明确经验要求、明确经验偏好，或明确“经验不限”，并能稳定归一 | `3年以上测试经验`、`经验不限` |
| `partial` | 主要求能解析，但仍有部分经验信息无法稳定归一 | `3年以上游戏经验，有复杂项目经验者优先` |
| `unknown` | 明显涉及经验但无法结构化；或者 API、requirements、description 均没有经验信息 | `有丰富经验`；所有来源均无经验信息 |
| `conflict` | API experience 与文本抽取存在实质冲突 | API `1-3年`，文本 `5年以上` |
| `not_experience` | 命中的候选句经判断并不是工作经验要求 | `具备良好的沟通能力` |

---

## 什么叫 partial？

只要主门槛能解析，但还有一部分不好判断，就用 `partial`。

例子：

```text
3年以上游戏相关经验，有复杂项目经验者优先
```

输出：

```json
{
  "experience_min_years": 3,
  "experience_required_tags": ["game"],
  "experience_prefer_tags": ["unknown"],
  "experience_parse_status": "partial"
}
```

原因：

```text
3年以上游戏相关经验 = 清楚
复杂项目经验者优先 = 不好归类
```

---

# 9. `experience_source`

## 含义

每个 experience 字段来自哪里。

## 数据类型

```json
{
  "years": "api | text_rule | manual | none | conflict",
  "required_tags": "api | text_rule | manual | none | conflict",
  "prefer_tags": "text_rule | manual | none"
}
```

## 例子

```json
{
  "years": "text_rule",
  "required_tags": "text_rule",
  "prefer_tags": "none"
}
```

## 给谁用？

| 消费端         | 怎么用                    |
| ----------- | ---------------------- |
| analysis 脚本 | `conflict` 时进 grey     |
| 你           | 排查误判来自 API 还是文本规则      |
| 后续规则维护      | 看哪些字段主要靠 text_rule 补出来 |

---

# 10. 从 sentence 判断字段的顺序

不要一上来就抽标签。
顺序应该是：

```text
1. 文本标准化
2. 切分硬要求句段 / 优先句段
3. 从硬要求句段抽年限
4. 从硬要求句段抽 required_tags
5. 从优先句段抽 prefer_tags
6. 判断 requirement_type
7. 判断 parse_status
8. 写 source
```

---

## 10.1 文本标准化

先把这些统一：

| 原始写法                 | 统一       |
| -------------------- | -------- |
| `3 年以上`              | `3年以上`   |
| `3 年及以上`             | `3年以上`   |
| `3-5年`、`3–5年`、`3~5年` | `3-5年`   |
| `三年以上`               | `3年以上`   |
| `一年及以上`              | `1年以上`   |
| `半年以上`               | `0.5年以上` |

---

## 10.2 切分硬要求 / 优先句段

遇到这些词，后半段一般进入 prefer：

```text
优先
加分
更佳
尤佳
者优先
可考虑
```

例子：

```text
3年以上游戏运营经验，有海外发行经验者优先
```

切成：

```text
hard_part = 3年以上游戏运营经验
prefer_part = 有海外发行经验者优先
```

---

## 10.3 抽年限

优先匹配范围：

```text
3-5年
2~3年
0-2年
```

再匹配下限：

```text
3年以上
至少5年
5年及以上
不少于3年
```

再匹配经验不限：

```text
经验不限
不限经验
优秀应届可考虑
```

---

## 10.4 抽 tags

只用关键词映射，不做复杂理解。

简单映射：

| 关键词                    | tag          |
| ---------------------- | ------------ |
| 游戏、手游、电竞               | `game`       |
| 电商、跨境电商                | `ecommerce`  |
| AI、人工智能、机器学习、大模型、Agent | `ai`         |
| 数据、数据分析、数据科学           | `data`       |
| 服务端、后端                 | `backend`    |
| 前端                     | `frontend`   |
| 测试、质量、QA               | `testing`    |
| 运营、社群、用户运营             | `operations` |
| 产品、策划、制作人              | `product`    |
| 市场、营销、投放、品牌            | `marketing`  |
| 商务、BD                  | `bd`         |
| 战略、咨询、投行、商分            | `strategy`   |
| 用户研究、用研                | `research`   |
| 安全、SOC                 | `security`   |
| 管理、负责人、团队管理            | `management` |
| 海外、全球、出海、MENA、SEA      | `overseas`   |
| 内容、创作者、社区、UGC、PGC      | `content`    |
| UI、UX、设计               | `design`     |

---

# 11. 典型句子输出示例

## 例子 1：硬年限 + 硬方向

```text
3年以上游戏服务端开发经验
```

```json
{
  "experience_min_years": 3,
  "experience_max_years": null,
  "experience_years_bucket": "3_5",
  "experience_requirement_type": "hard_min",
  "experience_required_tags": ["game", "backend"],
  "experience_prefer_tags": [],
  "experience_parse_status": "ok",
  "experience_source": {
    "years": "text_rule",
    "required_tags": "text_rule",
    "prefer_tags": "none"
  }
}
```

---

## 例子 2：范围年限 + 优先经验

```text
本科及以上学历，3-5年电竞/游戏行业工作经验，有国内/海外大型电竞赛事项目经验者优先；
```

```json
{
  "experience_min_years": 3,
  "experience_max_years": 5,
  "experience_years_bucket": "3_5",
  "experience_requirement_type": "range",
  "experience_required_tags": ["game"],
  "experience_prefer_tags": ["overseas"],
  "experience_parse_status": "ok",
  "experience_source": {
    "years": "text_rule",
    "required_tags": "text_rule",
    "prefer_tags": "text_rule"
  }
}
```

---

## 例子 3：多个硬年限

```text
行业经验：8年以上游戏开发从业经验，3年以上制作人/主策/产品负责人角色经验
```

```json
{
  "experience_min_years": 8,
  "experience_max_years": null,
  "experience_years_bucket": "8_plus",
  "experience_requirement_type": "mixed",
  "experience_required_tags": ["game", "development", "management"],
  "experience_prefer_tags": [],
  "experience_parse_status": "partial",
  "experience_source": {
    "years": "text_rule",
    "required_tags": "text_rule",
    "prefer_tags": "none"
  }
}
```

MVP 处理：

```text
experience_requirement_type=mixed
experience_parse_status=partial
```

可以同时存在：

- mixed 表示存在多个硬性经验层级；
- partial 表示 MVP 没有为每个子门槛单独建字段。

进入 decision 层后，必须先判断
experience_requirement_type=mixed，再判断
experience_parse_status=partial。

因此本例固定输出：

```text
experience_decision=grey
experience_reason_codes=experience_mixed_requirement
```

禁止输出：

```text
experience_reason_codes=experience_partial
```

也不得再根据 experience_min_years 把该岗位改判为 rejected。

---

## 例子 4：只有优先经验

```text
有海外发行案例者优先
```

```json
{
  "experience_min_years": null,
  "experience_max_years": null,
  "experience_years_bucket": "unknown",
  "experience_requirement_type": "prefer_only",
  "experience_required_tags": [],
  "experience_prefer_tags": ["overseas"],
  "experience_parse_status": "ok",
  "experience_source": {
    "years": "none",
    "required_tags": "none",
    "prefer_tags": "text_rule"
  }
}
```

MVP 处理：

```text
prefer_only 不 reject
```

---

## 例子 5：经验不限

```text
经验不限，优秀应届生可考虑
```

```json
{
  "experience_min_years": 0,
  "experience_max_years": null,
  "experience_years_bucket": "none",
  "experience_requirement_type": "none",
  "experience_required_tags": [],
  "experience_prefer_tags": [],
  "experience_parse_status": "ok",
  "experience_source": {
    "years": "text_rule",
    "required_tags": "none",
    "prefer_tags": "none"
  }
}
```

---

## 例子6： 明确写“经验不限”

输入：

```text
经验不限
```

输出：

```json
{
  "experience_min_years": 0,
  "experience_max_years": null,
  "experience_years_bucket": "none",
  "experience_requirement_type": "none",
  "experience_required_tags": [],
  "experience_prefer_tags": [],
  "experience_parse_status": "ok",
  "experience_source": {
    "years": "text_rule",
    "required_tags": "none",
    "prefer_tags": "none"
  }
}
```

---

## 例子7：API 和文本都没有 experience 信息

### 含义：
无法确认岗位是否有经验要求，不等于岗位明确经验不限。


输出：

```json
{
  "experience_min_years": null,
  "experience_max_years": null,
  "experience_years_bucket": "unknown",
  "experience_requirement_type": "unknown",
  "experience_required_tags": [],
  "experience_prefer_tags": [],
  "experience_parse_status": "unknown",
  "experience_source": {
    "years": "none",
    "required_tags": "none",
    "prefer_tags": "none"
  }
}
```

---

## 例子8：命中的候选句不是 experience 要求

not_experience 只用于候选句假阳性。
完全没有匹配到 experience 信息时，必须使用 unknown。

输出：

```json
{
  "experience_min_years": null,
  "experience_max_years": null,
  "experience_years_bucket": "unknown",
  "experience_requirement_type": "unknown",
  "experience_required_tags": [],
  "experience_prefer_tags": [],
  "experience_parse_status": "not_experience",
  "experience_source": {
    "years": "none",
    "required_tags": "none",
    "prefer_tags": "none"
  }
}
```

---

# 12. 最终冻结版 schema

```json
{
  "experience_min_years": 3,
  "experience_max_years": null,
  "experience_years_bucket": "3_5",
  "experience_requirement_type": "hard_min",
  "experience_required_tags": ["game", "operations"],
  "experience_prefer_tags": ["overseas"],
  "experience_parse_status": "ok",
  "experience_source": {
    "years": "text_rule",
    "required_tags": "text_rule",
    "prefer_tags": "text_rule"
  }
}
```

---

# 13. MVP 判断边界

| 情况            | MVP 处理                                     |
| ------------- | ------------------------------------------ |
| 年限明确          | 正常解析                                       |
| 年限范围          | 取 min 和 max                                |
| 多个硬年限         | `mixed` 优先 grey                             |
| 只有优先经验        | 不 reject                                   |
| 经验方向不清楚       | tag 用 `unknown`，status 用 `partial/unknown` |
| API 和 text 冲突 | `parse_status=conflict`                    |
| 不是经验要求        | `parse_status=not_experience`              |

最后冻结成一句话：

```text
experience 只回答 3 件事：
硬性最低几年、硬性要求什么经验、哪些只是优先。
```
