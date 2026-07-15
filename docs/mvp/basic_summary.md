|字段|类型|例子|用途|
|---|---|---|---|
|`total_jobs`|`number`|`20842`|总岗位数|
|`final_pool_counts`|`object`|`{"candidate": 320, "rejected": 18000, "grey": 2522}`|看最终分池比例|
|`city_counts`|`object`|`{"深圳": 5000, "北京": 6000}`|看城市分布|
|`education_decision_counts`|`object`|`{"pass": 9000, "reject": 3000, "grey": 800}`|看 education 筛选影响|
|`experience_decision_counts`|`object`|`{"pass": 7000, "reject": 5000, "grey": 1000}`|看 experience 筛选影响|
|`education_parse_status_counts`|`object`|`{"ok": 8000, "partial": 1000, "unknown": 300}`|看 education 解析质量|
|`experience_parse_status_counts`|`object`|`{"ok": 6500, "partial": 1200, "unknown": 500}`|看 experience 解析质量|
|`top_reject_reason_codes`|`object`|`{"years_too_high": 3000}`|看主要淘汰原因|
|`top_grey_reason_codes`|`object`|`{"experience_mixed_requirement": 800}`|看主要不确定原因|