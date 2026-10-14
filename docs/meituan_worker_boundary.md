# 美团 Worker 隔离：离线验收与边界

诊断基线：`fbffedd4dec11d09da247d90f0981d64f5ad20b6`。
修复分支：`codex/meituan-worker-boundary`。本批不部署、不合并、不推送、不真实采集。

## 实现与修改范围

| 文件 | 修改目的 |
|---|---|
| `config.yaml` | 仅美团增加 1800 秒预算及 10 秒退出宽限配置 |
| `src/collectors/__init__.py` | 仅美团注册为 Worker adapter，其他平台不变 |
| `src/collectors/meituan.py` | 复用原请求／映射；有限窗口提交、停止检查、增量结果与进度回传 |
| `src/collectors/meituan_worker.py` | 父进程监督、隔离启动、IPC 确认、共享预算、身份检查及退出证据 |
| `tools/run_daily.py` | 给正式 Crawl 传递 invocation 专属 Worker 上下文；Retry 前检查 deadline；检查退出证据 |
| `tests/meituan_worker_fixture.py` | 真实子进程中的模拟 HTTP 与异常 IPC，无真实网络请求 |
| `tests/test_meituan_worker.py` | 正常／异常进程、确认消息、预算、锁、隔离和生命周期断言 |
| `tests/test_meituan_worker_pipeline.py` | 真实 Worker → Raw → Clean → Analysis → staged publication 离线贯通 |
| 本文 | 固化验收方法、证据位置和保守语义 |

`src/main.py`、SourceHealth、Classification、Lifecycle、Trend、业务分类、城市规则、
其他平台 collector、Scheduler 和电源管理未修改。

## 进程与预算

- 正式注册入口启动 exec 子进程，`start_new_session=True`、`close_fds=True`，只传专用 socket。
- 信号前检查直接子进程仍未被回收、PID=PGID=SID 且不同于父进程边界；握手另核对父 PID、随机启动 token。
  未回收的直接子进程 PID 在检查与发信号之间不能被复用。不使用 `killpg`。
- Worker 只有 HTTP 与线程。Python audit hook 禁止 fork、spawn、exec、system；退出时用有超时的进程表检查确认没有后代。
  出现未知后代、身份不符或无法证明退出时报告 BLOCKED，不向不明进程补发信号。
- 父进程使用 `time.monotonic()`，从首次进入美团建立 1800 秒绝对 deadline。
  Retry 复用同一 invocation/config 摘要绑定的预算文件；不重置 deadline。
  deadline 也包含首次美团退出至 Retry 之间的有效运行时间，因此其他平台运行期间也可能耗尽。
- 预算耗尽不再发新任务确认，发送 SIGTERM；Worker 停止新详情／新 HTTP 请求。
  最多 10 秒有效运行时间后才允许对已证明身份的 Worker PID 发送 SIGKILL。
  宽限另有 30 秒墙钟安全检查；机器休眠期间不能承诺墙钟完成，唤醒后进行检查。
- 强杀后最多等待 2 秒回收；不能确认则 BLOCKED。记录实际退出时间，不把 10 秒写成实际耗时。
  原有 invocation 的真实日期窗口仍由既有 validator 检查。
- 父进程持有预算文件锁，Worker 不继承锁 fd。`budget.lock` 证据文件保留，但退出后内核锁释放。

## 数据、健康与发布契约

父进程只接受完整且校验成功的 IPC 消息；按序号确认、按 `(meituan, job_id)` 保存岗位。
最近一条相同消息重传幂等；冲突、乱序、截断或未收到的消息不能增加成功计数。
`detail_attempted` 表示父进程已经接收的详情开始事件；开始事件后是否完成请求未知时计入 unknown。
列表已发现数只覆盖已确认页面；列表未完成时不推断尚未发现的岗位数量。

保留已确认的列表岗位及成功详情原文，分别统计成功、最终失败、未尝试、取消／结果未知。
中断使用既有 `status=error, complete=false`，审计及覆盖细分仅进入开放的 `metadata.worker`。
正常完成的少量详情失败仍使用原 `partial/detail_errors` 及原容忍规则。

这是保守兼容策略：中断来源的成功内容仍保存在 Raw，但现有 SourceHealth 将整个 error 来源的
Presence/Content 判为不可靠，不能将这些正文直接计为新的可靠分类或市场变化。
没有新增业务状态，也没有将未知 ID 混入 `detail_failed_job_ids`。
如需中断来源中成功详情单独恢复业务可靠性，需要另批审批，不属于本次修复。

所有 Worker 证据位于 invocation 的 `data` staging 目录之外、相邻的 `meituan-worker/`：
预算、启动审计、接收日志及每次结果。Runner 发布规则不复制这些 sidecar。
既有不完整 Retry 不替换原 Raw 的门禁不变：Retry 新增的已确认结果保留在该次 sidecar，
首次已落盘观测保留；只有完整 Retry 按原规则替换。不会拼接多次观察伪造 COMPLETE。
Runner 在继续分析前还检查每次启动对应的退出证据，避免 Retry 拒绝发布掩盖未退出的 Worker。

## 验收与证据

均使用项目 venv Python。没有真实 Crawl、平台探测或生产历史回放；贯通测试仅处理临时目录中的合成岗位。

```bash
python -m compileall src tests
python -m pytest tests/test_sourcehealth_reliability_v2.py -q
python -m pytest tests/test_meituan_worker.py tests/test_meituan_worker_pipeline.py tests/test_meituan_diagnostics.py tests/test_platform_collectors.py tests/test_detail_error_types.py -q
python -m pytest tests/test_invocation.py tests/test_daily_orchestration.py tests/test_sourcehealth_reliability_v2.py tests/test_detail_gap_tolerance.py tests/test_market_pipeline.py tests/test_daily_health.py -q
python -m pytest -q
git status --short
git diff --stat
git diff --check
git diff -- config.yaml src/collectors/__init__.py src/collectors/meituan.py tools/run_daily.py
```

进程测试同时断言退出码、空后代列表、`os.kill(pid, 0)` 抛出 `ProcessLookupError`、预算锁可重新获取。
独立哨兵仍存活，后续平台执行；阶段贯通验证 DEGRADED、完整性非 COMPLETE、原 invocation、摘要及发布门禁。
1800 秒测试加速父进程有效时钟，另用真实短预算覆盖强杀；不是等待 1800 秒的生产试跑。

之前 7 项失败来自 worktree 缺少冻结分析输入。本批只复制既有文件并核对 SHA256，未重算历史数据，
冻结输入没有纳入提交。恢复时共核对 28 个分析输入与诊断 worktree 一致。
原 checkout 的 632 个受保护文件及原 git status 与开工快照比较；不把用户的 3 个测试修改纳入修复。

## 限制

该实现针对当前 POSIX/macOS 生产环境，不是 Windows 进程隔离实现。OS 无法回收进程、证据磁盘故障或
未知后代均保守报告 BLOCKED／失败，不声称已恢复安全。证据目录保留，不自动清理。
离线验收不能替代另行批准的生产验收；本批不修改生产 checkout 或正式数据。

## 2026-10-14 最终离线结果

- 恢复后原 7 项冻结输入测试：7 passed；定点：65 passed；相关回归：205 passed；最终全量：805 passed。
- `compileall`、`git diff --check` 通过；原 checkout 632 个受保护文件 SHA256 及 git status 完全一致。
- 最终全量包含新增的 Retry 前实时 deadline 检查和启动审计之前的 BLOCKED 结果检查。
- 当前会话机器证据：`/tmp/meituan-worker-exit-evidence.json`；测试输出：
  `/tmp/meituan-worker-focused.txt`、`/tmp/meituan-worker-related.txt`、`/tmp/meituan-worker-full.txt`。
  这些生成日志和复制的冻结数据均不纳入功能提交。
- 完整提交 diff 可用 `git show HEAD -- <file_path>` 查看；文件用途见本文首表。
