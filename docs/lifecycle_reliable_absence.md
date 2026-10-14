# 不可靠缺失后的恢复观测

本批基于 Worker 提交 `48bea53acd06fb1af8389ce024c702f978440d6e`，
独立分支 `codex/lifecycle-reliable-absence`，不合并 taxonomy、不推送、不运行真实 Crawl。

## 批准的规则与最小实现

`Observation.missing` 会因可靠或不可靠缺失而设为 true，旧代码仅检查它就生成 REAPPEARED。
因此来源失败造成的 provisional MISSING，也能在来源恢复时变成 confirmed REAPPEARED。

改为同时要求 `missing_streak > 0`。这个既有计数只由来源可靠且范围兼容的缺失增加；
不增加 schema、状态字段或 Event enum，不做平台特判。
不能仅检查事件是否 provisional，因为首次**可靠**缺失的 MISSING 同样是 provisional。

- 只有不可靠缺失：保留 MISSING 审计，再次观测不生成 REAPPEARED。
- 曾有可靠缺失：保持原有 REAPPEARED 及当前来源可靠性判定，包括已 REMOVED 后的返回。
- 再次观测仍执行原状态刷新，清除 missing/removed/streak。
- 可靠正文真正变化仍生成 UPDATED；正文不可靠时不推进 reliable_sha。

## 文件与测试

| 文件 | 原因 |
|---|---|
| `src/analysis/lifecycle.py` | 一处条件变更及解释注释 |
| `tests/test_lifecycle_reliable_absence.py` | 19 项确定性对照与贯通验证 |
| 本文 | 记录批准的语义、验收及历史数据边界 |

新增测试原代码下 11 failed、8 passed，修复后 19 passed。
原 Worker 合并门禁的合成输入已固化为测试：同一 RawJobPosting、manifest、缺失原因和 SHA256；
无论再次观测时来源可靠与否，原错误的 REAPPEARED 都不再产生，MISSING 审计保持原样。

warmup 测试仅在 pytest 临时目录中生成合成的三日数据，比较全区间计算、单日 warmup、
以及读取合成事件账本的 Trend-only 结果，并校验输入和 MISSING 审计未被改写。
未执行生产历史重算。已落盘的历史事件不追溯修改；Trend-only 对既有事件账本的读取契约不变。

验收命令（使用项目 venv Python）：

```bash
python -m compileall src tests
python -m pytest tests/test_lifecycle_reliable_absence.py -q
python -m pytest tests/test_lifecycle_reliable_absence.py tests/test_market_pipeline.py tests/test_trend_v1.py tests/test_sourcehealth_reliability_v2.py tests/test_sourcehealth_v2_backfill.py tests/test_invocation.py tests/test_meituan_worker.py tests/test_meituan_worker_pipeline.py -q
python -m pytest -q
git status --short
git diff --stat
git diff --check
git diff -- src/analysis/lifecycle.py
```

冻结分析测试输入仅从原 Worker worktree 复制并逐文件校验哈希，不修改冻结期望，也不纳入提交。
SourceHealth、Trend、Classification、城市规则、invocation 和 Worker 实现均未修改。
提交后完整 diff 可用 `git show HEAD -- <file_path>` 查看。

## 最终结果

2026-10-14：定点 19 passed；相关 187 passed；全量 824 passed；compileall、diff 检查通过。
原 checkout 的 632 个受保护文件 SHA256、3 个用户测试修改及未跟踪文件状态保持一致。
Worker 分支仍在 `48bea53` 且工作区干净；taxonomy 未移动。
测试输出保留在 `/tmp/lifecycle-absence-before.txt`、`/tmp/lifecycle-absence-related.txt`、
`/tmp/lifecycle-absence-full.txt`，不纳入提交。
