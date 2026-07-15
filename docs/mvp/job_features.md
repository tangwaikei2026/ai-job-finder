## 字段类型说明
| 字段                            | 类型                | 例子                                   | 枚举值                                                          | 用途                 |
| ----------------------------- | ----------------- | ------------------------------------ | ------------------------------------------------------------ | ------------------ |
| `job_id`                      | `string`          | `7624476433381869860`                |                                                              | 定位岗位               |
| `platform`                    | `string`          | `feishu`                             |                                                              | 按平台统计              |
| `title`                       | `string`          | `AI应用评测工程师`                          |                                                              | 人工快速判断             |
| `company`                     | `string`          | `智谱AI`                               |                                                              | 人工快速判断             |
| `city_norm`                   | `string enum`     | `深圳`                                 |标准化城市名称                                   |  job_features 中的单一城市展示值；城市是否匹配仍基于 clean 中完整城市集合判断           |
| `education_degree_barrier`    | `string enum`     | `bachelor_plus`                      | `none;associate_plus;bachelor_plus;master_plus;phd_plus;unknown` | 判断学历硬门槛            |
| `education_degree_prefer`     | `list[string]`    | `master_plus;phd_plus`               | `bachelor_plus;master_plus;phd_plus`                         | 学历偏好，不直接 reject    |
| `education_major_barrier`     | `list[string]`    | `computer;ai_ml`                     |                                                              | 判断专业硬门槛            |
| `education_major_prefer`      | `list[string]`    | `computer;design_art`                |                                                              | 专业偏好，不直接 reject    |
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
| `final_pool`                  | `string enum`     | `candidate`                          |                                                              | 最终岗位池              |
| `final_reason_codes`          | `list[string]`    | `city_ok;education_ok;experience_ok` |                                                              | 解释为什么进入该池          |



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
| 12 | 硬年限满足，required tags 为空或只命中 acceptable tags | `pass` | `years_ok;experience_required_tags_match` |
| 13 | `requirement_type=prefer_only` | `pass` | `prefer_only_not_blocking` |


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
| 10 | 只有专业偏好不匹配 | `pass` | `degree_ok;major_prefer_only` |
| 11 | 只有学历偏好不匹配 | `pass` | `degree_prefer_only;major_ok` |

---

## city_norm 映射规则

`city_norm` 必须是单个字符串。

上游 clean 当前可能包含多个标准化城市，因此生成 job_features 时按以下规则输出：

1. 使用 clean 中完整的城市集合判断是否命中 `target_profile.target_cities`。
2. 如果命中一个或多个目标城市：
   - 按 `target_profile.target_cities` 的配置顺序，输出第一个命中的目标城市。
3. 如果没有命中目标城市，但存在标准化城市：
   - 输出 clean 城市集合中的第一个城市。
4. 如果没有可用城市：
   - CSV 中写空字符串。

### 例子1：

```text
clean city_norm = ["北京", "深圳"]
target_cities = ["深圳"]
```

输出：
```text
job_features.city_norm = 深圳
city 判断 = pass
```

### 例子2：

```text
clean city_norm = ["北京", "上海"]
target_cities = ["深圳"]
```

输出：
```text
job_features.city_norm = 北京
city 判断 = reject
```