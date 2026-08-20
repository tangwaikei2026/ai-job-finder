| 字段                         | 数据类型           | 例子                               | 必须/延后 | 来源 | 作用                           |
| -------------------------- | -------------- | -------------------------------- | ----- | ---------------------------- |
| `job_id` | `string` | `7624476433381869860` | 必须 | 平台原始岗位 ID | 单个平台内定位岗位 |
| `platform` | `string` | `feishu` | 必须 | 当前 collector / 配置里的平台标识 | 平台来源；与 `job_id` 共同组成唯一键 |
| `title` | `string` | `AI应用评测工程师` | 必须 | 平台列表页或详情页返回的岗位标题 | 人工快速判断岗位方向 |
| `company` | `string` | `智谱AI` | 必须 | 平台列表页或详情页返回的公司名 | 人工快速判断公司来源，也可用于公司维度统计 |
| `city_norm` | `string` | `深圳` | 必须 | 平台列表页或详情页返回的location | 岗位所在城市，不符合直接reject |
| `education_degree_barrier` | `string enum`  | `bachelor_plus`                  | 必须    | api / text_rule / manual | 判断学历硬门槛                      |
| `education_degree_prefer`  | `list[string]` | `["phd_plus"]`                   | 必须    | api / text_rule / manual | 判断学历偏好，不直接 reject            |
| `education_major_barrier`  | `list[string]` | `["computer"]`                   | 必须    | api / text_rule / manual | 判断专业硬门槛                      |
| `education_major_prefer`   | `list[string]` | `["computer", "design"]`     | 必须    | api / text_rule / manual | 判断专业偏好，不直接 reject            |
| `education_parse_status`   | `string enum`  | `ok`、`partial`                   | 必须    | api / text_rule / manual 聚合判断 | 判断 education 字段是否稳定可用            |
| `education_source`         | `object`       | `{"degree_barrier":"text_rule"}` | 必须    | 字段来源追踪 | 追踪字段来源，避免 analysis 回查 review |
| `experience_min_years`        | `number \| null` | `3`、`5`、`0`、`null`               | 必须    | api / text_rule / manual | 判断最低年限门槛          |
| `experience_max_years`        | `number \| null` | `5`、`2`、`null`                   | 必须    | api / text_rule / manual | 处理 `3-5年`、`0-2年`  |
| `experience_years_bucket`     | `string enum`    | `3_5`                            | 必须    | 由 experience_min_years 派生 | 统计和粗筛，不直接reject             |
| `experience_requirement_type` | `string enum`    | `hard_min`、`range`、`prefer_only` | 必须    | api / text_rule / manual  | 区分硬要求/范围/优先       |
| `experience_required_tags`    | `list[string]`   | `["game", "operations"]`         | 必须    | api / text_rule / manual | 表示硬性经验方向          |
| `experience_prefer_tags`      | `list[string]`   | `["overseas"]`                   | 必须    | api / text_rule / manual | 表示优先经验，不用于 reject |
| `experience_parse_status`     | `string enum`    | `ok`、`partial`、`unknown`         | 必须    | api / text_rule / manual 聚合判断 | 判断解析结果能不能用        |
| `experience_source`           | `object`         | `{"years":"text_rule"}`          | 必须    | 字段来源追踪 | 追踪来源，避免回查 review  |