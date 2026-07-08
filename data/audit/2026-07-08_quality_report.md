# RawJobPosting 数据质量报告

- 生成时间：2026-07-08T13:40:00+08:00
- 输入文件：`data/raw/2026-07-08.json`
- 总岗位数：24963
- 计数口径：缺失字段按缺失字段值计数；重复按同一键中超过首条的额外记录数计数。
- 短描述定义：去除首尾空白后少于 50 个字符。

## 按 platform 统计

| platform | 数量 |
| --- | ---: |
| aliyun | 463 |
| baidu | 1495 |
| bytedance | 11643 |
| didi | 1026 |
| dingtalk | 103 |
| feishu | 276 |
| jd | 1335 |
| kuaishou | 1386 |
| meituan | 1642 |
| netease | 2417 |
| quark | 329 |
| tencent | 1925 |
| tongyi | 76 |
| xiaohongshu | 847 |

## 平台采集计数

| platform | raw | in_scope | details_fetched | detail_failed |
| --- | ---: | ---: | ---: | ---: |
| aliyun | 463 | 463 | 0 | 0 |
| baidu | 1495 | 1495 | 0 | 0 |
| bytedance | 11643 | 11643 | 0 | 0 |
| didi | 1026 | 1026 | 1026 | 0 |
| dingtalk | 103 | 103 | 0 | 0 |
| feishu | 276 | 276 | 0 | 0 |
| jd | 1335 | 1335 | 0 | 0 |
| kuaishou | 1386 | 1386 | 0 | 0 |
| meituan | 1642 | 1642 | 1642 | 0 |
| netease | 2417 | 2417 | 0 | 0 |
| quark | 329 | 329 | 0 | 0 |
| tencent | 1925 | 1925 | 1925 | 0 |
| tongyi | 76 | 76 | 0 | 0 |
| xiaohongshu | 847 | 847 | 0 | 0 |

## 问题汇总

| 问题 | 数量 |
| --- | ---: |
| missing_required_fields | 0 |
| missing_optional_fields | 64026 |
| description_too_short | 13 |
| description_and_requirements_empty | 0 |
| invalid_or_missing_url | 0 |
| duplicate_platform_job_id | 0 |
| suspected_duplicate_company_title_location | 443 |
| manifest_job_count_mismatch | 0 |
| manifest_incomplete_platforms | 2 |
| manifest_abnormal_stopped_by | 2 |
| unparseable_education | 21581 |
| unparseable_experience_years | 17994 |
| unparseable_scraped_at | 0 |

## missing_required_fields

总缺失字段值：0

| 缺失字段 | 数量 |
| --- | ---: |
| job_id | 0 |
| platform | 0 |
| title | 0 |
| company | 0 |
| description | 0 |
| location | 0 |
| url | 0 |

### job_id（0）

无样例。

### platform（0）

无样例。

### title（0）

无样例。

### company（0）

无样例。

### description（0）

无样例。

### location（0）

无样例。

### url（0）

无样例。


## missing_optional_fields

总缺失字段值：64026

| 缺失字段 | 数量 |
| --- | ---: |
| department | 785 |
| experience | 16703 |
| education | 21566 |
| salary | 24963 |
| requirements | 9 |

### 按平台岗位样例（每个平台 2 条，不足则全部）

| 行号 | platform | job_id | company | title | location | 缺失字段 | 详情 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 4672 | aliyun | 100005043007 | 阿里云 | 阿里云智能-解决方案架构师-杭州/上海/北京 | 北京, 杭州, 上海 | salary | requirements=-8年以上云计算经验；对阿里云/AWS/Azure有深入了解 -在AI/ML方面有扎实的实际经验（TensorFlow / PyTorch / 大模型 / MLOps） -3年以上为大型跨国客户提供技术售前或解决方案交付的经验 -普通话流利，英语具备商务水平；德语能力者优先  技术专长（至少需具备两项）： -AI/ML：模型加速、推理优化、模型迁移、RAG / 生成式AI -云原生：多云迁移、Kubernetes、基础设施即代码（IaC） -数据：大数据框架、数据湖仓、数据治理与数据管理 , education=本科, url=https://careers.aliyun.com/off-campus/position-detail?positionId=100005043007, experience=8年以上 |
| 4673 | aliyun | 100015563020 | 阿里云 | CEO办公室-AI Agent研发工程师-AI搜索-杭州/北京 | 北京, 杭州 | salary | requirements=1. 计算机科学、人工智能、软件工程或相关专业本科及以上学历，具备 5 年以上搜索、推荐、NLP、大模型应用、AI      Agent、爬虫系统或分布式系统研发经验。   2. 精通 Python、Go、Java、C++ 中至少一到两门语言，具备扎实的数据结构、算法、系统设计和工程落地能力。   3. 熟悉搜索引擎核心原理，包括倒排索引、向量索引、召回、排序、重排、相关性优化、增量索引、索引压缩和大规模集群      调优。   4. 熟悉 Elasticsearch、Lucene、Solr、OpenSearch、Milvus、Qdrant、Weaviate、Faiss 等搜索或向量检索系统，有生产      环境建设和调优经验。   5. 熟悉联网搜索或大规模数据采集链路，理解爬虫调度、网页解析、内容抽取、去重、反爬、数据质量评估、增量更新和合      规治理等问题。   6. 熟悉搜索质量评估方法，能够基于 Query 分析、点击反馈、人工标注、离线评测、在线 A/B、Badcase 分析持续优化搜索      效果。   7. 理解 RAG、Hybrid Search、Query Rewriting、Reranking、Context Compression、GraphRAG、多跳检索、Deep Search      等技术，有复杂知识问答或智能搜索系统落地经验。   8. 熟悉 AI Agent 核心机制，包括任务规划、工具调用、工作流编排、记忆管理、上下文管理、多 Agent 协作等；有      LangChain、LlamaIndex、LangGraph、AutoGen 或自研 Agent Framework 经验优先。   9. 熟悉 LLM 工程化实践，包括 Prompt Engineering、Function Calling / Tool Calling、模型路由、缓存、并发控制、推      理加速、上下文裁剪和成本优化。   10. 熟悉微服务、消息队列、任务调度、缓存、数据库、K8s、Docker 等基础设施，有高并发、高可用、低延迟系统设计和性      能调优经验。  优先考虑   1. 有联网搜索、通用网页搜索、垂类搜索、企业搜索或搜索引擎从 0 到 1 建设经验。   2. 有大规模爬虫 Infra、网页解析、离线索引构建、增量索引、搜索数据回流或搜索质量优化经验。   3. 有 Agentic Search、Deep Research、企业知识库问答、AI 助手或通用 Agent 平台核心开发经验。   4. 有复杂 RAG / GraphRAG 系统落地经验，熟悉多源异构数据的检索、重排、推理和答案生成链路。   5. 有排序模型、Reranker、Learning to Rank、语义匹配、Embedding、点击模型或搜索相关性优化经验。   6. 有 Agent RL、RLHF / RLAIF、DPO / GRPO、Reward Model、Trajectory 数据构建或模型后训练相关工程经验。   7. 在 Lucene、Elasticsearch、OpenSearch、LangChain、LlamaIndex、LangGraph、vLLM 等开源项目中有贡献，或有高质量      技术博客 / 开源项目。  我们期待的你   1. 对搜索、爬虫、索引、RAG、Agent 和大模型工程有系统性理解，不满足于简单调用框架 API。   2. 既能建设底层搜索基础设施，也能把搜索能力与 Agent / LLM 应用结合，形成真实可用的产品能力。   3. 面对搜索质量差、数据不干净、索引更新慢、幻觉严重、长链路不稳定等问题，能够快速定位、验证并推动闭环。   4. 具备结果导向和用户体验意识，能够从用户搜索、问答和任务完成效果出发，反推召回、排序、索引和 Agent 链路设计。   5. 具备良好的技术沟通和协作能力，能够推动复杂技术方案在产品和业务场景中落地。, education=本科, url=https://careers.aliyun.com/off-campus/position-detail?positionId=100015563020, experience=3年以上 |
| 18259 | baidu | 5639c595-b85c-451e-b101-6a1a920ded73 | 百度 | 合同商务（J102187） | 北京市 | experience, education, salary | requirements=-具备一定的合同相关专业知识，统招本科及以上学历，财务、经济、金融、工商管理等专业背景优先  -2年以上合同管理和商务经验，有公有云合同和运营的经验优先  -内外部沟通协调能力强，有过处理大批量公有云合同或与客户直接沟通经验者优先  -具备AI在实际业务中有深刻理解，实际使用AI经验者优先, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/5639c595-b85c-451e-b101-6a1a920ded73, experience= |
| 18260 | baidu | ca254a37-0a5d-48f7-9f4e-90600d29a373 | 百度 | 大客户销售（J102184） | 上海市 | experience, education, salary | requirements=-5年以上金融领域销售经验，银行、消金、互金经验优先 -有独立拓展客户并完成业务/产品的销售能力 -目标导向，有比较强的自驱力，学习能力，沟通能力和应变能力, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/ca254a37-0a5d-48f7-9f4e-90600d29a373, experience= |
| 6616 | bytedance | 7658146308167715125 | 字节跳动 | 产品法务（海外音乐方向）（北京/上海） | 北京 | experience, education, salary | requirements=1、法学本科及以上学历，并具备律师执业资格； 2、具备在律所或担任内部法务的扎实经验，曾为面向消费者的数字音乐、视频技术或前沿科技应用提供深度的产品合规咨询； 3、对一个或多个亚太法域（如新加坡、日本、韩国、印尼）的数字音乐版权，以及中国版权法、平台责任与避风港原则有深入且广泛的理解；熟悉与数据使用及AI音乐产品/模型相关的知识产权问题者优先； 4、具备出色的商业敏锐度与战略思维，能够将复杂的法律风险转化为可落地的合规解决方案，在降低风险的同时赋能产品业务； 5、中英双语可作为工作语言；具备较强的书面与口头沟通能力，能够有效管理内部决策层的预期，与国际团队高效跨部门协作并按时交付成果。, education=, url=https://jobs.bytedance.com/experienced/position/7658146308167715125/detail, experience= |
| 6617 | bytedance | 7644763620393371909 | 字节跳动 | iOS资深研发工程师-TikTok研发 | 北京 | experience, education, salary | requirements=1、本科及以上学历，计算机、通信等相关专业，两年以上iOS开发经验； 2、有强烈的责任心，具备良好的沟通能力和优秀的团队协作能力；有较强的技术好奇心和钻研精神、强大的自驱力，具备优秀的解决问题和逻辑思维能力； 3、有性能优化、架构、SDK等经验者优先，有业务背景但对技术有深度追求者优先。, education=, url=https://jobs.bytedance.com/experienced/position/7644763620393371909/detail, experience= |
| 5590 | didi | JR2026070700E | 滴滴 | 模型推理优化工程师 | 北京市 | experience, education, salary | requirements=掌握Python/C++编程语言， 熟悉至少一种主流推理引擎（如 TensorRT、OnnxRuntime 等），并熟练使用至少一种大模型推理部署框架（如 vLLM、SGLang、TensorRT-LLM 等）； 熟悉GPU架构（如NVIDIA Hopper、ThorX），有CUDA/OpenMP编程经验者优先，熟悉CUDA 编程工具的使用；  具备优秀的沟通协作能力和扎实的问题分析与解决能力； ​加分项： 熟悉PyTorch等深度学习训练框架； 有大模型（LLaMA、Qwen、GPT等）服务化部署经验者优先。 熟悉vLLM、TGI、LightLLM、SGLang等大模型专用推理框架者优先。 熟悉 NVIDIA Thor 芯片架构，具备在其上进行模型部署、推理加速与资源调度优化的实际经验者优先；, education=, url=https://talent.didiglobal.com/social/p/65045, experience= |
| 5591 | didi | JR20260121002 | 滴滴 | 专家工程师（架构治理） | 北京市 | experience, education, salary | requirements=任职资格 1.全日制本科及以上学历，计算机相关专业，4年及以上相关工作经验 2.有深厚的技术功底，具有策略架构&在线数据架构的人员优先，较强的业务敏感度，具有良好的逻辑思维能力 3.熟悉业务抽象和数据模型设计，具有很强的分析问题、解决问题能力，对解决具有挑战性问题充满激情 4.知识面广，思路开阔，创新能力强，对新技术持有敏感性，并能合理利用相关技术 5. AI工具驱动落地：熟练使用Cursor、Copilot等AI编程工具加速代码生成与重构 加分项 1.熟练使用主流AI coding工具进行日常开发，能够通过提示词工程优化代码生成质量，具备将AI集成到开发流程（如CI/CD、自动化重构）的实践经验。 2.了解大语言模型基本原理，有利用AI辅助架构设计、代码迁移、遗留系统分析或自动化测试用例生成的实际案例者优先 3.具有策略架构 & 在线数据架构经验者优先；了解大语言模型基本原理，并有实际AI辅助架构设计或代码迁移案例者优先, education=, url=https://talent.didiglobal.com/social/p/61242, experience= |
| 5211 | dingtalk | 100013860006 | 钉钉 | 悟空事业部-全球化AI研发工程师-DingTalk & WuKong | 杭州 | department, salary | requirements=1、扎实的工程基础：3年及以上Java/Python开发经验，熟悉主流开源框架及其原理，在后端技术领域有深厚积累；熟悉分布式系统的设计与应用，精通缓存、消息队列、存储等核心机制，能将分布式技术方案高质量落地。 2、系统设计能力：2年以上大型分布式系统开发与架构经验，或复杂B端系统的领域建模与系统设计经验；具备高度的抽象设计能力，思路清晰，能独立分析和解决复杂技术问题。 3、AI领域经验：具备AI相关项目经验，熟悉大语言模型（LLM）应用开发、Prompt工程、Agent架构、RAG等方向者优先。 4、全栈与快速学习能力：具备端到端开发能力，能在需要时跨越前后端边界；学习能力强，能快速掌握新技术并应用于实际业务。 5、产品感知与业务理解：有完整的产品开发项目经验，具备独立判断力，能与产品及业务团队进行深度对话，将业务诉求转化为技术方案。 6、协作与责任心：责任心强，具备良好的团队合作精神与风险预判能力，能在跨时区、跨文化的团队环境中高效协作。   加分项 1、有国际化/全球化产品研发经验，熟悉多区域部署架构 2、有英语或日语工作沟通能力 3、有企业级SaaS或PaaS平台研发经验 4、对AI Agent、多模态交互等前沿方向有实践探索, education=本科, url=https://talent.dingtalk.com/off-campus/position-detail?positionId=100013860006, experience=2年以上 |
| 5212 | dingtalk | 100013460012 | 钉钉 | 悟空事业部-Java 服务端开发工程师-钉钉视觉 AI 业务 | 杭州 | department, salary | requirements=1、计算机相关专业本科及以上学历，2 年以上 Java 服务端开发经验 2、技术基础扎实：精通 Java 及 JVM 原理，熟练掌握 Spring Boot/Cloud 框架；熟悉分布式系统和微服务架构；熟练使用 PolarDB, PostgreSQL ，MySQL，Redis 及消息队列（MetaQ/Kafka/RocketMQ） 3、工程能力强：具备良好代码规范和文档习惯，熟悉 Docker/Kubernetes 等容器化技术，有 CI/CD 建设和运维经验 4、Vibe Coding 经验优先：有 AI 辅助编程工具（Cursor/GitHub Copilot/Codeium 等）实战经验，熟悉 Prompt Engineering，能将 AI 编程融入日常流程并提升效率 5、加分项：有 CV 算法服务集成、GPU 资源管理、阿里云产品（OSS/SLS/ODPS/HSF）使用经验，或百万级日活系统开发经验, education=本科, url=https://talent.dingtalk.com/off-campus/position-detail?positionId=100013460012, experience=1年以上 |
| 5314 | feishu | 7624476433381869860 | 智谱AI | 解决方案架构师-北京 | 北京 | department, experience, education, salary | requirements=1. 本科及以上学历，计算机、通信、人工智能等相关专业。5-10年企业级应用架构、解决方案或项目技术管理经验。 2. 具备基于人工智能、云计算服务的解决方案分析和架构能力，了解生成式AI的最新行业动态、应用方向、对生成式AI在各领域落地的路径和可行性有认知和判断。 3. 具备团队意识、优秀的沟通技巧、文档编写、方案演讲和协调能力。能够在快节奏的环境中处理多个复杂项目支持，并以高执行力达到业绩目标。, education=, url=https://zhipu-ai.jobs.feishu.cn/index/position/7624476433381869860/detail, experience= |
| 5315 | feishu | 7624119064441653510 | 智谱AI | 销售-上海 | 上海 | department, experience, education, salary | requirements=1. Bachelor's or Master's degree in Computer Science, Engineering, Business, Marketing, or related fields (MBA preferred). Possess 5-10 years of enterprise sales experience within large global clients. 2. Work experience in sales or consulting in industries such as artificial intelligence, cloud computing. Have extensive resources among multinational corporate clients and experience in customer relationship management. Priority for those who have assisted global accounts in overseas expansions and entries into the Chinese market by providing business expansion consulting and technical services. 3. Possesses exceptional customer relationship management abilities, outstanding communication skills, adeptness in solution presentation, and effective resource utilization capabilities. Demonstrates the capacity to manage multiple complex projects in a fast-paced environment with strong execution skills to meet performance targets. Exhibits a skillset focused on teamwork and delivering results. Proficient in establishing mutually beneficial cooperation models and demonstrates resilience in high-pressure situations, education=, url=https://zhipu-ai.jobs.feishu.cn/index/position/7624119064441653510/detail, experience= |
| 23629 | jd | 220351 | 京东 | 用增产品运营 | 北京市 | experience, education, salary | requirements=1. 本科及以上学历，3年以上互联网产品经验，有保险、电商、金融C端产品增长经验者优先； 2.具备“独当一面”的业务闭环能力： 能独立完成从“发现问题 -> 抽象本质 -> 拆解路径 -> 落地拿结果”的全过程； 3. AI信仰与实践：对AI技术有极强的好奇心和敏锐度，愿意尝试或已有经验将AI引入日常工作流（如使用AI辅助数据分析、生成PRD、辅助编程等），不仅关注“做什么”，更关注“如何高效地做”。 4. 数据驱动（Data-Driven）： 对数据极度敏感，熟练掌握数据分析方法，能通过数据噪音发现业务真相。  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=220351, experience= |
| 23630 | jd | 220303 | 京东 | 销售策略 | 广东省 | experience, education, salary | requirements=任职要求 1. 教育背景 学历要求：本科及以上学历，物流管理、国际贸易等相关专业优先；专业不限，能力突出者亦可考虑； 2. 工作经验: 3年以上跨境物流背景，有海外仓解决方案及策略和销售开发工作经验优先 3. 能力要求： 对产品逻辑有基础了解，熟悉物流行业市场动态，具备较强的市场分析能力和销售策略制定能力；能够独立输出产品销售策略，推动内部协同；具备项目管理经验，能够有效管理和推进销售项目，确保项目目标的达成；具备基础的数据分析能力，能够通过数据分析指导方案策略的制定与优化； 4. 基本素质 具备良好的沟通能力和团队合作精神，能够与内部团队及外部客户建立良好的合作关系； 具备独立分析和解决问题的能力，能够在面对市场变化时迅速做出反应并提出有效的解决方案； 具有强烈的责任心和使命感，对工作认真负责，能够承受较大的工作压力； 具备创新意识，善于学习和探索新的销售策略和市场机会，不断提升个人和团队的业绩。  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=220303, experience= |
| 21396 | kuaishou | 27941 | 快手 | 可灵大模型资深销售经理（SKA客户 & 渠道方向） | 北京 | education, salary | requirements=1、学历背景：本科及以上学历，计算机、人工智能、市场营销、投资分析或相关专业优先； 2、行业经验：5年以上ToB企业软件/解决方案/销售经验，其中至少3年专注服务国内SKA客户；具备AI大模型、大数据、或企业数字化相关产品销售经验者优先； 3、资源与能力要求（关键项）：拥有丰富的国内SKA客户资源，尤其在金融、能源、制造、政务等行业具备高层决策链触达能力（如CIO、CTO、信息中心主任等）；具备成熟的渠道管理体系经验，曾主导建设或管理过覆盖全国或重点区域的渠道网络，熟悉渠道招募、赋能、考核与冲突管理；具备优秀的商务谈判、方案包装与项目运作能力，能独立主导千万级项目落地； 4、软性素质：结果导向，抗压能力强，适应高频出差；具备战略思维与长期客户经营意识，拒绝“一锤子买卖”；诚信正直，具备高度的商业敏感度与合规意识。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/27941, experience=不限 |
| 21397 | kuaishou | 25277 | 快手 | AI应用算法工程师(AIGC方向)-【生活服务】 | 北京 | education, salary | requirements=1、计算机科学、数据科学、人工智能、数学等相关专业，具备较好的数据分析和统计学基础，有根据数据表现驱动业务优化的经验； 2、在多模态生成、多模态理解等相关领域有深入的理解，有实际项目经验； 3、优秀的工程实践能力，熟悉pytorch/Tensorflow等深度学习框架，具备通过demo快速验证想法的能力； 4、做事具备主动推进意识，注重落地实际效果，追求质感和业务价值。  加分项： 1、熟悉传统机器学习方法，有使用机器学习完成分类/回归/聚类等实战问题的经验； 2、有深度学习/机器学习相关的科研和探索经历，在CV、NLP、多模态、机器学习等相关领域有高质量论文发表，或者数学建模、机器学习竞赛有获奖经历优先； 3、有AI直播、AI短视频或其他多模态大模型(图、视频理解和生成)实际业务应用落地经验优先。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/25277, experience=1-3年 |
| 19754 | meituan | 4611929667 | 美团 | 神抢手整合营销专家 | 北京市 | education, salary | requirements=1. 3-6 年互联网活动运营、整合营销、用户增长或平台型业务运营经验，有本地生活、电商、外卖、零售、内容平台经验优先。有 AI 工具在运营场景中的实操经验者优先。 2. 具备较强的营销策划能力，能把商品、价格、场景、用户情绪和传播内容结合起来，做出有新鲜感、有传播点、有业务结果的活动。了解 AI 在内容生成、智能推荐、用户洞察等方向的应用，具备用 AI 提升策划效率的意识。 3. 对用户和内容有感觉，熟悉小红书、抖音、视频号、知乎、朋友圈等不同渠道的用户心智和传播增长思路。了解 AIGC 内容创作逻辑和不同渠道的 AI 辅助内容分发策略。 4. 具备较强的自驱力和创新意识，不满足于执行既定活动，能主动提出新玩法、新机制、新资源组合，并推动验证。对新事物保持好奇，持续探索 AI 技术在营销增长场景中的落地应用。, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=4611929667&highlightType=social, experience=3年 |
| 19755 | meituan | 4610556543 | 美团 | 即时零售搜索产品经理 | 北京市 | education, salary | requirements=1、经验要求：5年以上互联网策略产品经验，3年以上搜推产品经验，有算法背景者优先； 2、技术理解力和用户理解力：对算法选型、技术能力边界、AI 应用有深入理解，能够充分结合技术架构和用户场景特点设计可行方案； 3、项目管理能力：具备良好的项目管理和团队协作能力，能识别核心问题并协调资源解决，推动项目快速落地。, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=4610556543&highlightType=social, experience=5年 |
| 1926 | netease | 77357 | 网易 | 淘系自直播运营 | 杭州市 | salary | requirements=1、本科及以上学历，3年以上直播运营及管理经验，对直播业务有全面的统筹和管理能力。 2、对AI应用感兴趣，通过AI持续提升工作效率，持续优化探索AI直播间。 3、熟悉淘系平台的规则和玩法、活动，了解淘系爆品打造底层逻辑，对市场、货品有较好的敏锐度。 4、具备很强的数据分析能力和解决问题能力，能独立通过人群、货品、流量结构、内容生态、用户等数据结合直播玩法输出方案。 5、责任心强，有管理经验，擅长团队协作，具备出色的理解能力、沟通能力和资源开拓能力。, education=本科, url=https://hr.163.com/job-detail.html?id=77357, experience=3-5年 |
| 1927 | netease | 64248 | 网易 | 高级产品运营（音乐人/C端） | 杭州市 | salary | requirements=1.本科及以上学历，3年以上产品运营经验，有创作者运营经验优先； 2.热爱音乐，对音乐行业的趋势和热点动态有较高的敏锐度； 3.逻辑清晰，具备较强的数据分析能力，能应用SQL处理数据，熟练使用AI辅助数据分析，并利用AI工具提升运营效率； 4.具备良好的沟通能力，可以与协同部门及合作方高效沟通，积极推动项目落地； 5.加分项：音乐专业或本人为音乐人，具备较高的音乐创作与审美能力。, education=不限, url=https://hr.163.com/job-detail.html?id=64248, experience=不限 |
| 4343 | quark | 100010020001 | 夸克 | 千问事业部-广告检索工程架构开发-北京 | 北京 | department, salary | requirements=1、本科及以上学历，热爱移动互联网，对计算广告行业有兴趣； 2、熟悉网络编程、多线程编程技术，有大规模系统的设计和开发经验 ； 3、具备良好的分析解决问题能力，能独立承担工作任务及把控任务进度； 4、精通C/C++开发语言，有使用甚至参与开源项目的经验更佳； 5、具有海量日志处理和并行计算开发经验的优先考虑； 6、有广告架构，搜索架构的相关开发经验优先。  在这里，你将获得： 超大规模系统挑战：参与天级超千亿广告检索请求的分布式系统架构设计，支撑高可靠服务稳定运行。 核心技术深耕：深入广告检索核心链路，持续优化吞吐、时延、稳定性与资源效率。 云原生与平台化建设：参与 PaaS 平台与资源调度优化，设计故障自愈、弹性伸缩等核心能力，推动系统智能化与自治化演进。, education=本科, url=https://talent.quark.cn/off-campus/position-detail?positionId=100010020001, experience=3年以上 |
| 4344 | quark | 100013000005 | 夸克 | 千问事业部-服务端研发工程师（UC浏览器）-北京 | 北京 | department, salary | requirements=1、计算机科学、软件工程、人工智能等相关专业，本科及以上学历；3 年以上工业级服务端研发经验，有大规模分布式系统实战经验者优先。 2、精通 Java / Python，熟悉语言生态与工程最佳实践；熟练掌握 Spring Boot、FastAPI 等主流框架，具备扎实的数据结构与算法功底。 3、熟悉主流数据库（MySQL / PostgreSQL）、缓存（Redis）、消息队列（Kafka / RocketMQ）及微服务架构（Dubbo / gRPC），具备高并发、高可用系统的设计与调优能力。 4、具备良好的沟通协作能力与技术文档写作能力，能清晰表达技术方案并推动跨团队落地。 5、熟练使用 Claude Code、Codex 等 AI 编程工具，具备全栈应用开发能力者优先。 6、具备 AI 应用或 AI Agent 相关技术的开发经验者优先。 7、热爱技术创新，有开源项目贡献、技术专利、技术博客或在技术社区具有一定影响力者优先。 8、有千万 / 亿级 DAU 产品的服务端架构经验，具备丰富的 B/C 端或工具型产品后端研发背景者优先。 9、对大模型微调、模型部署与推理优化有实际工程经验，有企业级 AI 应用项目落地经历者优先。  在这里，你将获得： 行业前列的技术平台：技术纵深扎实，场景宽度充足。 AI 变革先锋机会：AI 改造业务起点，创新空间大。 顶级 AI 资源：大模型 token 福利充足，AI 编程工具自由使用。 完善成长体系：新人专属导师，快速融入团队。, education=本科, url=https://talent.quark.cn/off-campus/position-detail?positionId=100013000005, experience=3年以上 |
| 1 | tencent | 2061995197415469056 | 腾讯 | S2—WXG财务管理（投入统筹与费用管理） | 深圳 | education, salary | requirements=1.本科及以上学历，商科相关专业； 2.对数字高度敏感，有好奇心；能熟练运用 SQL等统计工具进行数据提取和分析； 3.工作细致踏实，学习能力强；有较强的主观能动性和抗压能力； 4.有财务预算管理、政策管理、数据分析等工作经验者优先。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2061995197415469056, experience=两年以上工作经验 |
| 2 | tencent | 2059455036769091584 | 腾讯 | 混元 AI 产品经理（北京/深圳） | 北京 | education, salary | requirements=1.本科及以上学历，国内外优秀院校优先； 2.数学、计算机、工程、物理、认知科学、心理学、哲学等相关背景优先； 3.有大模型、Agent、AI 应用、Copilot、搜索/知识、工作流等相关产品经验优先； 4.有较强工程理解力，能够和算法、工程团队进行高质量协作； 5.有较强结构化思考能力，能把复杂问题讲清楚、拆明白； 6.具备 AI 产品评估意识和能力，能判断产品效果、定位问题，并推动优化闭环； 7.自驱力强，有 ownership，能在高不确定性中持续推进。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2059455036769091584, experience=两年以上工作经验 |
| 5135 | tongyi | 7000033602 | 通义实验室 | Token Foundry-视觉语言大模型算法工程师-Qwen | 北京, 杭州, 上海 | department, salary | requirements=1. 计算机科学、计算机视觉、人工智能、机器学习、具身智能等领域的博士/硕士毕业生。 2. 较强的代码能力，擅长模型训练及数据处理；精通Python及PyTorch等深度学习框架；熟悉Transformer架构以及CV、大语言模型基础知识。 3. 善于平衡研究目标及落地实现，具备跨学科视野与协作意识，能够与工程、产品等多学科团队紧密合作，推动研究成果快速落地并产生实际影响力。 4. 关注技术影响力，具有开源开放精神，对基础模型的前沿问题有持续热情，具备独立思考能力和系统性研究思维，敢于挑战现有范式，能够独立应用技术解决复杂问题。  加分项 1. 曾发表顶级会议论文并具有一定的学术影响力，包括但不限于：CVPR、ECCV、NeurIPS、ICML、ICLR、ACL、TPAMI等国际顶级计算机会议/期刊。 2. 拥有知名开源项目，在开源社区具有较好的影响力，或在竞赛中获得引领性的研究成果。 3. 具有大规模预训练实战经验。, education=硕士, url=https://careers-tongyi.alibaba.com/off-campus/position-detail?positionId=7000033602, experience=2年以上 |
| 5136 | tongyi | 100022900005 | 通义实验室 | Token Foundry-AI for Science/Engineering 算法专家-Qwen模型训练 | 北京, 杭州, 上海 | department, salary | requirements=1. 计算机、人工智能、自动化等相关专业本科及以上学历，硕士/博士优先。 2. 满足以下条件之一者优先： - 在科学研究或复杂工程领域具备较强的专业理解与积累，能够准确把握领域内的重要问题、核心参与方、关键数据资源和前沿发展方向；在相关方向具备较强的行业敏感度。 - 已在实际科学研究或工业领域将大模型深度融入工作流程，能够从领域问题出发完成方法设计、方案落地与效果迭代，并对AI与领域交叉方向的发展趋势形成较成熟的判断。 3. . 极强的求知欲与学习能力，对新技术保有好奇心；逻辑清晰，善于独立思考并反思总结；具备良好的沟通能力和团队协同意识。 4. 熟悉Python；具备较强的工程实现能力。 5. 具备较强科研能力或技术产出能力，有高水平论文、开源项目、竞赛成绩或实际落地成果者优先。, education=doctorate, url=https://careers-tongyi.alibaba.com/off-campus/position-detail?positionId=100022900005, experience=1年以上 |
| 22782 | xiaohongshu | 17766 | 小红书 | 电商产品经理-商家基础 | 上海市 | experience, education, salary | requirements=1、3年以上工作经验，有互联网产品策划/产品运营/策略运营等经验优先，对产品方向规划、目标设定、用户体验保证和市场推广具备较丰富的经验； 2、逻辑思维和沟通能力优秀，有较强的好奇心和学习能力，能够跨部门推动项目落地； 3、较强的数据敏感度，具有独立数据和经营分析的能力，能够通过数字化运营，持续打磨并优化产品能力； 4、有激情，具有突破、创新精神，自驱并能承受一定压力，喜欢有挑战性的工作。, education=, url=https://job.xiaohongshu.com/social/position/17766, experience= |
| 22783 | xiaohongshu | 20431 | 小红书 | 招聘专家 | 北京市，上海市 | experience, education, salary | requirements=1、本科及以上学历，3年以上招聘相关工作经验 2、具备良好的沟通和协调能力，能够高效对话沟通 3、具备敏锐的洞察力和分析能力，能够把握业务需求和人才发展方向 4、具备团队合作精神和强自驱力，能够独立完成项目任务, education=, url=https://job.xiaohongshu.com/social/position/20431, experience= |

## description_too_short（13）

| 行号 | platform | job_id | company | title | location | 详情 |
| ---: | --- | --- | --- | --- | --- | --- |
| 5366 | feishu | 7593245670041471238 | 智谱AI | AI产品实习生-上海 | 上海 | requirements=-, education=, url=https://zhipu-ai.jobs.feishu.cn/index/position/7593245670041471238/detail, experience=, length=2 |
| 5450 | feishu | 7527184302761855282 | 智谱AI | 产品测试 | 北京 | requirements=测试测试, education=, url=https://zhipu-ai.jobs.feishu.cn/index/position/7527184302761855282/detail, experience=, length=8 |
| 23815 | jd | 217522 | 京东 | 人才储备岗 | 北京市 | requirements=人才储备  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=217522, experience=, length=38 |
| 24049 | jd | 219062 | 京东 | 关务运营岗 | 北京市 | requirements=关务运营  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=219062, experience=, length=38 |
| 2772 | netease | 76904 | 网易 | 资深/高级游戏营销策划--燕云十六声 | 杭州市 | requirements=1, education=不限, url=https://hr.163.com/job-detail.html?id=76904, experience=不限, length=2 |
| 2943 | netease | 68165 | 网易 | 广州程序类岗位专项 | 广州市 | requirements=服务器开发/客户端开发等, education=不限, url=https://hr.163.com/job-detail.html?id=68165, experience=3-5年, length=24 |
| 23072 | xiaohongshu | 18147 | 小红书 | 电商运营高阶 | 上海市 | requirements=/, education=, url=https://job.xiaohongshu.com/social/position/18147, experience=, length=2 |
| 23084 | xiaohongshu | 18479 | 小红书 | 社区推荐策略产品经理 | 北京市，上海市 | requirements=推荐策略, education=, url=https://job.xiaohongshu.com/social/position/18479, experience=, length=8 |

## description_and_requirements_empty（0）

无样例。

## invalid_or_missing_url（0）

无样例。

## unparseable_education（21581）

| 行号 | platform | job_id | company | title | location | 详情 |
| ---: | --- | --- | --- | --- | --- | --- |
| 18259 | baidu | 5639c595-b85c-451e-b101-6a1a920ded73 | 百度 | 合同商务（J102187） | 北京市 | requirements=-具备一定的合同相关专业知识，统招本科及以上学历，财务、经济、金融、工商管理等专业背景优先  -2年以上合同管理和商务经验，有公有云合同和运营的经验优先  -内外部沟通协调能力强，有过处理大批量公有云合同或与客户直接沟通经验者优先  -具备AI在实际业务中有深刻理解，实际使用AI经验者优先, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/5639c595-b85c-451e-b101-6a1a920ded73, experience= |
| 18260 | baidu | ca254a37-0a5d-48f7-9f4e-90600d29a373 | 百度 | 大客户销售（J102184） | 上海市 | requirements=-5年以上金融领域销售经验，银行、消金、互金经验优先 -有独立拓展客户并完成业务/产品的销售能力 -目标导向，有比较强的自驱力，学习能力，沟通能力和应变能力, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/ca254a37-0a5d-48f7-9f4e-90600d29a373, experience= |
| 6616 | bytedance | 7658146308167715125 | 字节跳动 | 产品法务（海外音乐方向）（北京/上海） | 北京 | requirements=1、法学本科及以上学历，并具备律师执业资格； 2、具备在律所或担任内部法务的扎实经验，曾为面向消费者的数字音乐、视频技术或前沿科技应用提供深度的产品合规咨询； 3、对一个或多个亚太法域（如新加坡、日本、韩国、印尼）的数字音乐版权，以及中国版权法、平台责任与避风港原则有深入且广泛的理解；熟悉与数据使用及AI音乐产品/模型相关的知识产权问题者优先； 4、具备出色的商业敏锐度与战略思维，能够将复杂的法律风险转化为可落地的合规解决方案，在降低风险的同时赋能产品业务； 5、中英双语可作为工作语言；具备较强的书面与口头沟通能力，能够有效管理内部决策层的预期，与国际团队高效跨部门协作并按时交付成果。, education=, url=https://jobs.bytedance.com/experienced/position/7658146308167715125/detail, experience= |
| 6617 | bytedance | 7644763620393371909 | 字节跳动 | iOS资深研发工程师-TikTok研发 | 北京 | requirements=1、本科及以上学历，计算机、通信等相关专业，两年以上iOS开发经验； 2、有强烈的责任心，具备良好的沟通能力和优秀的团队协作能力；有较强的技术好奇心和钻研精神、强大的自驱力，具备优秀的解决问题和逻辑思维能力； 3、有性能优化、架构、SDK等经验者优先，有业务背景但对技术有深度追求者优先。, education=, url=https://jobs.bytedance.com/experienced/position/7644763620393371909/detail, experience= |
| 5590 | didi | JR2026070700E | 滴滴 | 模型推理优化工程师 | 北京市 | requirements=掌握Python/C++编程语言， 熟悉至少一种主流推理引擎（如 TensorRT、OnnxRuntime 等），并熟练使用至少一种大模型推理部署框架（如 vLLM、SGLang、TensorRT-LLM 等）； 熟悉GPU架构（如NVIDIA Hopper、ThorX），有CUDA/OpenMP编程经验者优先，熟悉CUDA 编程工具的使用；  具备优秀的沟通协作能力和扎实的问题分析与解决能力； ​加分项： 熟悉PyTorch等深度学习训练框架； 有大模型（LLaMA、Qwen、GPT等）服务化部署经验者优先。 熟悉vLLM、TGI、LightLLM、SGLang等大模型专用推理框架者优先。 熟悉 NVIDIA Thor 芯片架构，具备在其上进行模型部署、推理加速与资源调度优化的实际经验者优先；, education=, url=https://talent.didiglobal.com/social/p/65045, experience= |
| 5591 | didi | JR20260121002 | 滴滴 | 专家工程师（架构治理） | 北京市 | requirements=任职资格 1.全日制本科及以上学历，计算机相关专业，4年及以上相关工作经验 2.有深厚的技术功底，具有策略架构&在线数据架构的人员优先，较强的业务敏感度，具有良好的逻辑思维能力 3.熟悉业务抽象和数据模型设计，具有很强的分析问题、解决问题能力，对解决具有挑战性问题充满激情 4.知识面广，思路开阔，创新能力强，对新技术持有敏感性，并能合理利用相关技术 5. AI工具驱动落地：熟练使用Cursor、Copilot等AI编程工具加速代码生成与重构 加分项 1.熟练使用主流AI coding工具进行日常开发，能够通过提示词工程优化代码生成质量，具备将AI集成到开发流程（如CI/CD、自动化重构）的实践经验。 2.了解大语言模型基本原理，有利用AI辅助架构设计、代码迁移、遗留系统分析或自动化测试用例生成的实际案例者优先 3.具有策略架构 & 在线数据架构经验者优先；了解大语言模型基本原理，并有实际AI辅助架构设计或代码迁移案例者优先, education=, url=https://talent.didiglobal.com/social/p/61242, experience= |
| 5314 | feishu | 7624476433381869860 | 智谱AI | 解决方案架构师-北京 | 北京 | requirements=1. 本科及以上学历，计算机、通信、人工智能等相关专业。5-10年企业级应用架构、解决方案或项目技术管理经验。 2. 具备基于人工智能、云计算服务的解决方案分析和架构能力，了解生成式AI的最新行业动态、应用方向、对生成式AI在各领域落地的路径和可行性有认知和判断。 3. 具备团队意识、优秀的沟通技巧、文档编写、方案演讲和协调能力。能够在快节奏的环境中处理多个复杂项目支持，并以高执行力达到业绩目标。, education=, url=https://zhipu-ai.jobs.feishu.cn/index/position/7624476433381869860/detail, experience= |
| 5315 | feishu | 7624119064441653510 | 智谱AI | 销售-上海 | 上海 | requirements=1. Bachelor's or Master's degree in Computer Science, Engineering, Business, Marketing, or related fields (MBA preferred). Possess 5-10 years of enterprise sales experience within large global clients. 2. Work experience in sales or consulting in industries such as artificial intelligence, cloud computing. Have extensive resources among multinational corporate clients and experience in customer relationship management. Priority for those who have assisted global accounts in overseas expansions and entries into the Chinese market by providing business expansion consulting and technical services. 3. Possesses exceptional customer relationship management abilities, outstanding communication skills, adeptness in solution presentation, and effective resource utilization capabilities. Demonstrates the capacity to manage multiple complex projects in a fast-paced environment with strong execution skills to meet performance targets. Exhibits a skillset focused on teamwork and delivering results. Proficient in establishing mutually beneficial cooperation models and demonstrates resilience in high-pressure situations, education=, url=https://zhipu-ai.jobs.feishu.cn/index/position/7624119064441653510/detail, experience= |
| 23629 | jd | 220351 | 京东 | 用增产品运营 | 北京市 | requirements=1. 本科及以上学历，3年以上互联网产品经验，有保险、电商、金融C端产品增长经验者优先； 2.具备“独当一面”的业务闭环能力： 能独立完成从“发现问题 -> 抽象本质 -> 拆解路径 -> 落地拿结果”的全过程； 3. AI信仰与实践：对AI技术有极强的好奇心和敏锐度，愿意尝试或已有经验将AI引入日常工作流（如使用AI辅助数据分析、生成PRD、辅助编程等），不仅关注“做什么”，更关注“如何高效地做”。 4. 数据驱动（Data-Driven）： 对数据极度敏感，熟练掌握数据分析方法，能通过数据噪音发现业务真相。  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=220351, experience= |
| 23630 | jd | 220303 | 京东 | 销售策略 | 广东省 | requirements=任职要求 1. 教育背景 学历要求：本科及以上学历，物流管理、国际贸易等相关专业优先；专业不限，能力突出者亦可考虑； 2. 工作经验: 3年以上跨境物流背景，有海外仓解决方案及策略和销售开发工作经验优先 3. 能力要求： 对产品逻辑有基础了解，熟悉物流行业市场动态，具备较强的市场分析能力和销售策略制定能力；能够独立输出产品销售策略，推动内部协同；具备项目管理经验，能够有效管理和推进销售项目，确保项目目标的达成；具备基础的数据分析能力，能够通过数据分析指导方案策略的制定与优化； 4. 基本素质 具备良好的沟通能力和团队合作精神，能够与内部团队及外部客户建立良好的合作关系； 具备独立分析和解决问题的能力，能够在面对市场变化时迅速做出反应并提出有效的解决方案； 具有强烈的责任心和使命感，对工作认真负责，能够承受较大的工作压力； 具备创新意识，善于学习和探索新的销售策略和市场机会，不断提升个人和团队的业绩。  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=220303, experience= |
| 21396 | kuaishou | 27941 | 快手 | 可灵大模型资深销售经理（SKA客户 & 渠道方向） | 北京 | requirements=1、学历背景：本科及以上学历，计算机、人工智能、市场营销、投资分析或相关专业优先； 2、行业经验：5年以上ToB企业软件/解决方案/销售经验，其中至少3年专注服务国内SKA客户；具备AI大模型、大数据、或企业数字化相关产品销售经验者优先； 3、资源与能力要求（关键项）：拥有丰富的国内SKA客户资源，尤其在金融、能源、制造、政务等行业具备高层决策链触达能力（如CIO、CTO、信息中心主任等）；具备成熟的渠道管理体系经验，曾主导建设或管理过覆盖全国或重点区域的渠道网络，熟悉渠道招募、赋能、考核与冲突管理；具备优秀的商务谈判、方案包装与项目运作能力，能独立主导千万级项目落地； 4、软性素质：结果导向，抗压能力强，适应高频出差；具备战略思维与长期客户经营意识，拒绝“一锤子买卖”；诚信正直，具备高度的商业敏感度与合规意识。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/27941, experience=不限 |
| 21397 | kuaishou | 25277 | 快手 | AI应用算法工程师(AIGC方向)-【生活服务】 | 北京 | requirements=1、计算机科学、数据科学、人工智能、数学等相关专业，具备较好的数据分析和统计学基础，有根据数据表现驱动业务优化的经验； 2、在多模态生成、多模态理解等相关领域有深入的理解，有实际项目经验； 3、优秀的工程实践能力，熟悉pytorch/Tensorflow等深度学习框架，具备通过demo快速验证想法的能力； 4、做事具备主动推进意识，注重落地实际效果，追求质感和业务价值。  加分项： 1、熟悉传统机器学习方法，有使用机器学习完成分类/回归/聚类等实战问题的经验； 2、有深度学习/机器学习相关的科研和探索经历，在CV、NLP、多模态、机器学习等相关领域有高质量论文发表，或者数学建模、机器学习竞赛有获奖经历优先； 3、有AI直播、AI短视频或其他多模态大模型(图、视频理解和生成)实际业务应用落地经验优先。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/25277, experience=1-3年 |
| 19754 | meituan | 4611929667 | 美团 | 神抢手整合营销专家 | 北京市 | requirements=1. 3-6 年互联网活动运营、整合营销、用户增长或平台型业务运营经验，有本地生活、电商、外卖、零售、内容平台经验优先。有 AI 工具在运营场景中的实操经验者优先。 2. 具备较强的营销策划能力，能把商品、价格、场景、用户情绪和传播内容结合起来，做出有新鲜感、有传播点、有业务结果的活动。了解 AI 在内容生成、智能推荐、用户洞察等方向的应用，具备用 AI 提升策划效率的意识。 3. 对用户和内容有感觉，熟悉小红书、抖音、视频号、知乎、朋友圈等不同渠道的用户心智和传播增长思路。了解 AIGC 内容创作逻辑和不同渠道的 AI 辅助内容分发策略。 4. 具备较强的自驱力和创新意识，不满足于执行既定活动，能主动提出新玩法、新机制、新资源组合，并推动验证。对新事物保持好奇，持续探索 AI 技术在营销增长场景中的落地应用。, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=4611929667&highlightType=social, experience=3年 |
| 19755 | meituan | 4610556543 | 美团 | 即时零售搜索产品经理 | 北京市 | requirements=1、经验要求：5年以上互联网策略产品经验，3年以上搜推产品经验，有算法背景者优先； 2、技术理解力和用户理解力：对算法选型、技术能力边界、AI 应用有深入理解，能够充分结合技术架构和用户场景特点设计可行方案； 3、项目管理能力：具备良好的项目管理和团队协作能力，能识别核心问题并协调资源解决，推动项目快速落地。, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=4610556543&highlightType=social, experience=5年 |
| 2175 | netease | 77302 | 网易 | 资深GUI设计师（无限大） | 杭州市 | requirements=1.有3年以上（近期）移动端游戏项目开发经验，参与设计过多套系统GUI界面设计； 2.有一定手绘能力，能独立产出界面相关的功能图标及相关绘制工作； 3.有一定动效设计能力，协同动效设计师共同完成最终动态表现； 4.有Unity设计开发经验，MMO项目设计经验者优先考虑； 5.对工作认真负责，沟通能力良好，一定抗压能力。, education=其他, url=https://hr.163.com/job-detail.html?id=77302, experience=5-10年 |
| 2683 | netease | 76578 | 网易 | 资深GUI设计师（无限大） | 杭州市 | requirements=1.有3年以上（近期）移动端游戏项目开发经验，参与设计过多套系统GUI界面设计； 2.有一定手绘能力，能独立产出界面相关的功能图标及相关绘制工作； 3.有一定动效设计能力，协同动效设计师共同完成最终动态表现； 4.有Unity设计开发经验，MMO项目设计经验者优先考虑； 5.对工作认真负责，沟通能力良好，一定抗压能力。, education=其他, url=https://hr.163.com/job-detail.html?id=76578, experience=5-10年 |
| 1 | tencent | 2061995197415469056 | 腾讯 | S2—WXG财务管理（投入统筹与费用管理） | 深圳 | requirements=1.本科及以上学历，商科相关专业； 2.对数字高度敏感，有好奇心；能熟练运用 SQL等统计工具进行数据提取和分析； 3.工作细致踏实，学习能力强；有较强的主观能动性和抗压能力； 4.有财务预算管理、政策管理、数据分析等工作经验者优先。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2061995197415469056, experience=两年以上工作经验 |
| 2 | tencent | 2059455036769091584 | 腾讯 | 混元 AI 产品经理（北京/深圳） | 北京 | requirements=1.本科及以上学历，国内外优秀院校优先； 2.数学、计算机、工程、物理、认知科学、心理学、哲学等相关背景优先； 3.有大模型、Agent、AI 应用、Copilot、搜索/知识、工作流等相关产品经验优先； 4.有较强工程理解力，能够和算法、工程团队进行高质量协作； 5.有较强结构化思考能力，能把复杂问题讲清楚、拆明白； 6.具备 AI 产品评估意识和能力，能判断产品效果、定位问题，并推动优化闭环； 7.自驱力强，有 ownership，能在高不确定性中持续推进。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2059455036769091584, experience=两年以上工作经验 |
| 22782 | xiaohongshu | 17766 | 小红书 | 电商产品经理-商家基础 | 上海市 | requirements=1、3年以上工作经验，有互联网产品策划/产品运营/策略运营等经验优先，对产品方向规划、目标设定、用户体验保证和市场推广具备较丰富的经验； 2、逻辑思维和沟通能力优秀，有较强的好奇心和学习能力，能够跨部门推动项目落地； 3、较强的数据敏感度，具有独立数据和经营分析的能力，能够通过数字化运营，持续打磨并优化产品能力； 4、有激情，具有突破、创新精神，自驱并能承受一定压力，喜欢有挑战性的工作。, education=, url=https://job.xiaohongshu.com/social/position/17766, experience= |
| 22783 | xiaohongshu | 20431 | 小红书 | 招聘专家 | 北京市，上海市 | requirements=1、本科及以上学历，3年以上招聘相关工作经验 2、具备良好的沟通和协调能力，能够高效对话沟通 3、具备敏锐的洞察力和分析能力，能够把握业务需求和人才发展方向 4、具备团队合作精神和强自驱力，能够独立完成项目任务, education=, url=https://job.xiaohongshu.com/social/position/20431, experience= |

## unparseable_experience_years（17994）

| 行号 | platform | job_id | company | title | location | 详情 |
| ---: | --- | --- | --- | --- | --- | --- |
| 4884 | aliyun | 100013803004 | 阿里云 | 诚云科技-IDC运维工程师（资产）-中卫/乌兰察布/呼和浩特/廊坊/桐庐/宁波/嘉兴 | 廊坊, 乌兰察布, 嘉兴, 中卫, 呼和浩特, 杭州, 宁波 | requirements=1、2025届或2026届毕业生，有资产管理经验优先 2、具备良好的学习能力和执行力，能够将公司的资产管理要求准确同步至机房现场； 3、具备良好的管理能力，能够发现业务中的风险点和漏洞，并提出优化建议。, education=本科, url=https://careers.aliyun.com/off-campus/position-detail?positionId=100013803004, experience={'from': None, 'to': 0} |
| 5008 | aliyun | 100004323001 | 阿里云 | 诚云科技-IDC运维工程师（设施）-南京/上海/杭州/北京/中卫/惠州/常熟/平湖 | 北京, 嘉兴, 中卫, 常熟, 杭州, 南京, 上海 | requirements=1、暖通/电气相关专业，有数据中心基础设施运维经验优先； 2、具备良好的学习能力和执行力，快速学习和理解公司的设施管理要求 3、具备良好的问题发现和解决能力，能够发现业务中的风险点和漏洞，并提出优化建议。 4、持续建立并推广标准化的运维体系和流程，降低运维风险，提升运营效率； 5、能够驱动供应商在日常运维过程中提升配合意愿度来达成业务目标；, education=本科, url=https://careers.aliyun.com/off-campus/position-detail?positionId=100004323001, experience={'from': None, 'to': 0} |
| 18259 | baidu | 5639c595-b85c-451e-b101-6a1a920ded73 | 百度 | 合同商务（J102187） | 北京市 | requirements=-具备一定的合同相关专业知识，统招本科及以上学历，财务、经济、金融、工商管理等专业背景优先  -2年以上合同管理和商务经验，有公有云合同和运营的经验优先  -内外部沟通协调能力强，有过处理大批量公有云合同或与客户直接沟通经验者优先  -具备AI在实际业务中有深刻理解，实际使用AI经验者优先, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/5639c595-b85c-451e-b101-6a1a920ded73, experience= |
| 18260 | baidu | ca254a37-0a5d-48f7-9f4e-90600d29a373 | 百度 | 大客户销售（J102184） | 上海市 | requirements=-5年以上金融领域销售经验，银行、消金、互金经验优先 -有独立拓展客户并完成业务/产品的销售能力 -目标导向，有比较强的自驱力，学习能力，沟通能力和应变能力, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/ca254a37-0a5d-48f7-9f4e-90600d29a373, experience= |
| 6616 | bytedance | 7658146308167715125 | 字节跳动 | 产品法务（海外音乐方向）（北京/上海） | 北京 | requirements=1、法学本科及以上学历，并具备律师执业资格； 2、具备在律所或担任内部法务的扎实经验，曾为面向消费者的数字音乐、视频技术或前沿科技应用提供深度的产品合规咨询； 3、对一个或多个亚太法域（如新加坡、日本、韩国、印尼）的数字音乐版权，以及中国版权法、平台责任与避风港原则有深入且广泛的理解；熟悉与数据使用及AI音乐产品/模型相关的知识产权问题者优先； 4、具备出色的商业敏锐度与战略思维，能够将复杂的法律风险转化为可落地的合规解决方案，在降低风险的同时赋能产品业务； 5、中英双语可作为工作语言；具备较强的书面与口头沟通能力，能够有效管理内部决策层的预期，与国际团队高效跨部门协作并按时交付成果。, education=, url=https://jobs.bytedance.com/experienced/position/7658146308167715125/detail, experience= |
| 6617 | bytedance | 7644763620393371909 | 字节跳动 | iOS资深研发工程师-TikTok研发 | 北京 | requirements=1、本科及以上学历，计算机、通信等相关专业，两年以上iOS开发经验； 2、有强烈的责任心，具备良好的沟通能力和优秀的团队协作能力；有较强的技术好奇心和钻研精神、强大的自驱力，具备优秀的解决问题和逻辑思维能力； 3、有性能优化、架构、SDK等经验者优先，有业务背景但对技术有深度追求者优先。, education=, url=https://jobs.bytedance.com/experienced/position/7644763620393371909/detail, experience= |
| 5590 | didi | JR2026070700E | 滴滴 | 模型推理优化工程师 | 北京市 | requirements=掌握Python/C++编程语言， 熟悉至少一种主流推理引擎（如 TensorRT、OnnxRuntime 等），并熟练使用至少一种大模型推理部署框架（如 vLLM、SGLang、TensorRT-LLM 等）； 熟悉GPU架构（如NVIDIA Hopper、ThorX），有CUDA/OpenMP编程经验者优先，熟悉CUDA 编程工具的使用；  具备优秀的沟通协作能力和扎实的问题分析与解决能力； ​加分项： 熟悉PyTorch等深度学习训练框架； 有大模型（LLaMA、Qwen、GPT等）服务化部署经验者优先。 熟悉vLLM、TGI、LightLLM、SGLang等大模型专用推理框架者优先。 熟悉 NVIDIA Thor 芯片架构，具备在其上进行模型部署、推理加速与资源调度优化的实际经验者优先；, education=, url=https://talent.didiglobal.com/social/p/65045, experience= |
| 5591 | didi | JR20260121002 | 滴滴 | 专家工程师（架构治理） | 北京市 | requirements=任职资格 1.全日制本科及以上学历，计算机相关专业，4年及以上相关工作经验 2.有深厚的技术功底，具有策略架构&在线数据架构的人员优先，较强的业务敏感度，具有良好的逻辑思维能力 3.熟悉业务抽象和数据模型设计，具有很强的分析问题、解决问题能力，对解决具有挑战性问题充满激情 4.知识面广，思路开阔，创新能力强，对新技术持有敏感性，并能合理利用相关技术 5. AI工具驱动落地：熟练使用Cursor、Copilot等AI编程工具加速代码生成与重构 加分项 1.熟练使用主流AI coding工具进行日常开发，能够通过提示词工程优化代码生成质量，具备将AI集成到开发流程（如CI/CD、自动化重构）的实践经验。 2.了解大语言模型基本原理，有利用AI辅助架构设计、代码迁移、遗留系统分析或自动化测试用例生成的实际案例者优先 3.具有策略架构 & 在线数据架构经验者优先；了解大语言模型基本原理，并有实际AI辅助架构设计或代码迁移案例者优先, education=, url=https://talent.didiglobal.com/social/p/61242, experience= |
| 5314 | feishu | 7624476433381869860 | 智谱AI | 解决方案架构师-北京 | 北京 | requirements=1. 本科及以上学历，计算机、通信、人工智能等相关专业。5-10年企业级应用架构、解决方案或项目技术管理经验。 2. 具备基于人工智能、云计算服务的解决方案分析和架构能力，了解生成式AI的最新行业动态、应用方向、对生成式AI在各领域落地的路径和可行性有认知和判断。 3. 具备团队意识、优秀的沟通技巧、文档编写、方案演讲和协调能力。能够在快节奏的环境中处理多个复杂项目支持，并以高执行力达到业绩目标。, education=, url=https://zhipu-ai.jobs.feishu.cn/index/position/7624476433381869860/detail, experience= |
| 5315 | feishu | 7624119064441653510 | 智谱AI | 销售-上海 | 上海 | requirements=1. Bachelor's or Master's degree in Computer Science, Engineering, Business, Marketing, or related fields (MBA preferred). Possess 5-10 years of enterprise sales experience within large global clients. 2. Work experience in sales or consulting in industries such as artificial intelligence, cloud computing. Have extensive resources among multinational corporate clients and experience in customer relationship management. Priority for those who have assisted global accounts in overseas expansions and entries into the Chinese market by providing business expansion consulting and technical services. 3. Possesses exceptional customer relationship management abilities, outstanding communication skills, adeptness in solution presentation, and effective resource utilization capabilities. Demonstrates the capacity to manage multiple complex projects in a fast-paced environment with strong execution skills to meet performance targets. Exhibits a skillset focused on teamwork and delivering results. Proficient in establishing mutually beneficial cooperation models and demonstrates resilience in high-pressure situations, education=, url=https://zhipu-ai.jobs.feishu.cn/index/position/7624119064441653510/detail, experience= |
| 23629 | jd | 220351 | 京东 | 用增产品运营 | 北京市 | requirements=1. 本科及以上学历，3年以上互联网产品经验，有保险、电商、金融C端产品增长经验者优先； 2.具备“独当一面”的业务闭环能力： 能独立完成从“发现问题 -> 抽象本质 -> 拆解路径 -> 落地拿结果”的全过程； 3. AI信仰与实践：对AI技术有极强的好奇心和敏锐度，愿意尝试或已有经验将AI引入日常工作流（如使用AI辅助数据分析、生成PRD、辅助编程等），不仅关注“做什么”，更关注“如何高效地做”。 4. 数据驱动（Data-Driven）： 对数据极度敏感，熟练掌握数据分析方法，能通过数据噪音发现业务真相。  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=220351, experience= |
| 23630 | jd | 220303 | 京东 | 销售策略 | 广东省 | requirements=任职要求 1. 教育背景 学历要求：本科及以上学历，物流管理、国际贸易等相关专业优先；专业不限，能力突出者亦可考虑； 2. 工作经验: 3年以上跨境物流背景，有海外仓解决方案及策略和销售开发工作经验优先 3. 能力要求： 对产品逻辑有基础了解，熟悉物流行业市场动态，具备较强的市场分析能力和销售策略制定能力；能够独立输出产品销售策略，推动内部协同；具备项目管理经验，能够有效管理和推进销售项目，确保项目目标的达成；具备基础的数据分析能力，能够通过数据分析指导方案策略的制定与优化； 4. 基本素质 具备良好的沟通能力和团队合作精神，能够与内部团队及外部客户建立良好的合作关系； 具备独立分析和解决问题的能力，能够在面对市场变化时迅速做出反应并提出有效的解决方案； 具有强烈的责任心和使命感，对工作认真负责，能够承受较大的工作压力； 具备创新意识，善于学习和探索新的销售策略和市场机会，不断提升个人和团队的业绩。  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=220303, experience= |
| 21396 | kuaishou | 27941 | 快手 | 可灵大模型资深销售经理（SKA客户 & 渠道方向） | 北京 | requirements=1、学历背景：本科及以上学历，计算机、人工智能、市场营销、投资分析或相关专业优先； 2、行业经验：5年以上ToB企业软件/解决方案/销售经验，其中至少3年专注服务国内SKA客户；具备AI大模型、大数据、或企业数字化相关产品销售经验者优先； 3、资源与能力要求（关键项）：拥有丰富的国内SKA客户资源，尤其在金融、能源、制造、政务等行业具备高层决策链触达能力（如CIO、CTO、信息中心主任等）；具备成熟的渠道管理体系经验，曾主导建设或管理过覆盖全国或重点区域的渠道网络，熟悉渠道招募、赋能、考核与冲突管理；具备优秀的商务谈判、方案包装与项目运作能力，能独立主导千万级项目落地； 4、软性素质：结果导向，抗压能力强，适应高频出差；具备战略思维与长期客户经营意识，拒绝“一锤子买卖”；诚信正直，具备高度的商业敏感度与合规意识。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/27941, experience=不限 |
| 21399 | kuaishou | 23944 | 快手 | 童装童鞋行业运营-【电商】 | 杭州 | requirements=1.本科及以上学历，熟悉内容平台运营体系，有童装商家和品牌、达人资源从业背景优先； 2.极强的BD能力，自驱力较强，快速拿结果，具备结构性思维能力和担当； 3.善于跨部门沟通，善于团队合作，有一定创新能力，乐观开朗，执行力和抗压能力强。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/23944, experience=不限 |
| 19769 | meituan | 4596888205 | 美团 | 无人车业务部-综合采购 | 上海市,北京市 | requirements=1. 大学本科及以上学历，供应链管理、机械工程、自动化或相关专业优先。   2. 具备无人车间、智能制造或工业自动化领域采购经验者优先。   3. 熟悉采购流程、供应商管理及成本控制方法，具备较强的谈判与沟通能力。   4. 具备较强的数据分析能力与跨部门协作能力，能独立推动项目落地。   5. 工作城市为上海市、深圳市或北京市，能适应一定频率的出差。, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=4596888205&highlightType=social, experience=不限 |
| 19819 | meituan | 4342032148 | 美团 | 无人车业务部-动态感知算法工程师 | 北京市,深圳市 | requirements=1. 硕士及以上学历，计算机、电子、自动化、应用数学等相关专业，5 年以上相关经验。 2. 在计算机视觉或三维感知领域有深入认知，精通动态障碍物检测、分割、跟踪等核心算法中至少一个方向。 3. 具备良好的深度学习基础，熟悉 Transformer、CNN 等主流模型架构，有实际的模型调优和工程落地经验。 4. 熟练掌握 Python / C++，有良好的编程习惯和代码架构意识。 5. 具备较强的 Problem Solving 能力，能够独立分析长尾场景失效原因并推动解决。, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=4342032148&highlightType=social, experience=不限 |
| 1927 | netease | 64248 | 网易 | 高级产品运营（音乐人/C端） | 杭州市 | requirements=1.本科及以上学历，3年以上产品运营经验，有创作者运营经验优先； 2.热爱音乐，对音乐行业的趋势和热点动态有较高的敏锐度； 3.逻辑清晰，具备较强的数据分析能力，能应用SQL处理数据，熟练使用AI辅助数据分析，并利用AI工具提升运营效率； 4.具备良好的沟通能力，可以与协同部门及合作方高效沟通，积极推动项目落地； 5.加分项：音乐专业或本人为音乐人，具备较高的音乐创作与审美能力。, education=不限, url=https://hr.163.com/job-detail.html?id=64248, experience=不限 |
| 1930 | netease | 56088 | 网易 | 项目管理实习生 | 杭州市 | requirements=1、2027届及之后毕业的同学，有转正机会 2、 热爱游戏，有志于在游戏行业一展才华； 3、良好的学习能力，愿意在工作岗位上持续学习； 4、优秀的逻辑分析、沟通、组织与协调能力，能很快融入团队，能清晰、准确的在团队中传达自己的想法，并敢于提出自己的想法和建议； 5、做事认真负责、细心严谨，具备团队精神、责任心和工作主动性； 6、能够承受工作压力，具有抗压能力和多任务处理能力； 7、对美术或者动画有一定基础优先； 8、自动化、电子信息、计算机、软件工程等相关专业优先； 9、实习期4个月及以上，有意愿长期实习并转正的同学优先； 10、协助管线的负责人制定项目的计划和时间表； 11、负责推动团队日常执行工作，负责进度跟踪和把控，确保工作按计划完成； 12、收集管线进度状态并准备清晰、透明、高效的项目管理状态报告； 13、有PM相关实习经历的优先  注：投递简历时请附带游戏经历或将游戏经历在简历中说明。, education=本科, url=https://hr.163.com/job-detail.html?id=56088, experience=不限 |
| 20 | tencent | 2037411502792798208 | 腾讯 | 微信-AI Infra工程师-大模型推理方向 | 北京 | requirements=1.熟练掌握 C/C++、Python语言，有计算机体系结构背景或软件开发背景，熟悉系统性能调优的方式； 2.具备基础的GPU编程能力，包括但不限于Cuda、OpenCL；熟悉至少一种GPU加速库，如cublas、cudnn、cutlass等； 3.有Tensorrt/FasterTransformer/Tensorrt-llm/vllm/sglang等深度学习推理框架的实际使用经验； 4.熟悉各类深度学习网络和算子底层实现细节，训练和推理模型调试、调优有实操经验优先； 5.熟悉CPU/GPU异构加速瓶颈分析方法，有服务器端 AI 芯片、GPU加速经验优先； 6.熟悉分布式推理常用加速方法，有超大模型分布式部署经验优先。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2037411502792798208, experience=不限 |
| 21 | tencent | 2037392058448248832 | 腾讯 | 微信-产品经理-AI方向 | 广州 | requirements=1.对 AI 在微信生态下的独特价值有想法，有思考，有想象力； 2.强烈的好奇心和探索欲，极强的执行力和推动力； 3.积极主动，深入思考，实事求是，诚恳谦逊； 4.有 AI 助手方向算法/策略侧工作经历加分。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2037392058448248832, experience=不限 |
| 22782 | xiaohongshu | 17766 | 小红书 | 电商产品经理-商家基础 | 上海市 | requirements=1、3年以上工作经验，有互联网产品策划/产品运营/策略运营等经验优先，对产品方向规划、目标设定、用户体验保证和市场推广具备较丰富的经验； 2、逻辑思维和沟通能力优秀，有较强的好奇心和学习能力，能够跨部门推动项目落地； 3、较强的数据敏感度，具有独立数据和经营分析的能力，能够通过数字化运营，持续打磨并优化产品能力； 4、有激情，具有突破、创新精神，自驱并能承受一定压力，喜欢有挑战性的工作。, education=, url=https://job.xiaohongshu.com/social/position/17766, experience= |
| 22783 | xiaohongshu | 20431 | 小红书 | 招聘专家 | 北京市，上海市 | requirements=1、本科及以上学历，3年以上招聘相关工作经验 2、具备良好的沟通和协调能力，能够高效对话沟通 3、具备敏锐的洞察力和分析能力，能够把握业务需求和人才发展方向 4、具备团队合作精神和强自驱力，能够独立完成项目任务, education=, url=https://job.xiaohongshu.com/social/position/20431, experience= |

## unparseable_scraped_at（0）

无样例。

## duplicate_platform_job_id（0）

重复组数：0

无样例。

## suspected_duplicate_company_title_location（443）

重复组数：372

| 重复键 | 出现次数 | 行号 | URL |
| --- | ---: | --- | --- |
| title=腾讯视频-ai动漫制片人, location=北京, company=腾讯, description=1.ai技术与动画创意融合：深度结合动画制作需求，探索并引入前沿的aigc技术与工具（如runway、midjourney、stable diffusion、可灵、即梦等），应用于ip的前期创意开发； 2.动画制作流程重构与优化：主导ai技术在动画制作全流程中的落地应用，设计并推行融合aigc工具的高效动画制作工作流； 3.全流程项目管理与质量把控：负责ai动画项目的全流程制片管理，包括项目策划、预算制定、进度管控、资源协调与风险控制； 4.团队赋能与行业洞察：持续关注ai技术与动画行业的最新动态，挖掘新的应用场景与商业机会，推动团队技术创新与业务增长。 | 2 | 24, 42 | http://careers.tencent.com/jobdesc.html?postId=2074034574983348224<br>http://careers.tencent.com/jobdesc.html?postId=2028676570826309632 |
| title=高级战斗策划（遗忘之海）, location=杭州市, company=网易, description=1、从游戏性和战斗定位出发，遵循战斗管线规则，设计角色战斗机制，制作并验证其玩法原型，形成明确的战斗循环设计，制作并迭代至成品 2、同文案、美术等写作，产出符合规范和设计要求的需求，制作具有强表现力的战斗体验 3、负责战斗基础镜头规则梳理归纳，为战斗技能表现提供镜头支持 4、协同系统、数值，完善角色养成体验 5、完善上述涉及的管线规则，提质提效，保障后续执行推进合理有序。 | 2 | 1938, 2960 | https://hr.163.com/job-detail.html?id=63732<br>https://hr.163.com/job-detail.html?id=76564 |
| title=大模型销售经理-上海, location=上海, company=智谱ai, description=我们团队专注于将glm系列大型模型推向商业市场，服务于中央企业、国有企业、金融机构、能源行业等高端企业客户。我们致力于帮助这些客户迅速搭建起新一代人工智能的平台架构，培育技术力量，并实现场景化的应用部署。 依托于我们构建的企业级原生大模型应用开发平台，我们为用户提供了一系列专业化的产品与服务，覆盖音视频智能分析、多源异构知识整合管理、项目全生命周期研发支持、零代码的大模型应用快速开发，以及客户关键业务流程的智能化应用等多个领域。我们的目标是通过提升企业的运营效率，推动客户智能化转型，从而为企业带来更加深远的价值增长。 1、公司大模型相关产品及应用在各个领域的开拓及销售，建立并维护关键客户关系；深入调研客户业务场景、技术架构和数字化转型需求，精准定位大模型技术的应用切入点；制定并执行个人销售计划，完成公司设定的销售指标。 2、作为客户的“ai顾问”，向客户清晰、专业地阐述公司大模型产品的技术优势、核心价值和成功案例；负责撰写项目需求文档、技术方案、招投标文件等技术文档，完成招投标环节。 3、制定相关产品的商务拓展策略，有计划地推动商务合作及市场开拓；主导完整的销售流程，包括需求挖掘、方案呈现、商务谈判、合同签订及回款跟进。 4、提供市场趋势，需求变化，竞争对手和客户反馈方面的准确信息，为公司制定销售及市场策略提供可行性建议；沉淀销售方法论、行业解决方案和客户成功案例，并在团队内部进行分享，赋能团队共同成长。 | 2 | 5361, 5532 | https://zhipu-ai.jobs.feishu.cn/index/position/7594691075017951538/detail<br>https://zhipu-ai.jobs.feishu.cn/index/position/7390273385437235483/detail |
| title=高级软件研发工程师, location=北京市, company=滴滴, description=1. 负责滴滴租车业务系统的架构设计及系统开发 2. 充分理解并深入挖掘业务需求，基于此制定前瞻性的系统规划，推动系统的持续进化 3. 具备较强的技术攻关能力，持续优化系统架构、性能和稳定性 | 2 | 5633, 5695 | https://talent.didiglobal.com/social/p/64063<br>https://talent.didiglobal.com/social/p/62233 |
| title=社区产品经理（抖省省）-抖音生活服务, location=北京, company=字节跳动, description=1、社区从0到1建设：主导「抖省省」本地吃喝玩乐内容社区的产品规划与架构设计，从发现美好生活、分享探店避坑的年轻化视角出发，打造高活跃、强种草、有温度的本地生活内容阵地； 2、产品创新与体验打磨：打破传统本地生活产品的工具感，探索图文、短视频、互动组件等多元化内容体裁与创新玩法（如个性化榜单、打卡地图、兴趣圈子等），为年轻用户提供有趣、有用且极致流畅的浏览与互动体验； 3、内容生态与分发策略：具备生态视角，协同运营制定创作者入驻与内容沉淀的产品机制，协同算法团队优化搜推联动策略（“推后搜”、“搜后推”），提升优质内容的分发效率及从“种草”到“到店/交易”的转化渗透率； 4、用户心理与趋势洞察：深入研究新时代及年轻客群在餐饮、休闲娱乐等领域的消费趋势与社交行为模式，将时下热点敏捷转化为产品落地； 5、数据驱动与跨组协同：建立社区健康度与业务漏斗转化指标体系，与运营、内容生态、推荐算法及商业化团队紧密配合，实现社区内容规模与商业变现的双向共赢。 | 2 | 6688, 10777 | https://jobs.bytedance.com/experienced/position/7631808185550096645/detail<br>https://jobs.bytedance.com/experienced/position/7631807594580363525/detail |
| title=databuilder 产品经理（j95916）, location=北京市, company=百度, description=-负责大模型应用数据准备平台整体规划、产品设计与落地运营，围绕数据采集、清洗、标注、治理、特征工程、向量数据构建等核心环节，制定ai 原生数据产品路线图与产品策略 -深度参与数据中台与数据治理体系建设，负责数据标准、元数据管理、数据质量、数据安全、数据权限等产品能力设计，构建面向大模型场景的高质量、高可信、高可用数据底座 -开展市场与用户调研，挖掘业务侧、算法侧、研发侧对大模型数据加工、数据治理、数据服务的真实需求，输出高质量 prd 与产品方案，持续提升数据产品易用性与效率 -协同数据研发、ai 工程、架构、测试、市场、销售等团队，推动数据中台能力、数据治理工具、大模型数据平台的研发落地、联调测试与上线交付 -负责产品上线后数据埋点、效果跟踪与深度数据分析，围绕数据产出效率、数据质量、模型效果等指标持续迭代优化 -配合市场与销售团队，输出产品方案、最佳实践与客户化支撑，推动数据产品与 ai 能力的商业化落地与推广 | 2 | 18267, 18269 | https://talent.baidu.com/jobs/detail/SOCIAL/4cf88973-571c-4dd8-8e17-229eb1bbf7e7<br>https://talent.baidu.com/jobs/detail/SOCIAL/80e86000-3c46-422d-b864-28e8d2fa17cb |
| title=酒类品牌旗舰店运营, location=北京市, company=美团, description=1.负责白酒品牌旗舰店的引入和日常运营工作 2.负责制定所负责品牌旗舰店的销售及推广计划 3.负责迭代品牌旗舰店的运营策略并总结认知 4.负责项目的数据分析和业绩评估，及时调整策略以实现业绩目标 岗位亮点 1.可以获得酒类头部品牌合作机会，提升自身行业资源 2.可以在酒类品牌旗舰店在即时零售场景的运营中展现自己的才华，实现个人职业发展； | 2 | 19777, 20488 | https://zhaopin.meituan.com/web/position/detail?jobUnionId=4585744479&highlightType=social<br>https://zhaopin.meituan.com/web/position/detail?jobUnionId=4344667660&highlightType=social |
| title=行业运营专家（服饰方向）-【电商】, location=杭州, 北京, company=快手, description=1、负责服饰行业的商家商业化营收结果负责：深入分析所bp行业的竞争态势、客户画像及经营模式，基于商家分型特点和适配的产品能力做差异化商家策略和落地闭环； 2、客户运营对ka商业化增量负责：负责行业头客精细化运营，建立并维护长期稳定的客户关系。通过数据分析、定期复盘和策略沟通，帮助客户提高生意增长以及商业化产品能力的分层适配渗透； 3、运营体系与效率提升：搭建并持续优化所负责行业的运营sop，沉淀方法论，包含新商孵化成长、商家分层的跃迁，与销售、产运、推动解决客户运营中的共性难题，提升整体运营效率； 4、数据分析与驱动决策：建立行业核心数据监控体系，定期分析消耗、留存、流失等关键指标，定位问题并提出改进方案。通过对客户行为数据的深度分析，发现增长机会点，并推动运营策略的迭代优化。 | 2 | 21416, 21783 | https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/27352<br>https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/31366 |
| title=湖仓专家, location=北京市，上海市，杭州市, company=小红书, description=1. 主导云原生数据湖架构设计与落地，参与公司湖仓链路建设，支撑bi+ai业务场景。 2. 基于湖仓架构，完善相关的生态和产品，提供更低成本、更高效率的数据开发范式。 3. 和开源社区保持沟通合作，提升团队和个人在业界的影响力。 | 2 | 23183, 23193 | https://job.xiaohongshu.com/social/position/20493<br>https://job.xiaohongshu.com/social/position/18237 |
| title=策略运营岗, location=北京市, company=京东, description=1. 负责制定和优化平台策略，确保策略的有效实施，推动业务增长； 2. 分析市场趋势与竞争对手动态，提供数据支持，制定有竞争力的市场策略； 3. 与产品、运营等团队紧密合作，确保策略与业务目标一致，提升用户体验与满意度； 4. 监控策略执行效果，定期进行策略评估与调整，确保策略的持续优化与业务目标的达成； 5. 领导并指导团队成员，提升团队整体策略制定与执行能力，推动团队成长与发展。 | 2 | 23651, 24801 | https://zhaopin.jd.com/web/job-info-detail?requementId=219977<br>https://zhaopin.jd.com/web/job-info-detail?requementId=213771 |

## manifest_incomplete_platforms（2）

| platform | complete | status | stopped_by |
| --- | --- | --- | --- |
| aliyun | False | partial | empty_page |
| feishu | False | partial | company_error |

## manifest_abnormal_stopped_by（2）

| platform | complete | status | stopped_by |
| --- | --- | --- | --- |
| feishu | False | partial | company_error |
| bytedance | True | success | all_city_totals_reached |
