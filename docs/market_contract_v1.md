# Frozen Market Human Oracle Contract v1

version: market_contract_v1
status: FROZEN
git_commit_sha: 9155b4ce372ac606f1a64d5edfd07d1034ebaae6

本契约为Human Oracle/evaluation contract owner。production classifier taxonomy/rules/config保持原样；本文件不成为production规则实现。
文件SHA-256存于tests/fixtures/market_oracle_v1.yaml的metadata.contract.file_sha256及baseline metadata（文件不自嵌自身哈希）。

A1: FROZEN — Market = core + adjacent。
A2: FROZEN — market_relevance = core / adjacent。
A3: FROZEN — one primary role_family + 0..2 secondary_role_families；无numeric weights；analytics contract已接受。
A4: FROZEN — one primary ai_relation；只有core_ai_evaluation / ai_product_quality / ai_for_testing。

## Oracle字段与已接受证据规则


- core：Evaluation / AI Quality / AI Testing是核心或共同核心正式交付责任，不要求是唯一职业身份。
- adjacent：明确、持续、有owner和独立交付的实质次要workstream。
- NO：偶发关键词、工具使用、加分项、普通研发验证或弱关联；scope=false时其它字段按STOP归null及secondary=[]。
- role_family仅八种：qa_test、quality_engineering、evaluation_engineering、algorithm_research、development、product、operations、domain_expert。
- qa_test负责测试设计/执行/缺陷/回归/专项/验收；quality_engineering负责质量体系/平台/自动化基建/度量/效能/门禁；evaluation_engineering负责Benchmark/Eval Set/Rubric/Judge/Harness/评测Infra/能力测量/归因。
- algorithm_research为算法/模型研究训练身份；development为软件/AI应用/Agent/平台/Infra研发身份；product为产品规划策略体验交付；operations为运营治理业务运营；domain_expert以专业领域判断知识为核心价值。
- primary按E1职业身份/title、E2最终负责交付、E3招聘能力要求判断；E4近似平手按组织招聘职业身份选primary。不得按JD序号赋权。
- secondary默认[]，最多2个；不重复、不与primary重复。入选须F1独立负责产出、F2成组连续职责、F3明确职业经验、F4删除显著改变能力画像，至少满足一项。弱信号不入选。
- ai_product_quality：主要保障AI/Agent产品或系统功能、效果、稳定性、安全性、交付质量；模型评测可为重要组成。
- core_ai_evaluation：主要Evaluation work直接测量模型/Agent能力，建设基准、数据集、Judge/Harness、体系并分析归因。
- ai_for_testing：主要被测对象不是模型能力，AI作为测试质量工程技术手段。
- 同时测试AI产品和用AI测试工具，按主要被保障对象选relation，不因primary非评测而把relevance降为adjacent。

## admission_conditions为audit evidence，非人工字段

人工只决策scope、relevance、primary、secondary、relation。ACCEPT并备注无法判断F-code，仍归档语义ACCEPT。

本轮确定性验证限定在60条固定JD与明确证据绑定：校验content_sha256、原句匹配、具体family独立交付、责任动词及产物词，以及secondary结构约束。各accepted secondary至少绑定一个F1可追溯证据。未证明的旧F3/F4不伪装为通过，保留于历史，不要求人工填F-code；F-code不进入open_fields。此为审计证据检查，不是通用classifier或对语义正确性的程序证明。

## Analytics

同一active cohort按(platform,job_id)去重；by_role_family仅primary，互斥additive，sum=active_jobs。
hybrid_role_count为secondary非空岗位数，hybrid_role_share=该数/active_jobs，零分母为null。
by_role_family_any使用每岗位set(primary+secondary)，标注NON_ADDITIVE_METRIC，总和可超过active_jobs。没有职责百分比。


## A4 Evaluation Infra clarification


当主要建设、运行、保障或维护的对象是专门用于模型/Agent Evaluation的Evaluation Platform、Evaluation Infra、Eval Pipeline、Judge Infrastructure或Eval Execution System，且直接支撑评测执行、结果产出或评测研发流程，ai_relation=core_ai_evaluation。primary可以是quality_engineering、development或其它family。
AI/Agent产品本身的功能、体验、稳定性和上线质量→ai_product_quality；AI作为传统测试/质量工程方法→ai_for_testing；专用Evaluation Infra/Platform本身→core_ai_evaluation。
通用Agent Runtime/Sandbox/Harness不因名称自动变成Evaluation Infra。按主要被保障对象和明确交付判定；不要求Infra owner亲自设计模型能力指标。

## Frozen Oracle与内容绑定

tests/fixtures/market_oracle_v1.yaml是本60-case Human Oracle唯一正式owner。此前ledger及candidate文件为历史审计来源，不再用候选覆盖frozen expected。
ACCEPT绑定case_id + platform + job_id + 完整content_sha256。hash采用既有job_content_sha256对title/description/requirements规范化后计算；原始人工作答文件另存等字节快照与SHA-256。delta前12位仅展示，不能代替完整哈希校验。
同platform/job_id但content_sha256变化→review_required，旧Oracle不得carry forward；不修改production lifecycle。Frozen fixture包含完整被审核JD版本，禁止为了提高classifier分数更改Oracle。
out-of-scope STOP: expected_in_scope=false时expected_market_relevance=null、expected_role_family=null、expected_secondary_role_families=[]、expected_ai_relation=null。
N-01旧受限枚举条件标签只在audit history；本轮人工接受NO候选后按STOP冻结，不继承旧expected。
35条既有accepted不重新解释；最新delta 23 ACCEPT+2 CHANGE，其中N-04/B-03的adjacent是人工semantic change，仅对输入做mechanical normalization。admission F-code不是新人工gate。

## Baseline评分契约

60条为purposefully sampled diagnostic/regression set，非随机市场样本，不外推生产总体准确率。每case权重相同。
scope对全部60条计TP/FP/TN/FN及precision/recall/F1。
relevance/primary/secondary/relation仅在expected_in_scope=true上计分，包含scope FN，不使用负例null提高字段准确率。
primary/relevance/relation为exact；secondary exact_set_match以及成员集合micro P/R/F1。列表顺序不影响集合，缺少或多一个成员均非exact。
classifier字段缺失如实保留unavailable（projection=null），不得补造预测；字段exact计错。secondary未输出时exact=false，micro视为零个已输出成员，P分母为0显示null；F1=2TP/(2TP+FP+FN)。
FULL_ORACLE_EXACT_MATCH：正例五字段同时相等；负例仅要求predicted_in_scope=false。
详细failure codes可多选，MULTI_FIELD_WRONG按不同失败字段数>1；互斥primary_failure按scope→relevance→primary→relation→secondary，仅用于汇总。
