# Codex 全局执行规则：每个批次都必须遵守

## 项目与范围

- 当前项目：`tangwaikei2026/ai-job-finder`。
- 当前结构、生产主链路与证据边界见 [工程工作手册](docs/workbook.md#生产主链路与业务契约)；验证方法见 [测试策略](docs/test_strategy.md)。这些说明不授予额外执行权限。
- 迁移背景：原目标是围绕 `src` 建立稳定采集主路径、逐步去掉旧路径；当前旧 `src.raw` namespace 已移除，见 `tests/migration/test_migration_contract.py`。
- 历史分支约定：`clean_mvp` 允许修改 `src/clean`、`src/analysis`、`configs/normalization` 和对应 tests。此处保留该约定，不将其当作当前批次的修改清单或其他分支的新增授权。
- 每批修改范围以用户当前任务为准，不主动扩大；保留 raw 层现有约束，clean/analysis 不得修改 raw collector 行为。

## 总原则

1. 每次只执行用户给出的当前批次任务，不主动扩大修改范围；批次完成后的停止要求见文末。
2. 默认不真实访问招聘网站；只有满足下文 `Explicit Production Execution Exception`
   的明确 production execution 才可例外。
3. 不修改业务过滤逻辑，除非当前批次明确要求。
4. 不修改 README。
5. 不修改数据库写入逻辑。
6. 不修改 diff 逻辑。
7. 不修改通知逻辑。
8. 不提交 commit，除非用户明确要求。
9. 如果发现当前代码结构和任务假设不一致，先说明差异，再给出最小修改方案，不强行大改。

## 统一视图文档影响检查

每批涉及代码、配置、调度、测试或业务契约的变更，在交付前必须检查是否影响以下统一视图：

- `docs/workbook.md`：正式/手动执行入口、调用关系、模块职责、数据输入输出、业务契约、故障保护及运行边界。
- `docs/test_strategy.md`：业务不变量、测试映射、证据等级、已知缺口及验收状态。

处理原则：

1. 如果变更影响上述事实，应在本批已授权修改范围内同步更新对应文档。
2. 如果文档修改不在本批授权范围内，不得擅自扩大范围；记录具体文档影响，标记 `DOC_UPDATE_PENDING`，等待人工批准。
3. 如果确定不影响，交付报告记录 `DOC_IMPACT=NONE` 及简要理由。
4. 文档不能把“代码存在”“测试通过”“生产已部署”“生产运行成功”混为一谈。
5. 历史审计记录必须保留；新增证据应写入新的状态记录，不改写当时事实。
6. 不引入另一份平行架构权威文档，不自动修改冻结业务契约。
7. 文档同步检查不授予真实 Crawl、生产执行、提交、推送、合并或部署权限。

## Explicit Production Execution Exception

开发、调试、单元测试、回归测试、forensic audit 和探索性调查等场景，
默认禁止真实访问招聘网站，并优先使用 mock、fixture、frozen artifacts 和
offline evidence。

真实招聘网站访问仅在以下条件全部满足时允许：

1. 用户在当前任务中明确要求真实 production execution，例如 production
   acceptance、real full E2E、launchd/scheduler production validation 或
   scheduled production run。
2. 必须通过仓库已有正式 production entrypoint 执行，例如
   `tools/run_daily_with_health.py` 或正式 scheduler adapter。
3. 禁止为调试临时编写或执行 ad-hoc curl、ad-hoc HTTP requests、ad-hoc
   Playwright/browser probes 或 temporary scraper。
4. 禁止为了让 Gate PASS 而放宽 validator、绕过 failed source、修改
   completeness semantics，或修改 SourceHealth / Daily Health interpretation。
5. 每个 production Gate 最多一次顶层 invocation；平台级 retry 只能由已有
   Runner contract 自己执行。
6. production execution 失败时，必须保留 artifact、log 和 error evidence，
   随即停止，且不得人工重复 Crawl。
7. production execution 必须继续遵守项目已有的 source scope、rate limiting、
   collector contracts 和 completeness contracts。

### Approved Unattended Production Scheduler

用户明确授权启用特定的 permanent production scheduler 后，该 scheduler 可以：

- 按已经批准的固定 schedule 运行；
- 仅从正式 production root、使用正式 production Python，通过正式 production
  entrypoint 执行正常 Crawl → Clean → Analysis → Health 链路。

该授权只适用于用户已经批准的 scheduler。开发、测试、调试、审计和探索场景仍
禁止真实访问招聘网站；也不得以此授权进行 ad-hoc curl / HTTP、临时 Playwright
probe、临时 scraper、绕过正式 production wrapper、OLD_ROOT execution、自行增加
scheduler frequency、自行创建额外 scheduler，或因单次 source partial 人工补跑完整
production。scheduler failure 或 DEGRADED 不自动授权人工第二次 full crawl；需要
recovery 时仍须遵守既有 recovery contract 和 policy。

## 仓库实现约束

- 开工先检查当前分支、工作区状态及相对主分支的 diff。
- 平台逻辑只放独立 adapter，不改 `main.py` 或其他 adapter。
- 简单参数放入配置；新平台默认关闭，除非任务明确启用。
- raw 层不复制岗位池规则。
- 平台失败须返回 manifest，不得击穿 pipeline。
- 全失败不得用空结果覆盖旧产物。
- 浏览器方案须先证明 HTTP 不可行，并确保资源释放。
- 测试覆盖正常、去重、结构变化，并跑全量回归。
- 生成数据、日志和临时文件不得进入功能提交。

## 每个批次完成后的必需输出

每个批次结束时必须输出：

1. 本批次修改了哪些文件。
2. 每个文件为什么要改。
3. 运行过哪些命令。
4. 命令结果是否通过。
5. 工作区状态、diff 统计及关键文件 diff，命令与展示要求见下文「Diff 输出要求」。
6. 是否存在风险或未解决问题。
7. 明确写出：`本批次已完成，已停止，等待人工确认后再继续下一批次。`
8. 增加一行 `DOC_IMPACT: UPDATED / PENDING / NONE`；`UPDATED` 必须提供文档路径，`PENDING` 必须指出待更新内容，`NONE` 必须说明原因。

## 每个批次的固定验收命令

能运行则运行：

```bash
python -m compileall src tests
pytest -q
```

如果当前仓库测试太多或已有旧测试失败，则至少运行：

```bash
python -m compileall src tests
pytest tests -q
```

如果 `tests` 还不存在，必须说明原因。

## Diff 输出要求

必须输出：

```bash
git status --short
git diff --stat
```

并针对本批次修改的关键文件输出：

```bash
git diff -- <file_path>
```

如果 diff 很长，可以只输出关键片段，但必须说明可用什么命令查看完整 diff。

## 停止规则

- 当前批次完成后必须停止，等待用户确认；不允许一次性完成后续批次。
- 不说“我接下来会继续做”。
- 必须停在当前批次验收结果。
