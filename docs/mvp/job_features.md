## 字段类型说明
| 字段                            | 类型                | 例子                                   | 枚举值                                                          | 用途                 |
| ----------------------------- | ----------------- | ------------------------------------ | ------------------------------------------------------------ | ------------------ |
| `job_id`                      | `string`          | `7624476433381869860`                |                                                              | 定位岗位               |
| `platform`                    | `string`          | `feishu`                             |                                                              | 按平台统计              |
| `title`                       | `string`          | `AI应用评测工程师`                          |                                                              | 人工快速判断             |
| `company`                     | `string`          | `智谱AI`                               |                                                              | 人工快速判断             |
| `city_norm`                   | `string | empty`     | `深圳`                                 |  标准化城市名称                           |  job_features 中的单一城市展示值；      |
| `city_decision`     | `string enum`  | `pass`       |  `pass;reject`                           | 判断岗位城市是否命中目标城市       |
| `city_reason_codes` | `list[string]` | `city_match` |  `city_match;city_mismatch;city_unknown` | 解释 city_decision 的原因 |
| `education_degree_barrier`    | `string enum`     | `bachelor_plus`                      | `none;associate_plus;bachelor_plus;master_plus;phd_plus;unknown` | 判断学历硬门槛            |
| `education_degree_prefer`     | `list[string]`    | `master_plus;phd_plus`               | `bachelor_plus;master_plus;phd_plus`                         | 学历偏好，不直接 reject    |
| `education_major_barrier`     | `list[string]`    | `computer;ai_ml`                     |                                                              | 判断专业硬门槛            |
| `education_major_prefer`      | `list[string]`    | `computer;design`                |                                                              | 专业偏好，不直接 reject    |
| `education_parse_status`      | `string enum`    | `ok`                                 | `ok;partial;unknown;conflict;not_education`                  | 判断字段是否稳定           |
| `education_decision`          | `string enum`     | `pass`                               | `pass;reject;grey`                                           | education 维度判断     |
| `education_reason_codes`      | `list[string]`    | `degree_ok;major_ok`                 |                                                              | 解释 education 判断原因  |
| `experience_min_years`        | `number \| empty` | `3`                                  |                                                              | 判断最低年限             |
| `experience_max_years`        | `number \| empty` | `5`                                  |                                                              | 处理 `3-5年`          |
| `experience_years_bucket`     | `string enum`     | `3_5`                                |                                                              | 年限统计               |
| `experience_requirement_type` | `string enum`     | `hard_min`                           | `hard_min;range;prefer_only;none;mixed;unknown`              | 判断硬要求/偏好/混合        |
| `experience_required_tags`    | `list[string]`    | `ai;testing;data`                    |                                                              | 判断硬经验方向            |
| `experience_prefer_tags`      | `list[string]`    | `overseas;game`                      |                                                              | 偏好经验，不直接 reject    |
| `experience_parse_status`     | `string enum`     | `ok`                                 | `ok;partial;unknown;conflict;not_experience`                 | 判断字段是否稳定           |
| `experience_decision`         | `string enum`     | `pass`                               | `pass;reject;grey`                                           | experience 维度判断    |
| `experience_reason_codes`     | `list[string]`    | `years_ok;experience_required_tags_match`       |                                                              | 解释 experience 判断原因 |
| `final_pool`                  | `string enum`     | `candidate`                          |    `candidate;rejected;grey`                    | 最终岗位池              |
| `final_reason_codes`          | `list[string]`    | `city_ok;education_ok;experience_ok;city_mismatch;education_reject;experience_reject;has_grey_dimension;all_core_dimensions_pass` |                                                              | 解释为什么进入该池          |



## CSV 物理序列化规则

字段表中的 `list[string]` 是逻辑类型。

由于 CSV 没有原生数组类型，所有 `list[string]` 字段统一使用以下规则：

1. 多个元素使用英文分号 `;` 连接。
2. 分号两侧不增加空格。
3. 空列表写成空字符串。
4. 不写 JSON 数组、Python list 字符串、`None`、`null` 或 `nan`。
5. 元素顺序沿用 clean JSONL 中的稳定顺序。
6. 同一字段中的重复元素应在写入 CSV 前去重。

示例：

| clean JSONL | job_features CSV |
|---|---|
| `["computer", "ai_ml"]` | `computer;ai_ml` |
| `["degree_ok", "major_ok"]` | `degree_ok;major_ok` |
| `[]` | 空字符串 |

禁止：

```text
["computer", "ai_ml"]
['computer', 'ai_ml']
computer,ai_ml
[]
None
null
nan
```

本规则适用于：

- city_reason_codes
- education_degree_prefer
- education_major_barrier
- education_major_prefer
- education_reason_codes
- experience_required_tags
- experience_prefer_tags
- experience_reason_codes
- final_reason_codes

---

## experience_decision 控制状态优先级

先判断解析状态和 requirement type，再判断已知硬门槛。

固定顺序：

```text
conflict
→ unknown
→ mixed
→ partial
→ not_experience
→ 已知硬门槛 reject/pass
```

前四项属于控制状态。

只要命中其中一项，就直接返回对应 grey 结果，
不再继续使用年限和 required tags 改判。

---

## experience_decision 执行顺序：

| 优先级 | 条件 | experience_decision | experience_reason_codes |
|---:|---|---|---|
| 1 | `experience_parse_status=conflict` | `grey` | `experience_conflict` |
| 2 | `experience_parse_status=unknown` | `grey` | `experience_unknown` |
| 3 | `experience_requirement_type=mixed` | `grey` | `experience_mixed_requirement` |
| 4 | `experience_parse_status=partial` | `grey` | `experience_partial` |
| 5 | `experience_parse_status=not_experience` | `pass` | `experience_no_requirement` |
| 6 | `experience_parse_status=ok` 且 `experience_requirement_type=none` | `pass` | `experience_no_requirement` |
| 7 | 年限过高，且 required tags 只命中 reject tags | `reject` | `years_too_high;experience_required_tags_mismatch` |
| 8 | `experience_min_years > max_acceptable_experience_years` | `reject` | `years_too_high` |
| 9 | required tags 同时命中 acceptable 和 reject | `grey` | `experience_required_tags_conflict` |
| 10 | required tags 包含未分类或 `unknown` 标签 | `grey` | `experience_required_tags_unknown` |
| 11 | required tags 只命中 reject tags | `reject` | `experience_required_tags_mismatch` |
| 12 | `requirement_type=prefer_only` | `pass` | `prefer_only_not_blocking` |
| 13 | 硬年限满足，required tags 为空或只命中 acceptable tags | `pass` | `years_ok;experience_required_tags_match` |


---

## education_decision 执行顺序

先判断 education_parse_status，再判断已知硬门槛：

| 优先级 | 条件 | education_decision | education_reason_codes |
|---:|---|---|---|
| 1 | `education_parse_status=conflict` | `grey` | `education_conflict` |
| 2 | `education_parse_status=unknown` | `grey` | `education_unknown` |
| 3 | `education_parse_status=partial` | `grey` | `education_partial` |
| 4 | `education_parse_status=not_education` | `pass` | `education_no_requirement` |
| 5 | `education_parse_status=ok` 且 `education_degree_barrier=none`，专业硬门槛为空 | `pass` | `education_no_requirement` |
| 6 | 学历和专业硬门槛都不满足 | `reject` | `degree_too_high;major_mismatch` |
| 7 | 只有学历硬门槛不满足 | `reject` | `degree_too_high;major_ok` |
| 8 | 只有专业硬门槛不满足 | `reject` | `degree_ok;major_mismatch` |
| 9 | 学历满足，专业为空或匹配 | `pass` | `degree_ok;major_ok` |
| 10 | 学历为空或匹配，专业满足 | `pass` | `degree_ok;major_ok` |
| 11 | 只有专业偏好不匹配 | `pass` | `degree_ok;major_prefer_only` |
| 12 | 只有学历偏好不匹配 | `pass` | `degree_prefer_only;major_ok` |
| 13 | 专业和学历偏好都不匹配 | `pass` | `degree_ok;major_ok` |

---

## city_decision 规则

| 条件                                          | city_decision | city_reason_codes |
| ------------------------------------------- | ------------- | ----------------- |
| `city_norm`命中 `target_profile.target_cities` | `pass`        | `city_match`      |
| `city_norm`不为空，但未命中`target_profile.target_cities`        | `reject`      | `city_mismatch`   |
| `city_norm`为空 / unknown / 无法识别          | `reject`      | `city_unknown`    |

---

## final_pool 规则

### 输入字段

`final_pool` 只依赖三个维度判断：

```text
city_decision
education_decision
experience_decision
```

### 判定优先级

固定优先级：

```text
reject > grey > pass
```

### final_pool 判定

| 条件                       | final_pool  |
| ------------------------ | ----------- |
| 任一维度为 `reject`           | `rejected`  |
| 无 `reject`，但任一维度为 `grey` | `grey`      |
| 三个维度全部为 `pass`           | `candidate` |

### final_reason_codes 生成规则

`final_reason_codes` 必须稳定生成，不能只保留首个原因。

固定规则：

1. 按维度顺序收集原因：`city → education → experience`。
2. 同一维度只生成一个 final-level reason。
3. 多个 reject 同时存在时，全部保留。
4. 如果已经进入 `rejected`，只保留 reject 级原因，不再追加 grey 原因。
5. 只有没有 reject 时，才保留 grey 级原因。
6. 三个维度全部 pass 时，只写 `all_core_dimensions_pass`。
7. 写入 CSV 前去重，保持固定顺序。

### final_reason_codes 映射

| 维度状态                                                            | final_reason_code          |
| --------------------------------------------------------------- | -------------------------- |
| `city_decision=reject` 且 `city_reason_codes` 包含 `city_mismatch` | `city_mismatch`            |
| `city_decision=reject` 且 `city_reason_codes` 包含 `city_unknown`  | `city_unknown`             |
| `education_decision=reject`                                     | `education_reject`         |
| `experience_decision=reject`                                    | `experience_reject`        |
| `education_decision=grey`                                       | `education_grey`           |
| `experience_decision=grey`                                      | `experience_grey`          |
| 三个维度全部 pass                                                     | `all_core_dimensions_pass` |

### 示例

| city_decision | education_decision | experience_decision | final_pool  | final_reason_codes                                 |
| ------------- | ------------------ | ------------------- | ----------- | -------------------------------------------------- |
| `reject`      | `reject`           | `reject`            | `rejected`  | `city_mismatch;education_reject;experience_reject` |
| `pass`        | `reject`           | `reject`            | `rejected`  | `education_reject;experience_reject`               |
| `reject`      | `grey`             | `pass`              | `rejected`  | `city_mismatch`                                    |
| `pass`        | `grey`             | `grey`              | `grey`      | `education_grey;experience_grey`                   |
| `pass`        | `pass`             | `grey`              | `grey`      | `experience_grey`                                  |
| `pass`        | `pass`             | `pass`              | `candidate` | `all_core_dimensions_pass`                         |