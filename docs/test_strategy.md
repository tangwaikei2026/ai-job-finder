# 测试策略

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

### Live smoke

目标：

- 验证浏览器二进制、系统权限、网络、反爬和实时响应结构。

要求：

- 与单元测试分开执行。
- 使用小关键词集和低页数。
- 记录运行环境、时间、结果数量和失败类型。
- live smoke 失败不能破坏已有产物。

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

## 3. 猎聘当前测试计划

### 已实现

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

### 下一批应补充

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
- 时间字段断言只验证存在和格式，不固定当前时间。

## 5. 验收命令

猎聘专项测试：

```bash
python3 -m pytest tests/test_liepin_raw_collector.py -q
```

全量测试：

```bash
python3 -m pytest -q
```

受限环境语法检查：

```bash
PYTHONPYCACHEPREFIX=/tmp/ai-job-finder-pycache \
python3 -m py_compile \
  src/raw/collectors/liepin.py \
  tests/test_liepin_raw_collector.py
```

Diff 检查：

```bash
git diff --check
git diff --name-status master
git diff --stat master
```
