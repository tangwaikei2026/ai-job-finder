任务：接入新平台{platform}，目标是抓取符合岗位池规则的岗位，并接入现有raw下的 pipeline。
### 现有 raw adapter 架构

- 所有平台继承 [`RawCollector` (line 17)](/Users/waikei/Documents/Codex/ai-job-finder/src/raw/base.py:17)，复用 HTTP client、重试、超时和城市范围判断。
- `collect()` 返回 `CollectionResult`，其中包含：
    - `list[RawJobPosting]`
    - `CollectionManifest`
- 标准字段由 [`RawJobPosting` (line 15)](/Users/waikei/Documents/Codex/ai-job-finder/src/raw/models.py:15) 固定。
- 平台通过 [`COLLECTOR_REGISTRY` (line 12)](/Users/waikei/Documents/Codex/ai-job-finder/src/raw/collectors/__init__.py:12) 注册。
- [src/raw/main.py (line 36)](/Users/waikei/Documents/Codex/ai-job-finder/src/raw/main.py:36) 负责按配置运行、合并结果、原子写 `data/raw` 和 manifest。
- 配置集中在 [raw_config.yaml (line 1)](/Users/waikei/Documents/Codex/ai-job-finder/raw_config.yaml:1)；
- 普通平台直接访问 API；滴滴、美团等在列表后补详情；详情失败保留基础岗位并计入 `detail_failed`。字节、飞书才使用浏览器捕获动态 API。
- raw pipeline 当前明确是“全量采集 + 城市范围”，不是岗位相关性过滤，见 [raw_config.yaml (line 6)](/Users/waikei/Documents/Codex/ai-job-finder/raw_config.yaml:6) 和 [src/raw/main.py (line 53)](/Users/waikei/Documents/Codex/ai-job-finder/src/raw/main.py:53)。
- `src/raw` 与旧的 `src/main.py + src/scrapers` 是两条独立链路；本任务应只接 `src/raw`。


请分两步执行：

第一步：只输出接入方案、风险点、需要修改的文件、测试计划，不改代码
一、先做盘点，不要改代码
1. 判断该平台属于哪类：
   - company_api
   - ATS 平台
   - 普通网页
   - 需要浏览器自动化
   - 需要登录/高反爬
2. 获取稳定的获取信息的方式
3. 验证输出该平台字段来源：
   - 列表页能拿到哪些字段
   - 详情页能拿到哪些字段
   - 哪些字段可能缺失
4. 说明是否需要单独 JD 详情补全逻辑。
5. 说明风险点，不要开始实现。
6. 指出需要修改的文件

二、验收标准
1. 能单独运行该平台抓取，返回 RawJobPosting 列表。
2. 每条岗位必须包含：
      - job_id
	   - platform
	   - title
	   - company
	   - department
	   - location
	   - experience
	   - education
	   - salary
	   - description
	   - requirements
	   - url
	   - scraped_at
3. 如果 JD 详情可获得，应填充 description/requirements。
4. 如果详情页失败，应保留列表页基础信息，并标记缺失原因或安全跳过。
5. 不能影响已有平台运行。
6. 不能改变已有 README 输出格式。
7. 至少新增以下测试：
   - 正常列表解析
   - 原有平台正常运行
   - 抓取目标岗位
   - 分页失败
   - 字段缺失
   - 详情页失败
   - 重复岗位去重
   - 城市过滤
8. 制定测试计划

第二步：等我确认后，只按确认后的范围实现，但请严格按小步提交，不要一次性大改。

一、实现约束
1. 只实现我刚刚确认过的方案。
2. 不要修改现有岗位池规则，除非我明确要求。
3. 不要修改已有平台 adapter 的行为。
4. 不要改变 README / jobs 输出格式。
5. 不要新增浏览器自动化，除非该平台必须依赖它，并先说明原因。
6. 不要新增数据库、队列、调度系统等重型依赖。
7. 不要新增方案外的重构。
8. 新平台逻辑必须放在独立 adapter 文件中，并且必须加注释。
9. 平台特殊逻辑只能放在该平台 adapter 或 platform_fixes 中，不要写进 main.py。
10. 字段标准化后必须输出现有 RawJobPosting 结构
11. 不要改变现有输出格式。
12. 请求失败、字段缺失、详情页失败时不能导致整个 pipeline 崩溃。
13. 新增配置必须写入 raw_config.yaml（不要把简单配置写死到代码里）：只能配置name, xx_api, xx_url,page_size,enable. 如需要增加的配置，需要先向我确认，再确认允许之后再增加新的配置。默认enable


二、只搭骨架
请先完成：
1. 新增该平台 adapter 文件
2. 接入现有 RawCollector / CollectorRegistry / config
3. 保持默认 enable
4. 不写复杂解析逻辑，只保证结构能被调用

完成后请停止，并输出：
- 修改了哪些文件
- 为什么改这些文件
- 如何运行单平台 smoke test
- 当前还没实现什么

三、实现列表页解析
在我确认【只搭骨架】后，再实现：
1. 请求列表页
2. 分页
3. 映射成 RawJobPosting
4. 字段缺失保护
5. job_id 去重

验收：
- 能返回岗位列表
- title/company/location/url/platform/job_id/description不为空或有 fallback
- 请求失败不导致整个 pipeline 崩溃

四、实现详情页补全
在我确认【实现列表页解析】后，再实现：
1. 详情页请求
2. description/requirements 补全
3. 详情页失败时保留列表页信息
4. manifest 记录详情失败数量

验收：
- 详情成功时 JD 字段完整
- 详情失败时不丢岗位、不崩溃
- manifest 能看出失败原因

五、执行之前已经制定好的测试计划
不要为了测试去大改业务代码。

六、最终自检
请运行：
1. 单平台采集命令
2. 全部测试
3. lint/format 如果项目已有

最后输出：
- 最终修改文件列表
- 已覆盖场景
- 未覆盖风险
- 是否建议开启该平台
- 后续改进建议
