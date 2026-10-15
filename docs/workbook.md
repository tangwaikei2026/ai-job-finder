# 工程工作手册

## 生产主链路与业务契约

本节记录当前代码与既有契约，不新增授权，也不表示所有入口已经具有相同保护。
执行范围、真实抓取、自动调度、停止和提交权限仍按 [AGENTS.md](../AGENTS.md)；测试证据状态见 [测试策略](test_strategy.md#6-业务不变量与证据状态)。

### 正式链路与唯一职责

```text
launchd adapter → run_daily_with_health → run_daily
  → src.main / collectors → Raw + manifest
  → clean.cli → Clean + report
  → analysis.pipeline → Classification / Events / Trends / Audit
  → Runner 校验与发布 → Daily Health → Operations / Notifications
```

| 节点与代码证据 | 职责与边界 |
|---|---|
| `ops/launchd/run_daily_launchd.py::build_command/main` | 提供运行时本地日期、项目 venv Python 和环境，调用正式 wrapper；本节不证明本机 scheduler 已加载或某次任务成功。 |
| `tools/run_daily_with_health.py::run_daily_with_health/_run_locked` | 持有项目锁，协调 Runner、Health、Operations；不自行重新分类岗位。 |
| `tools/run_daily.py::run_daily/_run_daily/_publish` | 调度 Crawl → Clean → Analysis；为新尝试建立 invocation 与 staging，对 error 平台按已有 contract 重试，校验后发布。失败尝试保留证据；最新尝试状态与上次成功发布产物是不同概念。逐文件替换有 OSError 回滚，不等于跨文件事务或已验证断电恢复。 |
| `src/main.py`、`src/collectors/` | adapter 获取、解析和执行既有来源治理与城市范围；输出 Raw 和 manifest，不复制岗位池分类规则。平台异常转为 manifest。 |
| `src/clean/cli.py`、`src/clean/jobs.py` | 添加规范化字段；正式 invocation 校验要求原始身份、内容和时间保持不变。 |
| `src/analysis/pipeline.py` | 组织历史预热、可靠性判定、分类、生命周期和聚合；不是另一套独立业务筛选规则。 |
| `src/analysis/source_health.py::SourceHealth` | 判定平台／公司／记录层面的存在和正文可靠性。 |
| `src/analysis/classification.py::classify_record` | 生成 Market / Fit / Skills 分类事实及 fresh、carried_forward、review_required 状态；同日 `analysis/classification/<date>.jsonl` 是正式候选资格的权威输入。 |
| `src/analysis/lifecycle.py`、`trends.py`、`audit_bundle.py` | 分别负责身份生命周期、趋势聚合和审计证据；分类变化不等于岗位新出现或消失。 |
| `src/analysis/daily_health.py` | 解释已完成运行、来源完整性、已知限制与是否需要行动；运营容忍不把 partial 改写为 complete。 |
| `src/operations/daily_ops.py`、`notifications.py` | 管理事件、有限 clean/analysis 恢复和通知；不自动重抓历史 Crawl。恢复输入衔接存在下述待验证缺口。 |
| `src/analysis/ai_eval_jobs.py::run_analysis`、`canonical_report.py` | 独立候选报告消费者，不是 Daily Runner 自动节点；正式模式只消费 Canonical 资格，探索模式使用独立名称。 |

### 既有业务不变量

- **Canonical 权威**：正式报告不重新分类资格；不把探索结果变成正式事实。现有报告的行级检查不等于整批发布证明，见下述缺口。
- **身份**：使用 `(platform, job_id)`；`lifecycle.index_jobs` 合并完全相同记录，冲突身份报错。正文相同仅折叠展示，不减少真实岗位数和技能统计分母。
- **深圳候选**：`candidate_city.match_shenzhen_candidate` 使用原始 title/location，任一正向匹配可入候选，明确否定否决；地点冲突保留提示。仅从 P1/P2 选择，不能据此声称确认有岗。正文不作为城市来源，候选判定不改写 `city_norm` 或职业 Fit；raw 城市范围与该候选规则各有职责。
- **SourceHealth**：存在可靠性与正文可靠性分开；列表不可靠时不推进确认删除。详情失败按已有条件保留可靠子集、继承历史分类或标记未知；有限详情容忍不改变 manifest completeness。详见 `source_health.py`、`classification.py`、`lifecycle.py`。
- **invocation / 日期**：`src/invocation.py` 校验身份、摘要、配置及时间顺序。窗口从带时区的开始时间起，到开始日后第二日零点之前；不是固定 48 小时。正式恢复沿用原 invocation，不为 legacy 推断新证明；现有 legacy 兼容路径不因本文自动取消或升级。
- **失败保护**：正式 Runner 在 staging 校验成功后才发布 Raw/Clean/Analysis；失败不应以空结果覆盖旧有效产物。单个文件原子写入、发布回滚与整个观察批次可信是不同保证，不能混为一谈。

### 2026-10-13 审计记录：证据与未解决项

审计基线：本地 `taxonomy`，提交 `dcefcb8`，与本地 `master`、`origin/master`、`origin/taxonomy` 同提交；未 fetch，不代表远端实时状态。开工已跟踪文件无 diff，另有 44 个未跟踪 raw/clean 产物，本批不处理。

**GitHub 自动任务事实（用户确认）**：用户在 2026-10-13 本批任务中明确提供：
“我已通过 GitHub 确认 `daily-scrape.yml` 存在近期自动触发记录，最近的采集步骤失败。”
这取代此前审计中“未确认实际运行”的表述。证据来源是本次用户确认，不能写成本代理独立检查 GitHub 日志的结果；本次未提供 run URL、run ID、具体触发时刻或错误日志，失败根因及采集结果未核验。

**仓库静态证据**：`.github/workflows/daily-scrape.yml` 声明 UTC 01:00、09:00（北京时间 09:00、17:00）定时触发，直接运行 `python -m src.main`，只上传 `data/raw/`。它与上面的完整生产链路不同，`tests/test_workflow_contract.py` 仍维护 raw-only 契约。实际触发不等于完整链路成功，也不构成本代理启停、修复、补跑或新增自动任务的授权；本批不改变该 workflow。

| 待解决项 | 静态证据与验证边界 |
|---|---|
| 多日期 replay 门禁 | `pipeline.replay` 的省略 invocation 拒绝条件限于 `start == end`，历史证明检查限于 `day < start`；请求区间内现代产物的多日路径需补测试。默认输出为正式 analysis 目录；未实际执行覆盖复现。 |
| 恢复输入位置 | `run_daily` 使用 `analysis/invocations/<id>/data`，`DailyOperations._validate_recovery_inputs` 读取正式 raw/clean。首次失败可能因正式文件缺失而被拒绝，有旧文件时可能预检了另一份输入。尚未完成真实离线 Runner 与 Ops 集成验证。 |
| 报告整批证明 | `analyze_canonical_candidates` 校验日期、身份、状态和 fresh 正文摘要，未调用 `validate_analysis`。截断或同日混合输入风险尚未通过新增用例验证；合法空候选及 legacy 兼容必须与损坏输入区分。 |
| GitHub 定时 raw 路径 | 已有用户确认的近期自动触发及最近采集失败；本批未调查根因，也未决定其启停或迁移。 |

以上是缺口与待验证事项，不是已发生数据污染的结论。完整代码证据可按所列符号在审计基线中定位；测试存在、测试通过和生产成功分别记录。

### 本批变更边界与暂不实施的建议

本批仅整理 `AGENTS.md`、本文和 `test_strategy.md`。生产访问例外和 unattended scheduler 条款原文保留；不改变业务语义、修改范围、停止、提交或调度权限。

上一轮提议把“禁止修改 main/数据库/通知”等规则改成按任务类别适用，以及为纯文档／只读审计普遍豁免固定回归命令，都可能改变约束适用范围，本批不实施。`AGENTS.md` 原限制和“能运行则运行”的固定验收保留；本批按用户指定的文档一致性、范围与 diff 检查验收，未运行编译或 pytest，不记为测试通过。

第二批仅拟在现有 `test_invocation.py`、`test_daily_orchestration.py`、`test_canonical_candidate_report.py` 补离线边界测试，需另行确认；不得因本文自动启动。若测试暴露缺陷，记录失败，不顺便修改生产代码或弱化断言。

### 2026-10-14 增量状态与执行入口登记

代码基线：`ec33299422992028afca6acb6d88d1aef4527333`（taxonomy）。本批 `git ls-remote origin refs/heads/taxonomy` 与本地 HEAD 一致；开工工作区干净，`master...HEAD` 与 `dcefcb8..HEAD` 的统计已核对。旧统一视图在 `b77e0fc` 落盘；以其记载的 `dcefcb8` 为代码基线核查增量，不读取新增历史 Raw/Clean 正文。上述 2026-10-13 记录保留，以下状态取代其“尚无新增测试”的当前解释，不改变历史事实。

登记范围为 `tools/`、`ops/launchd/`、`.github/workflows/`、`src/` 的 `main`、`__main__`、参数解析与调用点静态检索。下表代码路径均相对仓库根；证据为所列文件的 `main` 或明确符号及配置。所有行均为**静态确认**，本批入口执行 **NOT_RUN**；实际部署与生产成功均 **UNKNOWN**，唯一例外是 GitHub 的历史用户确认（近期触发、最近采集失败，仍无独立日志核验）。仓库 plist 存在不证明 launchd 已加载；未读取本机安装状态，不启停调度。

| 分类／触发者 | 正式入口与调用节点（代码证据） | 输入 → 产物／副作用 | 适用保护与验证边界 |
|---|---|---|---|
| 生产定时／launchd Daily | `ops/launchd/com.waikei.ai-job-finder.daily.plist` → `run_daily_launchd.py::main/build_command` → wrapper | 主机本地 10:00；固定 root/venv、运行日、邮件环境 → 日志轮转、`caffeinate -i`、完整 Daily | 获准 scheduler 才可执行；wrapper 锁与 invocation 门禁；部署／成功 UNKNOWN |
| 生产定时／launchd Wake Guard | `ops/launchd/com.waikei.ai-job-finder.wake-guard.plist` → `run_wake_guard.py::main/build_command` | 本地 09:55 → `caffeinate -i -t 600` 与共享 launchd 日志 | 仅有限防 idle sleep；不调用 Daily、不抓取，不证明机器会被唤醒；部署／成功 UNKNOWN |
| 生产定时或 GitHub 手动 dispatch | `.github/workflows/daily-scrape.yml` → `python -m src.main` | UTC 01:00/09:00、config → Raw/manifest、上传 `data/raw/` | raw-only，不具有 wrapper/全链路保证；历史用户确认失败，根因 UNKNOWN |
| 独立手动／操作者 | `tools/run_daily_with_health.py::run_daily_with_health/_run_locked` → Runner → Health → Ops → Notifications | config/运行日、既有 Ops 状态 → runs、health、ops DB/latest、通知队列及可能外发 | 项目锁；有限下游恢复、不重抓；真实执行需明确授权，本批禁用 |
| 独立手动／操作者或 wrapper | `tools/run_daily.py::run_daily/_run_daily/_publish` → main → clean CLI → pipeline | config、日期、resume → invocation staging、Worker sidecar、正式 Raw/Clean/Analysis、run 状态 | invocation/摘要/日期、失败保留、发布校验回滚；直接调用不等于 wrapper 锁／Health／通知 |
| 独立手动／操作者或 Runner | `src.main::main/collect_all` → collector registry | config、platform、可选 invocation/merge → Raw/manifest；真实网络 | 全失败旧产物保护、不完整 merge 拒绝；直接入口可无 invocation，不得推定 staging 保护；本批禁用 |
| 独立手动／操作者或 Runner | `src.clean.cli::main` 的 `clean-jobs` → `run_clean_jobs` | Raw、日期／可选 invocation → Clean/report | 正式 invocation 不改原始字段；独立输出默认 data/clean，不能视为 Runner 发布事务 |
| 独立手动／操作者或 Runner | `src.analysis.pipeline::main/replay` 的 run/replay → SourceHealth、Classification、Lifecycle、Trends、Audit | Clean/manifest、历史预热、版本 → classification/events/trends/audit；默认 data/analysis | 来源重叠拒绝、单日 invocation 门禁；trend-only 只读事件账本写趋势；多日缺口见下表，本批不执行历史 Replay |
| 独立手动／操作者 | `src.analysis.ai_eval_jobs::main/run_analysis` → `canonical_report.analyze_canonical_candidates` | 同日 Clean/Canonical/config → analysis JSON、候选／排除 JSONL 与 Markdown | Canonical 权威、探索独立命名；不是 Daily 自动节点；整批证明缺口未关闭 |
| 独立手动／操作者 | `tools/run_weekly_report.py::run_weekly_report` → `compare_trends` → `generate_market_report.py` | 两端点 snapshot → comparison JSON、周报 Markdown | 日期顺序与端点校验；未发现每周 scheduler 调用，名称不代表自动周任务 |
| 独立手动／操作者或周报 | `tools/generate_market_report.py::main` → render_snapshot/render_comparison | Trend snapshot/comparison → reports Markdown | artifact_type 检查，保留不可比标记；不重新分类、不采集 |
| 历史维护／操作者 | `tools/backfill_history.py::run_backfill` → staged replay、Health、Ops、报告 | 保存的 raw/manifest/clean → 缺失派生产物、历史 Ops DB 行、backfill audit | 不调用 collector；保留已有产物；dry-run 与正式写入区分，本批均不执行 |
| 历史维护／操作者 | `tools/sourcehealth_v2_backfill.py::run_v2_backfill/coverage_audit` → staged replay、Trend/report | 冻结历史输入 → V2 派生产物替换、审计；coverage-only 输出检查结果 | 校验后替换；不写 Raw/Clean/Health/Ops；本批不执行 |
| 历史维护／操作者 | `src.operations.daily_ops::main/rebuild_daily_operations` | canonical run/health/manifest → Ops DB/latest | 重建运营解释，不能当作 Crawl 或通知发送入口；本批不执行 |
| 诊断／操作者 | `tools/opsctl.py::main` → status/history/incidents/incident/recover/notify handlers | Ops DB／事件／邮件配置 → 状态或交接文本；notify 可入队、更新 delivery、外发 | recover 仅支持 dry-run 检视，不执行恢复；notify dry-run 仅渲染，正常模式本批禁止 |
| 诊断／操作者或 wrapper | `src.analysis.daily_health::main/generate_daily_health` | run/manifest/registry → health JSON | 已完成观测解释；不把 partial 升级 complete、不采集 |
| 诊断／操作者 | `src.clean.cli::main` 的 audit → `src.clean.audit.run_audit` | Raw → data/audit JSON/Markdown | 本地审计，有输出副作用，不是定时节点 |
| 诊断／操作者 | `src.audit.enum_audit::main/run_enum_audit`；`src.audit.missing_evidence::main/run_missing_evidence` | Clean、规范配置 → enum health/full JSON、例外 CSV；缺失证据 CSV/report | 仅审计／复核产物，不改 Clean、不采集 |
| 诊断／操作者 | `src.analysis.ai_eval_regression::main`；`tools/market_oracle_baseline.py::main/save_result` | frozen regression/Oracle → stdout；新目录 baseline JSON/CSV/Markdown | 冻结输入、baseline 既有文件冲突保护；不是正式资格发布或自动任务 |
| 历史维护／操作者（历史 freeze 工具） | `tools/market_v1_regression.py::main`；`tools/trend_v1_validation.py::main` | Oracle／历史证据 → 离线 replay、验证产物；freeze 标志还可改 versions 配置 | 有真实写入与测试子进程，非只读诊断；旧 freeze 授权不能据名称推定，本批不执行 |
| 诊断／操作者（网络工具） | `tools/tencent_detail_diagnostic.py::main/diagnose_detail` → Tencent collector | config/post-id → 真实详情请求、stdout 脱敏证据 | “read-only”不代表离线；不属于正式 production wrapper，本批及默认审计禁止执行 |

简洁调用关系：Daily plist → launchd adapter（运行期间防睡眠）→ wrapper → Runner → main/collectors → clean → pipeline → 校验发布 → Health → Ops/Notifications。Wake Guard 是平行的限时电源断言；GitHub 直接走 main → Raw；周报走 snapshots → comparison → Markdown；候选报告走 Clean + Canonical → 报告；两种 backfill 从保存输入走 staged 派生。内部 `_publish`、`DailyOperations.attempt_recovery` 等只作为下游；`meituan_worker.py` 的 exec/IPC 子进程是 collector 内部实现，不登记为独立 scheduler；测试 fixture、测试辅助 main 不作为业务入口。静态检索未发现其他业务 scheduler；实际仓库外任务 UNKNOWN。

增量专项复用：[Worker 隔离边界](meituan_worker_boundary.md)、[Lifecycle reliable absence](lifecycle_reliable_absence.md)、[美团失败诊断](meituan_failure_diagnostics.md)。诊断文档的 BLOCKED_BY_DECISION 是该批历史状态；当前 `48bea53` 已实现 Worker，不能沿用“未实现”作为当前事实，也不能推断已部署。Runner 的 `command_environment` 传 invocation 专属上下文，`retry_exhausted` 复用绝对预算，`verify_worker_cleanup` 在首次与 retry 后门禁；sidecar 位于 staging data 之外，不随正式发布复制。注册表仅美团换 Worker，其他 adapter 不变。中断仍为 error/complete=false，可靠性不自动提升。

Lifecycle 在 `c83a03b` 将 REAPPEARED 条件改为 `old.missing and old.missing_streak > 0`，只认可靠且范围兼容的缺失；`5ad3f33` 补 Worker → Lifecycle/Trend 合成贯通。当前文档引用此已落地变更，不另行设计、不追改历史事件；trend-only 仍消费原事件账本。专项文档历史 805/824 passed 属于对应分支当时报告，不能替代当前 HEAD 回归。

| 2026-10-13 待办 | 当前增量状态与证据 |
|---|---|
| 多日期 replay 门禁 | 新增 `tests/test_invocation.py::test_multiday_replay_rejects_unproven_inputs_and_preserves_affected_publications`（两日 × 三种损坏）；pipeline 本次无修改，单日／warmup 门禁仍限原范围。不得因测试存在关闭。当前执行结果见 test_strategy。 |
| 恢复输入位置 | 新增 `tests/test_daily_orchestration.py::test_offline_staged_failure_recovers_once_without_recrawl`（clean/analysis × 有无旧发布），记录 Ops 实际 precheck 路径；DailyOperations 本次无修改，旧正式输入预检缺口仍保留。成功恢复控制组也不能证明预检读 staging。 |
| 报告整批证明 | 新增 `tests/test_canonical_candidate_report.py` 五种损坏拒绝／旧输出保留，以及正常现代报告、合法零候选控制；报告实现本次无修改，仍未调用整批 validate_analysis。合法空分类不得等同被清空的非零发布。 |
| GitHub 定时 raw 路径 | workflow 无增量，保留用户确认及 UNKNOWN 根因；未修复、启停、迁移或补跑。 |

本批仅修改 workbook 的入口／增量登记及 test_strategy 的测试映射／实际证据。未触发生产入口、通知、调度、历史 backfill 或招聘网站；发现的代码缺口仅记录，非白名单实施停止。当前结果与验收见下方测试策略新记录；不启动历史第二批计划。

### 2026-10-15 集成候选验收状态

集成分支为 `integration/unified-view-reliability`，从已核实的 `origin/taxonomy` `ec33299422992028afca6acb6d88d1aef4527333` 创建；五组变更整合后的代码 HEAD 为 `2c1dc1ae2ed83c39bff7d1e24347c06347ec2802`。本地 taxonomy 另有数据提交 `561cc56`，未纳入集成。2026-10-13/14 的审计、失败证据及入口登记保留；以下是本次实际离线验证后的当前状态。

| 已验收修复 | 集成提交（来源提交） | 当前状态与最小影响 |
|---|---|---|
| Canonical 整批证明 | `4c4c275`（`ca03675`） | 原 5 项拒绝／输出保留测试 **5 passed**；`canonical_report.analyze_canonical_candidates` 在正式报告写入前复用 `validate_analysis`，保留合法零候选、legacy 与探索隔离行为。 |
| 多日期 Replay 输入证明 | `71257b9`（`a7aa646`） | 原 6 项 **6 passed**；`pipeline.replay` 对现代目标重算使用 `validate_clean`，预热／trend-only 使用 `validate_analysis`，受影响产物字节保持不变。 |
| Daily Operations 恢复来源 | `b02c202`（`ee6129b`） | 原无旧发布 2 项 **2 passed**，完整四组 **4 passed**；`DailyOperations._validate_recovery_inputs` 校验同一 Invocation staging 的 Raw／Clean，沿用一次受控恢复，不重新 Crawl。 |

文档提交 `3a01b43` 来自干净提交 `2f40f09`（两份文档与 `08c1dc5` 内容一致），治理提交 `2c1dc1a` 来自 `b6bdab8`；均独立 cherry-pick，不纳入数据父提交或其他分支历史。三个修复文件保持已验收内容，未增加业务逻辑。

当前原 13 项失败全部通过；相关 Invocation／SourceHealth／Market／Lifecycle／Trend／Ops／Report 回归 **435 passed**，全量 **843 passed / 0 failed / 0 skipped**，compileall、diff 范围及 Markdown 引用检查通过。冻结输入仅在隔离环境按 SHA-256 校验复制，未进入提交。详细命令、测试映射和证据边界见 [本次集成验证](test_strategy.md#10-2026-10-15-集成候选离线验收)。本次仅建立本地候选，不代表已部署；真实 Crawl、生产 Replay／Backfill、恢复运行、通知及调度验证均 **NOT_RUN**，实际部署与生产运行成功仍 **UNKNOWN**。未 push、merge 或部署。

### 2026-10-15 Modern → Legacy 降级修复离线验收

基于 PR #1 HEAD `118c348921ca5053e4a5aa142010ff22544eb128` 的新隔离 worktree；原 PR 分支保持不变。先用完整现代发布 fixture 删除 Raw manifest 的 invocation 与 Analysis proof，保留成功 Run 的 invocation：Canonical 截断分类后错误接受 1/2 候选并覆盖四个旧报告；多日 Replay 在首日／次日损坏时均未拒绝，并生成 comparison。三个新增风险用例在修复前均失败；这只是临时离线复现，不代表生产数据已发生污染。

根因为现代观察识别漏掉 Run invocation。`src/invocation.py::has_invocation_evidence` 复用 Daily Health 已有的三标记识别规则：Manifest invocation、Analysis proof 或 Run invocation 任一存在即进入现代证明门禁；标记本身不建立可信性。Canonical 与 Replay 的单日、目标重算、预热及 trend-only 使用该识别，继续调用原 `validate_clean`／`validate_analysis`。未改变分类、SourceHealth、时间窗口、合法 Legacy 规则或发布／数据库／通知逻辑；无 invocation 的真实 Legacy Run 保持兼容，不要求补现代证明。

修复后新增 9 项（3 项风险、3 项其他 Replay 路径、3 项 Legacy 对照）通过，原 13 项失败对应回归全部通过；三文件专项 **84 passed**，全量 **852 passed / 0 failed / 0 skipped**。不可信输入拒绝后旧报告、受影响分析产物与源输入字节保持不变，且不新增 comparison。详细命令和证据见 [本次测试记录](test_strategy.md#11-2026-10-15-modern--legacy-降级风险验证)。冻结测试输入仍以原 SHA-256 清单校验，仅复制到隔离 worktree，未进入 diff。未 commit、push、merge、生产执行或部署；生产验证仍 **NOT_RUN**。本次状态不改写此前历史验收结论。`DOC_IMPACT: UPDATED`。

#### 集成到 PR #1 的状态更新

上述隔离验收补丁已作为独立提交 `fb481f3a66df142419b0b3ebe00685a656c9ff75` 创建，并以普通 cherry-pick 应用到原集成分支，当前 PR 候选 HEAD 为 `dc83685084064b3d1811e252cccad9d53c13708c`。原六个提交顺序保留。集成 worktree 的原 13 项回归节点为 **18 passed**（含参数化展开及既有成功控制），新增单日／预热／trend-only 与 Legacy 对照 **6 passed**，全量再次为 **852 passed / 0 failed / 0 skipped**；compileall 和冻结输入 SHA-256 校验通过。本批按授权准备普通推送并同步 PR 描述；未合并、部署或执行生产链路。

## 场景：接入一个未知招聘平台

做法：

1. 先分类平台：公开 API、公司 API、ATS、普通网页、浏览器依赖、登录或高反爬。
2. 分别验证列表页、列表 API、详情页和详情结构。
3. 记录字段来源、缺失字段、限流表现和合规风险。
4. 在确认采集边界后再决定 adapter 的最小实现范围。

反例：

- 看到 JSON API 就直接认为可以长期用 httpx 调用。
- 未验证业务码，只根据 HTTP 200 判断成功。
- 在调研阶段直接写完整 adapter。

验收标准：

- 有明确的平台分类和选择依据。
- 能说明每个 RawJobPosting 字段的来源。
- 能说明为什么需要或不需要浏览器。
- 风险和未验证项被显式记录。

## 场景：私有 API 只能在浏览器中工作

做法：

1. 开发、调研先使用既有脱敏样本和离线证据分析会话依赖。
2. 实际页面及请求监听仅描述 adapter 的获取机制；真实访问须满足 AGENTS.md 的 production execution 例外，通过正式入口，不能据本节运行临时浏览器 probe。
3. 将浏览器控制限制在平台 adapter 内。
4. 将响应解析、字段映射和去重拆成不依赖浏览器的函数。
5. 延迟导入 Playwright，并在 `finally` 中关闭 page、context 和 browser。

反例：

- 把一次会话中的 token、`skId`、Cookie 写死到代码或配置。
- 为一个平台修改全局 portal helper，影响其他 adapter。
- 让单元测试连接真实网站。

验收标准：

- 关闭该平台时不会初始化浏览器。
- 浏览器异常只影响该平台。
- 解析逻辑可以用固定 payload 单测。
- 所有浏览器资源均可被释放。

## 场景：使用多关键词缩小采集范围

做法：

1. 关键词列表写入配置。
2. 明确 `max_pages` 是每关键词还是全局限制。
3. 每个关键词独立处理失败和页数。
4. 所有关键词共享一个按平台 job_id 建立的去重集合。
5. manifest 同时记录原始记录数、唯一岗位数和重复数。

反例：

- 将关键词硬编码到 adapter。
- 每个关键词使用独立结果列表，最后简单拼接。
- 使用标题和公司拼接值代替平台稳定 job_id 去重。

验收标准：

- 每个配置关键词都被调用。
- 单个关键词失败不会阻止后续关键词。
- 重复岗位只保留一条并增加重复计数。
- 页数限制行为可由测试证明。

## 场景：平台只采集列表，不抓详情

做法：

1. 明确配置 `fetch_details: false`。
2. 从列表填充所有可靠字段。
3. 对列表拿不到的字段使用空值或中性提示。
4. 保留可人工访问的详情 URL。
5. 不把搜索关键词伪装成 JD 内容，避免影响下游岗位相关性判断。

反例：

- `fetch_details: false` 但代码仍在失败后尝试详情请求。
- 为满足非空要求，把关键词写入 description，导致下游误判岗位相关性。
- 把公司行业映射成 department。

验收标准：

- 运行日志中没有详情请求。
- `requirements` 等不可得字段保持安全值。
- URL 可用于人工复核。
- 输出仍严格符合 RawJobPosting。

## 场景：需要额外输出人工复核文件

做法：

1. 输出路径进入平台配置。
2. 使用与现有 RawJobPosting 相同的字典结构。
3. 使用临时文件加原子替换。
4. 至少成功解析一个页面后才允许更新。
5. 将侧文件视为附加产物，不修改主 pipeline 的既有输出。

反例：

- 在请求开始前清空旧文件。
- 完全失败时写入空数组。
- 为侧文件发明另一套字段名。

验收标准：

- 文件内容等于 `[job.to_dict() for job in jobs]`。
- 完全失败时旧文件保持不变。
- 写文件失败只影响该平台 manifest。
- README 和已有 jobs 输出格式不变。

## 场景：外部响应结构发生变化

做法：

1. 对关键容器和数组做类型校验。
2. 抛出平台专用 schema error。
3. 在 collector 顶层捕获并转换成 error/partial manifest。
4. 记录关键词、页码和精简错误原因。

反例：

- 使用多层 `.get(..., {})` 后静默得到空列表。
- 平台格式变化时返回 success 和 0 条岗位。
- 把完整浏览器日志塞进 manifest。

验收标准：

- 缺少关键字段时 `complete=false`。
- 第一页失败时状态为 error。
- 已有成功页面不会因后续失败丢失。
- manifest 能定位失败关键词和页码。

## 场景：浏览器运行环境不可靠

做法：

1. 开发前运行最小 launch preflight。
2. 分开验证 Playwright 包、浏览器二进制和系统权限。
3. 单元测试 mock 浏览器边界。
4. 真实网站环境验证仅在满足 AGENTS.md 的 production execution 例外后通过正式入口执行；旧“独立 live smoke”表述不提供额外访问权限。
5. 生产验证失败时保留产物和错误证据，并按 AGENTS.md 停止，不人工重复 Crawl。

反例：

- Playwright 能 import 就认为浏览器一定可运行。
- 在沙箱启动失败后修改业务解析逻辑。
- 用单元测试成功替代真实环境验收。

验收标准：

- 能区分依赖缺失、系统权限、网络失败和网站风控。
- 失败不会击穿 pipeline。
- 获授权的生产环境验收应有真实运行证据；未执行时标为未验证，不能为满足本条自行抓取。

## 场景：新平台分支混入其他平台代码

做法：

1. 从目标主分支创建平台专用分支。
2. 开工前检查 merge-base 和提交 ancestry。
3. 提交前查看相对主分支的 name-status 和统计。
4. 若发现其他平台提交混入，先说明差异并提出最小处理方案；本节不是移动提交或改写历史的授权。
5. 生成数据、日志和临时文件不得进入功能提交；本节不是删除既有产物或提交代码的授权，提交仍须用户明确要求。

反例：

- 在已有功能分支上继续开发新平台。
- 只看工作树干净，不看分支历史。
- 将数十万行 raw 输出与业务代码一起提交。

验收标准：

- 平台分支只包含该平台、必要配置、注册和测试。
- Review diff 不出现其他 adapter。
- 无 raw 产物和大文件。
- 每个提交可以独立解释和回滚。
