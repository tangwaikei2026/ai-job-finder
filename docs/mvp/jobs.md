| 字段                         | 数据类型           | 例子                               | 必须/延后 | 作用                           |
| -------------------------- | -------------- | -------------------------------- | ----- | ---------------------------- |
| `education_degree_barrier` | `string enum`  | `bachelor_plus`                  | 必须    | 判断学历硬门槛                      |
| `education_degree_prefer`  | `list[string]` | `["phd_plus"]`                   | 必须    | 判断学历偏好，不直接 reject            |
| `education_major_barrier`  | `list[string]` | `["computer"]`                   | 必须    | 判断专业硬门槛                      |
| `education_major_prefer`   | `list[string]` | `["computer", "design_art"]`     | 必须    | 判断专业偏好，不直接 reject            |
| `education_parse_status`   | `string enum`  | `ok`、`partial`                   | 必须    | 判断 clean 字段是否稳定可用            |
| `education_source`         | `object`       | `{"degree_barrier":"text_rule"}` | 必须    | 追踪字段来源，避免 analysis 回查 review |
| `experience_min_years`        | `number \| null` | `3`、`5`、`0`、`null`               | 必须    | 判断最低年限门槛          |
| `experience_max_years`        | `number \| null` | `5`、`2`、`null`                   | 必须    | 处理 `3-5年`、`0-2年`  |
| `experience_years_bucket`     | `string enum`    | `3_5`                            | 必须    | 统计和粗筛             |
| `experience_requirement_type` | `string enum`    | `hard_min`、`range`、`prefer_only` | 必须    | 区分硬要求/范围/优先       |
| `experience_required_tags`    | `list[string]`   | `["game", "operations"]`         | 必须    | 表示硬性经验方向          |
| `experience_prefer_tags`      | `list[string]`   | `["overseas"]`                   | 必须    | 表示优先经验，不用于 reject |
| `experience_parse_status`     | `string enum`    | `ok`、`partial`、`unknown`         | 必须    | 判断解析结果能不能用        |
| `experience_source`           | `object`         | `{"years":"text_rule"}`          | 必须    | 追踪来源，避免回查 review  |