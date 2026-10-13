# 测试策略

执行权限以 [AGENTS.md](../AGENTS.md) 为准；当前链路、业务契约及审计缺口统一记录在 [工程工作手册](workbook.md#生产主链路与业务契约)。本文列出测试设计与证据标准，不授权真实抓取、生产重跑或后续批次。

## 1. 测试分层

### 纯解析单元测试

目标：

- 验证固定 payload 到 RawJobPosting 的映射。
- 验证字段 fallback、类型保护和 schema 校验。

要求：

- 不访问网络。
- 不启动浏览器。
- 使用最小、可读、脱敏 fixture。

### Collector 行为测试

目标：

- 验证分页、关键词遍历、去重、过滤、manifest 和失败回退。

要求：

- mock `_browser_page` 和实际请求边界。
- 保留真实 collector 主流程。
- 验证 status、complete、stopped_by 和计数器。

### 输出契约测试

目标：

- 验证输出仍为现有 RawJobPosting 格式。
- 验证原子写入和失败时旧文件保护。

要求：

- 使用 `tmp_path`。
- 比较落盘 JSON 与 `job.to_dict()`。
- 不向仓库 `data/raw` 写测试产物。

### 全量回归测试

目标：

- 确认新平台没有改变已有 adapter、模型和 pipeline 行为。

要求：

- 平台专项测试通过后运行全部 pytest。
- 不通过删除或弱化已有测试换取绿灯。

### 生产环境验证（原 Live smoke）

目标：

- 验证浏览器二进制、系统权限、网络、反爬和实时响应结构。

要求：

- 与离线单元测试分开；必须满足 AGENTS.md 的 Explicit Production Execution Exception，通过正式 production entrypoint。
- 不因旧“小关键词集和低页数”指南临时变更生产 source scope 或编写 probe；沿用获准范围与已有 collector contract。
- 记录运行环境、时间、结果数量、失败类型和产物引用。
- 失败保留产物与错误证据并停止，不人工重复 Crawl；本节不产生生产执行授权。

## 2. 新平台最低测试矩阵

| 场景 | 必须验证 |
|---|---|
| 正常列表 | 字段映射、RawJobPosting 类型、manifest 成功 |
| 重复岗位 | 按稳定 job_id 去重、重复计数正确 |
| 平台格式变化 | 不崩溃、不误报成功、错误可诊断 |
| 字段缺失 | 安全 fallback、无 ID 记录被跳过 |
| 分页失败 | 保留前页结果、manifest 为 partial |
| 城市过滤 | 范围内保留、范围外计数 |
| 平台来源过滤 | 猎头等来源治理有效 |
| 输出失败 | 不击穿 collector、manifest 有错误 |
| 完全失败 | 不覆盖旧输出 |
| 原有平台 | 全量测试无回归 |

若任务明确缩小范围，可先实现其中的核心项，但未覆盖项必须进入风险和后续计划。

## 3. 猎聘专项测试记录

以下为 `tests/test_liepin_collector.py` 可静态定位的用例，不代表本批运行通过。

### 已有测试

1. 正常列表解析
   - 遍历多个关键词。
   - 每关键词只请求第 0 页。
   - 映射岗位 ID、标题、公司、地点、薪资、经验和学历。
   - 输出 `raw_job.json`。

2. 重复岗位
   - 两个关键词返回相同 job_id。
   - 最终只保留一条。
   - `duplicate_records` 增加。

3. 平台返回格式变化
   - 将 `jobCardList` 改为未知字段。
   - Collector 返回 error manifest。
   - 不抛出到 pipeline。
   - 不创建或覆盖人工复核文件。

### 历史补充清单（不是本次下一批授权）

先检查其他测试文件是否已有覆盖，再决定补充，避免重复实现。

1. 一个关键词失败，其他关键词成功。
2. 列表字段缺失和 job_id 缺失。
3. 城市过滤。
4. 猎头岗位过滤。
5. 完全失败时保留已有输出。
6. 空搜索结果允许写入空列表。
7. 浏览器初始化失败。

## 4. 测试数据规则

- Fixture 不包含真实 Cookie、账号、动态 token 或个人联系方式。
- 只保留解析所需字段。
- 响应结构来自真实样本时必须脱敏。
- 不提交大体积 raw 数据。
- 实时生成的时间字段断言验证存在和格式，不硬编码机器当前时间；已有 invocation 边界测试使用冻结时钟构造开始日、次日、第三日场景，不代表改变生产时钟或日期语义。

## 5. 验收命令

猎聘专项测试：

```bash
python3 -m pytest tests/test_liepin_collector.py -q
```

全量测试：

```bash
python3 -m pytest -q
```

受限环境语法检查：

```bash
PYTHONPYCACHEPREFIX=/tmp/ai-job-finder-pycache \
python3 -m py_compile \
  src/collectors/liepin.py \
  tests/test_liepin_collector.py
```

Diff 检查：

```bash
git diff --check
git diff --name-status master
git diff --stat master
```

## 6. 业务不变量与证据状态

| 既有契约 | 代码 owner | 已有测试文件与代表用例 |
|---|---|---|
| Canonical 唯一资格权威；探索模式分离 | `canonical_report.py`、`ai_eval_jobs.py::run_analysis` | `tests/test_canonical_candidate_report.py::test_identity_grouping_authority_and_skill_denominator`、`test_exploration_is_explicit_and_namespaced` |
| `(platform, job_id)` 身份去重、冲突拒绝；正文分组只影响展示 | `lifecycle.py::index_jobs`、`canonical_report.py` | `tests/test_market_pipeline.py::test_identity_dedup_and_conflict`；候选报告身份／分母用例 |
| 深圳正向匹配、否定否决、冲突提示；不改变 city_norm / Fit | `candidate_city.py` | `tests/test_candidate_city.py`、`tests/test_canonical_candidate_report.py::test_city_uses_frozen_matcher` |
| SourceHealth 可靠性分层；有限详情容忍不改变 completeness | `source_health.py`、`classification.py`、`daily_health.py` | `tests/test_sourcehealth_reliability_v2.py`、`tests/test_detail_gap_tolerance.py`、`tests/test_market_pipeline.py::test_incomplete_source_never_advances_removal` |
| invocation、摘要、日期窗口、失败保护 | `src/invocation.py`、`tools/run_daily.py` | `tests/test_invocation.py::test_same_and_next_day_real_offline_stage_chain`、`test_third_day_rejected_before_retry`、`test_failed_second_clean_preserves_previous_published_observation` |

证据分级：

- **静态确认**：读取代码、配置或测试断言后可定位的事实；不能据此宣称运行通过。
- **已有测试未运行**：记录文件和用例。本批以上用例均属此状态；缓存文件和历史测试名称不是本批通过证据。
- **运行通过／失败**：只有执行后才能记录，附命令、环境、退出结果和适用范围；mock Runner 测试不能代替真实离线阶段贯通。
- **用户确认**：明确注明用户、确认日期及具体事实；GitHub 近期自动触发及最近采集失败见 workbook，不等于本代理独立验读运行日志。
- **尚未验证**：没有执行证据的运行效果、失败根因或缺口复现；不得以“历史回放已验证”等字段名推定完整正确性。

## 7. 待确认的第二批离线测试设计

优先复用现有文件与 fixture，不新增另一套验证器或业务规则：

1. `tests/test_invocation.py`：多日期 replay 中的缺失证明、混合 invocation、篡改产物，以及拒绝后正式输出保留。区分 modern 与 legacy，不扩大日期窗口。
2. `tests/test_daily_orchestration.py`：使用真实离线 Runner/Clean/Analysis 和临时目录，mock 采集边界及通知外部发送；模拟首次 clean/analysis 失败与已有旧正式产物，检查恢复是否读取对应 invocation staging、不重抓。
3. `tests/test_canonical_candidate_report.py`：现代分类文件截断、同日不同 invocation 混用、证明不一致；保留合法空候选、既有 legacy 与 carried_forward 的业务用例，避免用一律拒绝历史输入换取通过。

统一使用冻结时钟、离线 fixture 和临时目录，避免写生产 data；新增失败如实报告，不修改生产实现或弱化断言。本节仅为计划，本批未实现、未运行，需用户确认第二批后执行。

## 8. 2026-10-13 第一批文档整理验收记录

- 范围：只修改 `AGENTS.md`、`docs/workbook.md`、`docs/test_strategy.md`，不改代码、测试、调度、历史数据，不提交。
- 原因：AGENTS 合并重复说明并标记历史范围；workbook 统一主链路、事实来源与缺口；本文统一测试证据状态与后续边界用例。
- 开工证据：`git branch --show-current`、`git rev-parse --short HEAD`、`git rev-parse master origin/master origin/taxonomy`、`git status --short`、`git diff master...HEAD --stat`、`git diff --stat`。分支／提交及 44 个既有未跟踪文件见 workbook。
- 静态核对：通过 `cat`、`sed`、`rg -n` 读取三份文档、正式入口、invocation、SourceHealth、候选报告、workflow 与相关测试；没有调用生产入口或抓取网站。
- 验收命令：`git diff --check`、`git diff --name-only`、`git status --short`、`git diff --stat`、`git diff -- AGENTS.md docs/workbook.md docs/test_strategy.md`；另用内存脚本核对修改范围、生产授权条款原文、保留限制和 Markdown 本地链接。
- 编译及 pytest：本批为文档整理，按用户要求检查一致性、范围和 diff；未执行 `compileall` 或 pytest，不声称回归通过，也不把本批验收方式扩展成永久豁免。
- 完整 diff 与命令输出保留在本批会话工具记录；未提交前可用上述 diff 命令复核。
- 验收结果：`git diff --check` 通过；范围检查仅三份允许文档；生产授权／调度条款、仓库实现约束、固定验收和 diff 要求与 HEAD 原文相同，其他限制及停止要求保留；本地链接、锚点、代码围栏检查通过。最终 status 为三份文档修改及 44 个既有未跟踪数据路径，暂存区为空。
