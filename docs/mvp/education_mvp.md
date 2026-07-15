一句话结论：**education MVP 冻结 6 个字段，只回答“学历门槛、学历偏好、专业门槛、专业偏好、解析状态、来源”。**

---

# 0. 冻结版字段

`data/clean/YYYY-MM-DD_jobs.jsonl` 里 education 只放这 6 个：

```text
education_degree_barrier
education_degree_prefer
education_major_barrier
education_major_prefer
education_parse_status
education_source
```

不要进 MVP clean 的字段：

```text
education_confidence
education_original_sentence
education_exact_major_text
education_school_prefer
education_985_211
education_major_raw
education_pattern_name
```

这些可以留在 `data/review`，不要进入下游主表。

---

## 0.1 Clean JSONL 数据类型规则

`data/clean/YYYY-MM-DD_jobs.jsonl` 使用 JSON 原生类型。

以下字段必须写成真正的 JSON array：

- `education_degree_prefer`
- `education_major_barrier`
- `education_major_prefer`

正确：

```json
{
  "education_degree_prefer": ["master_plus", "phd_plus"],
  "education_major_barrier": ["computer", "ai_ml"],
  "education_major_prefer": []
}
```

禁止在 clean JSONL 中写成：

```json
{
  "education_degree_prefer": "master_plus;phd_plus",
  "education_major_barrier": "['computer', 'ai_ml']",
  "education_major_prefer": null
}
```

规则：

- 有值：使用 JSON array。
- 无值：使用空数组 []。
- 不使用分号字符串保存 list。
- 不使用 null、None、nan 表示空列表。

---

# 1. 字段总表

| 字段                         | 数据类型           | 例子                               | 必须/延后 | 作用                           |
| -------------------------- | -------------- | -------------------------------- | ----- | ---------------------------- |
| `education_degree_barrier` | `string enum`  | `bachelor_plus`                  | 必须    | 判断学历硬门槛                      |
| `education_degree_prefer`  | `list[string]` | `["phd_plus"]`                   | 必须    | 判断学历偏好，不直接 reject            |
| `education_major_barrier`  | `list[string]` | `["computer"]`                   | 必须    | 判断专业硬门槛                      |
| `education_major_prefer`   | `list[string]` | `["computer", "design_art"]`     | 必须    | 判断专业偏好，不直接 reject            |
| `education_parse_status`   | `string enum`  | `ok`、`partial`                   | 必须    | 判断 clean 字段是否稳定可用            |
| `education_source`         | `object`       | `{"degree_barrier":"text_rule"}` | 必须    | 追踪字段来源，避免 analysis 回查 review |

---

# 2. `education_degree_barrier`

## 含义

岗位明确写出的**学历硬门槛**。

## 数据类型

```text
string enum
```

建议枚举：

```text
none
associate_plus
bachelor_plus
master_plus
phd_plus
unknown
```

---

## 从 sentence 判断

| sentence                                | 输出               |
| --------------------------------------- | ---------------- |
| `本科及以上学历，商科相关专业；`                       | `bachelor_plus`  |
| `本科以上计算机相关专业，3年以上游戏开发经验；`               | `bachelor_plus`  |
| `计算机相关专业本科及以上学历，3年以上java后端开发经验；`        | `bachelor_plus`  |
| `教育背景：人工智能、计算机科学、数学或相关专业，硕士及以上学历，博士优先；` | `master_plus`    |
| `数据科学、统计学、应用数学、机器学习、计算机科学等领域专业硕士以上学位；`  | `master_plus`    |
| `专科及以上学历，物业管理、机电工程等相关专业；`               | `associate_plus` |
| `学历不限`                                  | `none`           |
| `良好的教育背景`                               | `unknown`        |

---

## 判断规则

优先识别这些学历词：

| 词                             | 归一               |
| ----------------------------- | ---------------- |
| `专科及以上`、`大专及以上`               | `associate_plus` |
| `本科及以上`、`本科以上`、`本科或以上`、`统招本科` | `bachelor_plus`  |
| `硕士及以上`、`硕士以上`、`研究生及以上`       | `master_plus`    |
| `博士及以上`、`博士学历`、`博士学位`         | `phd_plus`       |
| `学历不限`、`不限学历`                 | `none`           |

---

# 3. `education_degree_prefer`

## 含义

学历偏好，不是硬门槛。

## 数据类型

```text
list[string]
```

元素仍然用学历 enum：

```text
bachelor_plus
master_plus
phd_plus
```

---

## 从 sentence 判断

| sentence                                | 输出                |
| --------------------------------------- | ----------------- |
| `教育背景：人工智能、计算机科学、数学或相关专业，硕士及以上学历，博士优先；` | `["phd_plus"]`    |
| `学历背景：本科及以上学历，硕士学历优先，人工智能、教育技术学等专业优先。`  | `["master_plus"]` |
| `3年以上的咨询、战略等行业工作经验与背景...硕士及以上学历者优先；`    | `["master_plus"]` |
| `本科及以上学历，商科相关专业；`                       | `[]`              |

---

## 判断规则

只要学历词和这些偏好词绑定，就进 `degree_prefer`：

```text
优先
加分
更佳
尤佳
为佳
可考虑
```

例子：

```text
硕士学历优先
博士优先
硕士及以上学历者优先
```

都不是 barrier。
除非句子明确写：

```text
硕士及以上学历
博士学历
```

这种才是 `education_degree_barrier`。

---

# 4. `education_major_barrier`

## 含义

岗位明确要求的**专业硬门槛**。

## 数据类型

```text
list[string]
```

建议专业组枚举：

```text
computer
ai_ml
data_science
math_stats
engineering
business
finance
marketing_media
design_art
language
law
medical
education
other
unknown
```

---

## 从 sentence 判断

| sentence                                | 输出                                           |
| --------------------------------------- | -------------------------------------------- |
| `本科及以上学历，商科相关专业；`                       | `["business"]`                               |
| `本科以上计算机相关专业，3年以上游戏开发经验；`               | `["computer"]`                               |
| `计算机相关专业本科及以上学历，3年以上java后端开发经验；`        | `["computer"]`                               |
| `拥有计算机、统计学、数学、数据科学等相关专业本科及以上学历。`        | `["computer", "math_stats", "data_science"]` |
| `统计、数学、金融相关专业本科及以上学历；`                  | `["math_stats", "finance"]`                  |
| `自然语言处理/机器学习/模式识别/人工智能/计算机等相关专业硕士以上学历；` | `["ai_ml", "computer"]`                      |
| `本科及以上学历，具备交易相关的渠道运营或社交玩法的用增实战经验；`      | `[]`                                         |

---

## 判断规则

只有专业词出现在**硬要求区域**，才进 `major_barrier`。

硬要求区域通常长这样：

```text
计算机相关专业本科及以上学历
本科及以上学历，计算机相关专业
统计、数学、金融相关专业本科及以上学历
XX专业硕士以上学位
```

不带 `优先 / 加分 / 更佳`。

---

# 5. `education_major_prefer`

## 含义

专业偏好，不是硬门槛。

## 数据类型

```text
list[string]
```

元素使用和 `education_major_barrier` 同一套专业组。

---

## 从 sentence 判断

| sentence                                         | 输出                                              |
| ------------------------------------------------ | ----------------------------------------------- |
| `计算机科学、数字媒体技术、图形学等相关专业优先，有渲染技术专项研究或行业领先实践经验者更佳；` | `["computer", "design_art"]`                    |
| `本科及以上学历，计算机科学、信息技术、通信工程等相关专业优先。`                | `["computer", "engineering"]`                   |
| `教育背景与经验：本科及以上学历，动画、影视制片、数字媒体、计算机等相关专业优先。`       | `["design_art", "marketing_media", "computer"]` |
| `本科及以上学历，计算机、传媒或市场营销类专业优先。`                      | `["computer", "marketing_media"]`               |
| `本科以上学历，有电影宣发及制作等专业背景优先；`                        | `["marketing_media"]`                           |
| `本科及以上学历，商科相关专业；`                                | `[]`                                            |

---

## 判断规则

只要专业词和这些词绑定，就进入 `major_prefer`：

```text
专业优先
专业背景优先
相关专业优先
为佳
更佳
加分
尤佳
```

核心边界：

```text
计算机相关专业，本科及以上学历     → major_barrier
计算机相关专业优先               → major_prefer
```

---

# 6. 专业组映射规则

MVP 不保存原始专业名，先映射到粗专业组。

| 关键词                                 | 归一专业组             |
| ----------------------------------- | ----------------- |
| 计算机、软件工程、信息技术、网络工程                  | `computer`        |
| 人工智能、机器学习、深度学习、NLP、自然语言处理、模式识别、数据挖掘 | `ai_ml`           |
| 数据科学、数据分析、大数据                       | `data_science`    |
| 数学、统计学、应用数学、运筹、概率                   | `math_stats`      |
| 通信工程、电子、电气、自动化、机械、机电、材料、工业设计        | `engineering`     |
| 商科、工商管理、管理学、国际贸易、供应链管理、电子商务         | `business`        |
| 金融、经济、会计、财务                         | `finance`         |
| 市场营销、传媒、传播、广告、影视制片、电影宣发、新闻          | `marketing_media` |
| 动画、数字媒体、美术、设计、UI、UX、图形学             | `design_art`      |
| 英语、语言、翻译、小语种                        | `language`        |
| 法学、法律                               | `law`             |
| 医学、药学、护理、临床                         | `medical`         |
| 教育学、教育技术学                           | `education`       |
| 其他明确专业但不想细分                         | `other`           |
| 相关专业但无法判断方向                         | `unknown`         |

---

# 7. `education_parse_status`

## 含义

一个岗位聚合 API education、requirements 和 description 后，
education 信息是否能够稳定写入 clean。

`education_parse_status` 是岗位级状态，不是单条 evidence 的审核状态。

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
not_education
```

## 岗位级 parse_status 聚合顺序

当一个岗位存在多个 education 来源或多个候选句时，按以下顺序确定最终状态：

```text
conflict
→ partial
→ ok
→ not_education
→ unknown
```

解释：

- API/text 有冲突，最终为 conflict。
- 存在真实 education 信息但只解析出一部分，最终为 partial。
- 存在至少一个可稳定归一的 education 要求，最终为 ok。
- 没有真实 education 信息，但存在被确认是假阳性的候选句，最终为 not_education。
- API 为空且文本没有任何 education 信息，最终为 unknown。

只要存在有效 education 要求，其他 not_education 假阳性句不得覆盖有效结果。

---

## 判断规则

| 状态 | 判断标准 | 例子 |
|---|---|---|
| `ok` | 明确教育要求或明确“学历不限”，并且可以稳定归一 | `本科及以上学历`、`学历不限` |
| `partial` | 一部分教育信息明确，另一部分无法稳定归一 | `本科及以上学历，相关专业优先` |
| `unknown` | 明显涉及教育但无法归一；或者 API、requirements、description 均未提供教育要求 | `良好的教育背景`；所有来源均无教育信息 |
| `conflict` | API education 与文本提取结果存在实质冲突 | API `本科`，文本 `硕士及以上学历` |
| `not_education` | 命中的候选句经判断并不是学历或专业背景要求 | `负责数据中心电气专业设计` |
---

## 什么算 `ok`

满足任一即可：

```text
degree_barrier 能明确解析
major_barrier 能明确解析
degree_prefer 能明确解析
major_prefer 能明确解析
```

并且没有冲突。

例子：

```text
本科及以上学历，商科相关专业；
```

输出：

```json
{
  "education_degree_barrier": "bachelor_plus",
  "education_major_barrier": ["business"],
  "education_parse_status": "ok"
}
```

---

## 什么算 `partial`

有明确 education 信息，但部分信息无法稳定归一。

例子：

```text
本科及以上学历，相关专业优先；
```

输出：

```json
{
  "education_degree_barrier": "bachelor_plus",
  "education_major_prefer": ["unknown"],
  "education_parse_status": "partial"
}
```

原因：

```text
本科及以上学历 → 清楚
相关专业优先 → 知道是专业偏好，但不知道是什么专业
```

---

## 什么算 `unknown`

明显和 education 有关，但无法变成可分析字段。

例子：

```text
良好的教育背景
```

输出：

```json
{
  "education_degree_barrier": "unknown",
  "education_degree_prefer": [],
  "education_major_barrier": [],
  "education_major_prefer": [],
  "education_parse_status": "unknown"
}
```

---

## 什么算 `not_education`

句子里虽然有“专业”两个字，但不是学历/专业背景要求。

例子：

```text
负责新建及改造数据中心电气专业的设计及技术方案审核与评估
```

这里的“电气专业”是工作职责里的专业领域，不是“电气专业学历背景”。

输出：

```json
{
  "education_degree_barrier": "unknown",
  "education_degree_prefer": [],
  "education_major_barrier": [],
  "education_major_prefer": [],
  "education_parse_status": "not_education"
}
```

---

## 明确不限与无信息必须区分

### 情况 1：明确写“学历不限”
#### 含义：岗位明确声明不存在学历硬门槛。

输入：

```text
学历不限
```

输出：
```json
{
  "education_degree_barrier": "none",
  "education_degree_prefer": [],
  "education_major_barrier": [],
  "education_major_prefer": [],
  "education_parse_status": "ok",
  "education_source": {
    "degree_barrier": "text_rule",
    "degree_prefer": "none",
    "major_barrier": "none",
    "major_prefer": "none"
  }
}
```

### 情况2：API 和文本都没有 education 信息
#### 含义：无法确认岗位是否有学历要求，不等于岗位明确学历不限。

输入状态：

```text
education API 为空
requirements 中没有学历或专业背景信息
description 中没有学历或专业背景信息
```

输出：

```json
{
  "education_degree_barrier": "unknown",
  "education_degree_prefer": [],
  "education_major_barrier": [],
  "education_major_prefer": [],
  "education_parse_status": "unknown",
  "education_source": {
    "degree_barrier": "none",
    "degree_prefer": "none",
    "major_barrier": "none",
    "major_prefer": "none"
  }
}
```

### 情况3：候选句不是 education 要求

输入：

```text
负责数据中心电气专业设计
```

输出：

```json
{
  "education_degree_barrier": "unknown",
  "education_degree_prefer": [],
  "education_major_barrier": [],
  "education_major_prefer": [],
  "education_parse_status": "not_education",
  "education_source": {
    "degree_barrier": "none",
    "degree_prefer": "none",
    "major_barrier": "none",
    "major_prefer": "none"
  }
}
```
not_education 只用于已命中的候选句被确认是假阳性。

不能把“完全没有匹配到任何 education 信息”写成 not_education。
完全没有信息必须写成 unknown。

---

# 8. `education_source`

## 含义

每个 education 字段来自哪里。

## 数据类型

```json
{
  "degree_barrier": "api | text_rule | manual | none | conflict",
  "degree_prefer": "text_rule | manual | none",
  "major_barrier": "api | text_rule | manual | none | conflict",
  "major_prefer": "text_rule | manual | none"
}
```

---

## 例子

```json
{
  "degree_barrier": "text_rule",
  "degree_prefer": "none",
  "major_barrier": "text_rule",
  "major_prefer": "none"
}
```

---

## 它给谁用

| 消费端         | 怎么用                            |
| ----------- | ------------------------------ |
| analysis 脚本 | `conflict` 时放入 grey            |
| 你           | 排查某个岗位为什么被判 rejected / grey    |
| 后续规则维护      | 判断 API 字段可靠，还是 text_rule 补出来的多 |

它不是岗位好坏判断字段。
它是字段来源追踪字段。

---

# 9. 从 sentence 判断字段的顺序

不要一开始就抽专业。
建议固定顺序：

```text
1. 文本标准化
2. 切分硬要求区域 / 偏好区域
3. 抽 degree barrier
4. 抽 degree prefer
5. 抽 major barrier
6. 抽 major prefer
7. 判断 parse_status
8. 写 source
```

---

## 9.1 文本标准化

先统一这些写法：

| 原始写法      | 统一      |
| --------- | ------- |
| `本科以上`    | `本科及以上` |
| `本科或以上`   | `本科及以上` |
| `硕士以上`    | `硕士及以上` |
| `研究生及以上`  | `硕士及以上` |
| `大学本科`    | `本科`    |
| `专科`、`大专` | `专科/大专` |

---

## 9.2 切分 hard / prefer

遇到这些词，相关片段进入 prefer：

```text
优先
加分
更佳
尤佳
为佳
可考虑
```

例子：

```text
本科及以上学历，计算机、传媒或市场营销类专业优先。
```

切成：

```text
hard_part = 本科及以上学历
prefer_part = 计算机、传媒或市场营销类专业优先
```

输出：

```json
{
  "education_degree_barrier": "bachelor_plus",
  "education_major_prefer": ["computer", "marketing_media"]
}
```

---

# 10. 典型 sentence 输出示例

## 例子 1：学历 + 专业硬门槛

```text
本科及以上学历，商科相关专业；
```

```json
{
  "education_degree_barrier": "bachelor_plus",
  "education_degree_prefer": [],
  "education_major_barrier": ["business"],
  "education_major_prefer": [],
  "education_parse_status": "ok",
  "education_source": {
    "degree_barrier": "text_rule",
    "degree_prefer": "none",
    "major_barrier": "text_rule",
    "major_prefer": "none"
  }
}
```

---

## 例子 2：专业在学历前面

```text
计算机相关专业本科及以上学历，3年以上java后端开发经验；
```

```json
{
  "education_degree_barrier": "bachelor_plus",
  "education_degree_prefer": [],
  "education_major_barrier": ["computer"],
  "education_major_prefer": [],
  "education_parse_status": "ok",
  "education_source": {
    "degree_barrier": "text_rule",
    "degree_prefer": "none",
    "major_barrier": "text_rule",
    "major_prefer": "none"
  }
}
```

---

## 例子 3：学历硬门槛 + 学历偏好 + 多专业硬门槛

```text
教育背景：人工智能、计算机科学、数学或相关专业，硕士及以上学历，博士优先；
```

```json
{
  "education_degree_barrier": "master_plus",
  "education_degree_prefer": ["phd_plus"],
  "education_major_barrier": ["ai_ml", "computer", "math_stats"],
  "education_major_prefer": [],
  "education_parse_status": "ok",
  "education_source": {
    "degree_barrier": "text_rule",
    "degree_prefer": "text_rule",
    "major_barrier": "text_rule",
    "major_prefer": "none"
  }
}
```

---

## 例子 4：只有专业偏好

```text
计算机科学、数字媒体技术、图形学等相关专业优先，有渲染技术专项研究或行业领先实践经验者更佳；
```

```json
{
  "education_degree_barrier": "unknown",
  "education_degree_prefer": [],
  "education_major_barrier": [],
  "education_major_prefer": ["computer", "design_art"],
  "education_parse_status": "ok",
  "education_source": {
    "degree_barrier": "none",
    "degree_prefer": "none",
    "major_barrier": "none",
    "major_prefer": "text_rule"
  }
}
```

注意：这里不能把 `计算机科学、数字媒体技术、图形学` 写进 `major_barrier`。

---

## 例子 5：学历硬门槛 + 专业偏好

```text
本科及以上学历，计算机科学、信息技术、通信工程等相关专业优先。
```

```json
{
  "education_degree_barrier": "bachelor_plus",
  "education_degree_prefer": [],
  "education_major_barrier": [],
  "education_major_prefer": ["computer", "engineering"],
  "education_parse_status": "ok",
  "education_source": {
    "degree_barrier": "text_rule",
    "degree_prefer": "none",
    "major_barrier": "none",
    "major_prefer": "text_rule"
  }
}
```

---

## 例子 6：学校偏好不进 MVP

```text
本科及以上学历，国内外优秀院校优先；
```

```json
{
  "education_degree_barrier": "bachelor_plus",
  "education_degree_prefer": [],
  "education_major_barrier": [],
  "education_major_prefer": [],
  "education_parse_status": "ok",
  "education_source": {
    "degree_barrier": "text_rule",
    "degree_prefer": "none",
    "major_barrier": "none",
    "major_prefer": "none"
  }
}
```

`国内外优秀院校优先` 先不进 MVP。
它不是 degree，也不是 major。后面如果你要做排序，再加 `school_prefer`。


---

# 11. 最终冻结版 schema

```json
{
  "education_degree_barrier": "bachelor_plus",
  "education_degree_prefer": [],
  "education_major_barrier": ["computer"],
  "education_major_prefer": [],
  "education_parse_status": "ok",
  "education_source": {
    "degree_barrier": "text_rule",
    "degree_prefer": "none",
    "major_barrier": "text_rule",
    "major_prefer": "none"
  }
}
```

---

# 12. MVP 判断边界

| 情况             | MVP 处理                        |
| -------------- | ----------------------------- |
| 学历明确           | 写入 `education_degree_barrier` |
| 学历优先           | 写入 `education_degree_prefer`  |
| 专业明确且不是优先      | 写入 `education_major_barrier`  |
| 专业优先/背景优先      | 写入 `education_major_prefer`   |
| 只有学校优先         | 先不建字段                         |
| 只有“相关专业”但不知道方向 | `unknown`，通常 `partial`        |
| 有“专业”但不是学历背景   | `not_education`               |
| API 和文本学历冲突    | `conflict`                    |
| confidence     | 留在 review，不进 clean MVP        |

最后冻结成一句话：

```text
education 只回答 4 件事：
硬性学历、偏好学历、硬性专业、偏好专业。
```
