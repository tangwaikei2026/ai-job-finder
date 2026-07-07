# RawJobPosting 数据质量报告

- 生成时间：2026-07-07T12:58:53+08:00
- 输入文件：`data/raw/2026-07-07.json`
- 总岗位数：25241
- 计数口径：缺失字段按缺失字段值计数；重复按同一键中超过首条的额外记录数计数。
- 短描述定义：去除首尾空白后少于 50 个字符。

## 按 platform 统计

| platform | 数量 |
| --- | ---: |
| aliyun | 463 |
| baidu | 1500 |
| bytedance | 11650 |
| didi | 995 |
| dingtalk | 102 |
| feishu | 562 |
| jd | 1313 |
| kuaishou | 1411 |
| meituan | 1670 |
| netease | 2405 |
| quark | 330 |
| tencent | 1923 |
| tongyi | 73 |
| xiaohongshu | 844 |

## 平台采集计数

| platform | raw | in_scope | details_fetched | detail_failed |
| --- | ---: | ---: | ---: | ---: |
| aliyun | 463 | 463 | 0 | 0 |
| baidu | 1500 | 1500 | 0 | 0 |
| bytedance | 11650 | 11650 | 0 | 0 |
| didi | 995 | 995 | 995 | 0 |
| dingtalk | 102 | 102 | 0 | 0 |
| feishu | 562 | 562 | 0 | 0 |
| jd | 1313 | 1313 | 0 | 0 |
| kuaishou | 1411 | 1411 | 0 | 0 |
| meituan | 1670 | 1670 | 476 | 1194 |
| netease | 2405 | 2405 | 0 | 0 |
| quark | 330 | 330 | 0 | 0 |
| tencent | 1923 | 1923 | 1923 | 0 |
| tongyi | 73 | 73 | 0 | 0 |
| xiaohongshu | 844 | 844 | 0 | 0 |

## 问题汇总

| 问题 | 数量 |
| --- | ---: |
| missing_required_fields | 2 |
| missing_optional_fields | 67518 |
| description_too_short | 15 |
| description_and_requirements_empty | 2 |
| invalid_or_missing_url | 0 |
| duplicate_platform_job_id | 0 |
| suspected_duplicate_company_title_location | 441 |
| manifest_job_count_mismatch | 0 |
| manifest_incomplete_platforms | 3 |
| manifest_abnormal_stopped_by | 4 |
| unparseable_education | 21874 |
| unparseable_experience_years | 19360 |
| unparseable_scraped_at | 0 |

## missing_required_fields

总缺失字段值：2

| 缺失字段 | 数量 |
| --- | ---: |
| job_id | 0 |
| platform | 0 |
| title | 0 |
| company | 0 |
| description | 2 |
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

### description（2）

| 行号 | platform | job_id | company | title | location | 缺失字段 | 详情 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 5730 | feishu | 7656749825794476315 | 商汤科技 | 大模型算法实习生-金融方向 | 北京, 深圳, 上海 | description | requirements= , education=, url=https://sensetime.jobs.feishu.cn/index/position/7656749825794476315/detail, experience= |
| 5782 | feishu | 7647817236132481331 | 商汤科技 | 大模型算法实习生-数据生产与文档解析 | 深圳 | description | requirements=, education=, url=https://sensetime.jobs.feishu.cn/index/position/7647817236132481331/detail, experience= |

### location（0）

无样例。

### url（0）

无样例。


## missing_optional_fields

总缺失字段值：67518

| 缺失字段 | 数量 |
| --- | ---: |
| department | 1068 |
| experience | 18138 |
| education | 21859 |
| salary | 25241 |
| requirements | 1212 |

### 按平台岗位样例（每个平台 2 条，不足则全部）

| 行号 | platform | job_id | company | title | location | 缺失字段 | 详情 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 4659 | aliyun | 100000183002 | 阿里云 | 阿里云智能-技术-方案与服务-技术服务-海外事业部-国际客户技术服务部-GKA-A服务部 | 上海 | salary | requirements=• 5年以上大型互联网应用或集团型企业应用的解决方案、架构设计、服务端开发、交付、运维相关经验 • 具备技术背景、有基于云产品的大规模应用开发或运维经验 • 具备运维管理能力，能够对客户的系统进行全面管理和优化，确保云平台的稳定性与高效性 • 能够协调内外部干系人，独立完成简单客户项目管理或内部复杂项目管理，满足服务交付SLA，客户或业务方满意度高 • 准确识别和分类客户及关键干系人，针对不同的客户群体建立不同的应对措施 • 营造沟通氛围，把握沟通要点，有效倾听，清晰表达 • 良好的服务意识，能够对客户问题一根到底，切实帮助客户解决难题，并能保证客户满意度 • 对于特定领域，能够在有准备的情况下与客户高层沟通 • 具备系统性和全面性的解决方案设计和架构能力，能在复杂的技术环境下为客户提供可靠的解决方案 • 具备将复杂技术问题进行分解，形成综合技术判断和解决思路的能力 • 能独立完成一套基本的系统架构设计，仅涉及单个技术产品 • 掌握常见业务场景下的实践案例，能基于客户业务场景定制高可用优化、云上护航、容量规划、架构优化、容灾建设、成本评估及优化等优化方案，针对性识别客户风险，并有效落地方案 • 具备云原生、大数据、数据库、网络、中间件等领域中的一项或多项技术理解和应用经验。 • 掌握所支持业务线主要产品的底层架构 • 掌握所支持业务线的专业技术能力 • 掌握跨产品的系统架构，能基于此做方案设计或问题排查 • 对客户业务阶段和痛点有洞见，在交付与售后服务过程中识别客户需求，并紧密跟踪和推进与客户中高层的关键对话，形成商机 • 洞察、理解客户商机和需求，整合阿里云现有产品和服务方案，提供有竞争力的解决方案，促进客户复购或扩展合作范围。, education=本科, url=https://careers.aliyun.com/off-campus/position-detail?positionId=100000183002, experience=10年以上 |
| 4660 | aliyun | 2008903001 | 阿里云 | 阿里云智能-云迁移与专有云交付专家-迁移专家组 | 北京, 杭州, 上海 | salary | requirements=● 本科以上计算机及相关专业学历 ● 10 年以上工作经验，5年以上云计算相关交付工作经验 ● 具备良好的英语听说读写能力，英语可作为工作语言 ● 对AWS、Azure、GCP的主流公共云产品能力有深入了解，熟悉容器、消息中间件、大数据、搜索、AI 等云产品，掌握典型场景的技术架构方案特别是云迁移方案，具备重大项目架构设计/优化、产品部署测试、技术问题处理能力。 ● 对私有云架构有一定经验、擅长网络规划、网络安全、OS 管理等方面 IaaS技能。 ● 熟悉Java, Python, Go或其他主流语言，有云计算厂商 OpenAPI 的开发经验，有 AI项目交付经验 ● 能高质量完成面向客户中高层的方案汇报，影响客户技术和方案选型。 ● 3 年以上团队管理经验，熟悉团队绩效管理、团队激励、技术团队人员能力发展等 ● 有良好的沟通协调能力，能够与各个产品团队紧密合作，有过横向项目支持经验的优先 ● 国际化视野：对国际云厂商、行业生态的发展趋势有思考和理解，通过客户需求推动阿里云能力提升，打造阿里云行业竞争壁垒；能与来自不同国家和文化背景的团队工作协同，推动项目拿到结果，可以带领多元文化团队作战攻坚并拿到结果。, education=本科, url=https://careers.aliyun.com/off-campus/position-detail?positionId=2008903001, experience=10年以上 |
| 18504 | baidu | 7fe46777-234a-4956-a5dd-98c5ec02e493 | 百度 | 经营分析师（J101391） | 北京市 | experience, education, salary | requirements=-有模型产品相关数据分析、商业分析，或模型成本优化工作经验优先，3年以上数据分析经验 -基本功扎实，熟练使用MySQL、python、EXCEL、Power BI、Tableau等分析工具，具备大数据获取和分析经验 -熟练独立编写商业数据分析报告，及时发现和分析其中隐含的变化和问题，具备良好的商业敏感度和创新意识，快速识别商业问题和机会 -数据敏感度强，逻辑思维能力出色，学习能力及商业理解能力强，有足够的自驱力，良好的跨团队沟通合作能力，能够协调资源，推动解决问题 -本科及以上学历，数据、统计、经济、商业分析等相关专业优先 -严谨细致，综合能力强，责任心强，有owner意识，具备较强的执行力和抗压力, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/7fe46777-234a-4956-a5dd-98c5ec02e493, experience= |
| 18505 | baidu | 91fc2cef-4b6d-4127-b9cb-2e1266b9670f | 百度 | 公有云销售经理（J101343） | 北京市 | experience, education, salary | requirements=-经验要求：2年以上To B销售经验，有云计算/AI行业销售经验者优先 -行业认知：对云计算有基本理解，对大模型/AI应用趋势有敏感度和学习意愿 -客户能力：具备政企客户开发经验，能独立完成从客户触达、需求挖掘、方案讲解到商务谈判的全流程 -执行力：目标导向，抗压能力强，能适应高频客户拜访和快节奏的业务推进 -协同意识：具备跨团队协作意识，能高效配合解决方案、产研、交付等团队推动项目落地, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/91fc2cef-4b6d-4127-b9cb-2e1266b9670f, experience= |
| 6854 | bytedance | 7657467065993218309 | 字节跳动 | 用户增长产品运营（智能投放方向）-TikTok | 北京 | experience, education, salary | requirements=1、本科及以上学历，具备产品运营、商业化产品、广告产品运营或相关领域工作经验； 2、对广告投放/智能投放/AI投放有较强兴趣，能快速建立产品能力与业务价值之间的连接； 3、具备较强的结构化思考和需求抽象能力，能从零散反馈中识别问题本质和产品机会； 4、具备优秀的沟通表达与跨团队协作能力，能在产品、业务、运营及外部合作方之间高效推动项目进展。, education=, url=https://jobs.bytedance.com/experienced/position/7657467065993218309/detail, experience= |
| 6855 | bytedance | 7651892495110850821 | 字节跳动 | 推荐策略产品经理（用户增长）-TikTok | 北京 | experience, education, salary | requirements=1、本科及以上学历，丰富的互联网产品经验，有流量推荐策略、内容推荐策略经验者优先； 2、深入理解推荐机制流程以及算法基本原理，和推荐算法团队协作，完成策略效果验证与迭代； 3、具备较强的数据分析能力，能通过数据发现问题、验证假设并推动产品决策； 4、逻辑清晰、自驱力强，具备良好的跨团队沟通和项目推进能力。, education=, url=https://jobs.bytedance.com/experienced/position/7651892495110850821/detail, experience= |
| 5859 | didi | JR2026062600M | 滴滴 | 商家营销产品运营 | 上海市 | experience, education, salary | requirements=- 3年以上互联网产品运营、商家营销工具运营相关经验，有本地生活/电商相关商家营销工具运营经验者优先 - 具备较强的商家视角、数据分析能力和产品运营能力，能够将商家反馈和业务问题转化为清晰的产品优化需求 - 具备良好的跨团队协同和项目推动能力，能够协同产品、算法、研发、BD和区域运营等团队解决复杂问题 - 英语可作为工作语言，有海外业务或拉美市场经验者优先, education=, url=https://talent.didiglobal.com/social/p/64826, experience= |
| 5860 | didi | JR2026070600J | 滴滴 | 大客户销售经理 | 上海市 | experience, education, salary | requirements=1、统招本科及以上学历优先（优秀人才可放低标准），拥有5年以上To B大客户销售经验，有商旅、企业管理软件、SaaS类产品及系统服务解决方案行业销售经验者优先； 2、具有项目管控经验，能够独立为客户定制方案，并通过客户需求的不断挖掘积极改进销售策略； 3、具备良好的沟通和表达能力，掌握一定的顾问式营销方法与技能，能够通过有效地演讲和谈判呈现公司产品和服务，赢得客户的认可并与客户保持长期友好的合作关系； 4、熟练操作office办公软件，擅长PPT方案制作。 5、热爱销售工作，具备快速学习能力；有良好的团队合作意识、较强的抗压性；自我有较高的要求，追求卓越，愿意不断投入来提升自己的能力和专业度。, education=, url=https://talent.didiglobal.com/social/p/65010, experience= |
| 5195 | dingtalk | 100021400009 | 钉钉 | 悟空事业部-Agent安全-北上杭 | 杭州 | department, salary | requirements=1、相信 Agent 会重塑安全领域，具备好奇心、快速学习能力与独立解决问题的韧性； 2、对安全有热情和兴趣，计算机基础与 Agent 能力扎实； 3、业务理解力强，能识别关键痛点并将 AI 能力映射到业务场景，形成可评估、可迭代的方案； 4、有 LLM/Agent 应用落地经验优先；对 LLM/Agent 架构及其攻击面有理解者优先。, education=本科, url=https://talent.dingtalk.com/off-campus/position-detail?positionId=100021400009, experience=2年以上 |
| 5196 | dingtalk | 100018420012 | 钉钉 | 悟空事业部-AI Infra研发高级工程师/专家-悟空 | 杭州 | department, salary | requirements=● 计算机相关专业本科及以上学历，3年以上后端开发或AI应用工程化相关工作经验； ● 精通Python/Go中至少一门语言，具备扎实的软件工程能力和良好的代码规范，熟悉异步编程模型； ● 深入理解大语言模型的工作原理和能力边界，有LangChain、LlamaIndex、Semantic Kernel等Agent框架的实际项目经验； ● 熟悉向量数据库（Milvus/Pinecone/Chroma等）和检索增强生成（RAG）技术，有大规模向量检索系统经验者优先； ● 熟悉工作流引擎（如Airflow、Prefect、Temporal等）或状态机设计，有复杂业务流程编排经验者优先； ● 了解主流LLM API（OpenAI、Anthropic、通义千问等）的调用模式和最佳实践，有Prompt优化和成本控制经验者优先； ● 具备良好的系统设计和问题定位能力，有高并发、高可用分布式系统开发经验者优先； ● 强烈的责任心和团队协作精神，对AI技术有热情，能够快速学习新技术并应用于实际业务场景。, education=本科, url=https://talent.dingtalk.com/off-campus/position-detail?positionId=100018420012, experience=2年以上 |
| 5297 | feishu | 7658219588165699849 | MiniMax | AI 招聘专家 - 基座模型技术方向 | 北京, 上海 | department, experience, education, salary | requirements=1、学历与经验背景： 本科及以上学历（计算机、人工智能、人力资源等相关专业优先），3年以上互联网大厂、硬科技或顶级 AI 独角兽高端技术招聘（高招）经验；具备基座模型、AGI 赛道或海外技术人才寻访经验者优先。 2、技术理解力与海外寻访能力： 对 AI 基础大模型、AI Infra（基础设施）有基本的行业认知，能够读懂技术人才的学术论文背景/开源项目贡献；具备优秀的英语沟通能力（或海外留学/工作背景），能够流畅对接全球多元化背景的候选人。3、具备卓越的沟通协调能力和复杂问题解决能力，拥有较高的人际敏感度与雇主品牌影响力，能与顶尖科学家、技术专家建立平等且深度的对话。 4、自驱力与抗压： 热爱招聘工作，具备极强的自我驱动力、结果导向意识和抗压能力，乐于在高动态、高挑战的 AGI 变革期接受挑战。 5、接受具备硬核技术寻访能力的乙方（顶级猎头公司 AI/高科技方向）转甲方招聘背景。, education=, url=https://vrfi1sk8a0.jobs.feishu.cn/index/position/7658219588165699849/detail, experience= |
| 5298 | feishu | 7657846537234139442 | MiniMax | 云资源 FinOps 技术专家 | 北京, 上海 | department, experience, education, salary | requirements=1. 5 年以上云成本 / FinOps / 资源运营经验，有**多云（阿里云 / 腾讯云等）**成本优化的一线实战。 2. 精通云计费模型、成本分摊、预留 / 节省计划 / 竞价、用量分析；扎实的数据分析能力（SQL / BI / 脚本）。 3. 懂基础设施资源（计算 / 存储 / 网络 / GPU）的成本结构与优化手段。 4. coding / 自动化能力（Python 等）——能造成本分析 / 治理工具，不是纯 Excel。 5. 强跨团队协同与价值表达：能以"帮你省钱"的服务姿态推动降本，把成本合理性讲清楚。  加分 FinOps 相关认证；GPU 算力成本优化经验；成本 / 用量平台建设；相关开源贡献。, education=, url=https://vrfi1sk8a0.jobs.feishu.cn/index/position/7657846537234139442/detail, experience= |
| 23929 | jd | 220268 | 京东 | 自动驾驶仿真测试工程师 | 北京市 | experience, education, salary | requirements=1、大学本科及以上学历，电子、通信、计算机、机器人等相关专业； 2、熟悉ubuntu系统和python/C++语言，能编写测试代码和测试工具，有HIL上机位工具软件开发经测试验优先； 3、精通至少一种主流自动驾驶仿真软件，如VTD、CarMaker、Prescan、Carla、Simulink、SUMO等 4、具备较好的逻辑思维、较好的沟通与表达能力，做事细致严谨，强烈的责任心和敬业精神，能吃苦耐劳； 5、3年以上工作经验，了解车辆原理，熟悉自动驾驶测试方法和仿真评测体系；  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=220268, experience= |
| 23930 | jd | 214419 | 京东 | 系统方案 | 北京市 | experience, education, salary | requirements=职位描述： 负责供应链业务的系统标准化、配置化建设，通过市场调研推进系统产品化，缩短项目导入周期； 负责面向客群提供制定系统解决方案，输出行业系统能力建设文档，统筹产研资源落地交付； 统筹UAT测试用例编写及计划确认，组织协调测试，输出测试报告并跟进功能上线运营； 负责新增功能的系统操作文档梳理、培训及上线初期仓运配系统支持； 承接复杂供应链项目落地，及时识别风险并推动解决。 岗位要求： 计算机、物流等相关专业，统招本科及以上学历； 5年以上OMS/WMS/TMS系统规划、实施或产品经理经验； 具备：项目交付应经验，具有一定ERP实施经验，熟练运用实施方法论技能。 熟悉系统实施流程，具备全流程项目管理能力，能独立承接并推进项目；具备：【PMP】证书优先， 性格开朗，具备良好的沟通与表达能力； 能输出高质量的BRD需求文档 符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=214419, experience= |
| 21674 | kuaishou | 28301 | 快手 | 本地推投放产品专家（商业策略）-【生活服务】 | 北京 | education, salary | requirements=1、本科及以上学历，3-5年产品工作经验，有广告投放经验、智能化策略经验或本地生活相关行业经验优先； 2、对本地行业有一定了解，能独立完善需求调研、数据分析、产品设计工作，具备项目管理能力； 3、具备敏锐的商业洞察力、较强自驱力、较强的数据分析能力、较好的思维逻辑能力，有独立分析和解决问题的能力； 4、有较强的沟通能力和理解能力，工作细致有耐心，沟通清晰有重点，喜欢挑战，追求极致，有良好的自我管理能力。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/28301, experience=3-5年 |
| 21675 | kuaishou | 28180 | 快手 | 策略产品专家（本地推）-【生活服务】 | 北京 | education, salary | requirements=1、本科及以上学历，3-5年产品工作经验，有广告投放经验、智能化策略、字节和美团等本地生活相关行业经验优先； 2、对本地行业有一定了解，能独立完善需求调研、数据分析、产品设计工作，具备项目管理能力； 3、具备敏锐的商业洞察力、较强自驱力、较强的数据分析能力、较好的思维逻辑能力，有独立分析和解决问题的能力； 4、有较强的沟通能力和理解能力，工作细致有耐心，沟通清晰有重点，喜欢挑战，追求极致，有良好的自我管理能力。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/28180, experience=3-5年 |
| 20004 | meituan | 3583256658 | 美团 | 下沉市场 - 履约策略运营 | 北京市 | education, salary | requirements=1.有丰富物流或零售运营经验，在O2O、互联网电商等相关行业，独立负责过复杂业务的供给运营或策略运营，并有成功案例； 2.数据提取、处理及分析方面具备成熟的工作经验及专业能力，具备独立撰写报告能力 3.有较好的推动落地能力和团队协同能力 3.工作责任心强，自驱力强，善于模式创新并有创新落地能力。, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=3583256658&highlightType=social, experience=3年 |
| 20005 | meituan | 3585587425 | 美团 | 下沉市场 - 履约策略运营专家 | 北京市 | education, salary | requirements=1、3年以上即时配送/本地生活行业骑手运营或活动运营经验，深刻理解下沉市场运营逻辑 2、出色的数据分析与问题诊断能力，熟悉SQL或主流BI工具优先 3、强大的策略规划与落地执行能力，有骑手招募、留存激励等完整操盘经验 4、敏锐的市场洞察与商业敏感度，能快速识别运营机会和风险 5、优秀的沟通协调与跨部门影响力 6、扎实的项目管理能力，能同时推进多个活动项目 7、具备AI工具实际应用经验，能将AI融入日常工作提升效率。有参与AI体系建设或AI辅助运营工具搭建经验优先, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=3585587425&highlightType=social, experience=1年 |
| 1924 | netease | 77326 | 网易 | UGC游戏平台开发工程师 | 杭州市 | salary | requirements=1、本科及以上学历，计算机相关专业，1-3年游戏或相关领域开发经验； 2、良好的代码风格和编程习惯，熟悉至少一门主流语言（C++/Python/Lua/TypeScript等）； 3、熟练掌握常用的数据结构和算法，熟悉游戏相关的3D知识； 4、熟悉AI/LLM/Agent工作流，有实际AI Agent框架搭建、工作流编排评估经验者优先； 5、了解游戏GamePlay开发，有Roblox、MC等UGC平台游戏开发经验者优先。, education=不限, url=https://hr.163.com/job-detail.html?id=77326, experience=不限 |
| 1925 | netease | 77228 | 网易 | GL | 杭州市 | salary | requirements=1. 本科及以上学历，会计、财经或审计学相关专业；  2. 熟悉中美及国际会计准则，5年及以上财务相关工作经验；  3. 独立思考，具有较好的逻辑能力、判断力和沟通表达能力； 4. 乐观、开放、自驱力强，能承受工作压力，工作态度严谨、细致，协作意识强。, education=本科, url=https://hr.163.com/job-detail.html?id=77228, experience=5-10年 |
| 4329 | quark | 100009140004 | 夸克 | 千问事业部-AI高级前端研发工程师（智能创作）-广州 | 广州 | department, salary | requirements=1、精通前端基础技术，熟悉浏览器渲染&原理，具有良好的网络、数据结构、算法基础及软件编程能力； 2、熟练运用 React/Vue 框架以及NodeJS，深入理解其设计原理，并对其配套研发框架或最佳实践有一定了解； 3、熟悉常用设计模式，熟悉前端的模块化、编译和构建工具，熟练使用Webpack/Vite等工具，对前端的工程架构有理解和实践； 4、在Web音视频、前端性能体验优化、复杂单页前端架构、跨端技术，有相应的项目实践或开源项目经验则更佳； 5、有AI Native应用开发经验者优先，有深度AI Coding实践或者基建者优先。, education=本科, url=https://talent.quark.cn/off-campus/position-detail?positionId=100009140004, experience=1年以上 |
| 4330 | quark | 100006820010 | 夸克 | 千问事业部-交付管理专家-深圳/上海/杭州 | 深圳, 杭州, 上海 | department, salary | requirements=1、本科及以上学历，电子，机电，机械及管理类相关专业背景； 2、5年以上行业采购与交付管理工作经验； 3、有责任心，具备较强的抗压能力和团队合作精神； 4、有完成项目并取得财务成果经验，有建立团队或带团队进行流程或者项目改善的经验。, education=本科, url=https://talent.quark.cn/off-campus/position-detail?positionId=100006820010, experience=5年以上 |
| 1 | tencent | 2034611270900154368 | 腾讯 | 腾讯云-MaaS高级后台研发工程师 | 深圳 | education, salary | requirements=1.本科及以上学历，计算机、软件工程、人工智能等相关专业，3 年及以上云原生/AI工程化研发经验； 2.精通至少一种主流语言（Golang/Java/Python），具备扎实的数据结构、算法、操作系统、网络基础，有高并发分布式系统实践优先； 3.熟悉云原生技术栈：K8s、Docker、微服务、RPC/HTTP、消息队列、数据库、缓存，有云厂商或中间件研发经验优先； 4.了解大模型全流程：训练、微调、RAG、推理引擎、量化、蒸馏、向量数据库等，有MaaS/LLM Inference服务开发经验优先； 5.熟悉AI Infra：GPU使用与优化、异构算力纳管、分布式任务调度、性能压测与调优，有大规模模型服务上线运维经验优先； 6.具备良好的系统设计、问题定位与跨团队协作能力，能独立负责复杂模块 / 系统，执行力强； 7.对AGI与MaaS有强烈热情，学习能力强，关注混元、DeepSeek 等主流模型及行业竞品，愿意长期深耕 AI 工程化领域； 8.有AI 安全合规、内容审核、企业级私有化交付、金融/政务等高安全要求场景经验者优先。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2034611270900154368, experience=三年以上工作经验 |
| 2 | tencent | 2067104290106945536 | 腾讯 | 光子 AI-大语言模型Coding算法专家 | 深圳 | education, salary | requirements=1.硕士及以上学历，优秀的代码能力、精通常用数据结构和算法； 2.扎实的深度学习算法基础，熟悉深度学习框架和分布式训练推理加速； 3.出色的问题分析和解决能力，能深入解决大模型训练和应用存在的问题； 4.责任心强，良好的业务意识，团队合作能力和沟通协调能力。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2067104290106945536, experience=五年以上工作经验 |
| 5122 | tongyi | 100007700004 | 通义实验室 | Token Foundry-算法专家-多语言同传大模型 | 北京, 杭州 | department, salary | requirements=1. 研究生以上学历，熟悉Pytorch、Tensorflow等至少一种深度学习框架； 2. 熟悉机器学习，有语音语言方向研究经历。实际参与过大模型预训练、微调、偏好对齐中至少一项，熟悉相关流程； 3.良好的技术洞察力和优秀的业务分析能力，能应对多样的业务算法需求。乐于合作，能够与工程、产品等团队协同。对大模型应用、AGI有很强的技术热情。 4.良好的科研能力，在所在领域有高影响力的技术成果和沉淀优先（如论文、开源项目等）优先； 5.有多语言多模态大模型技术背景优先。, education=硕士, url=https://careers-tongyi.alibaba.com/off-campus/position-detail?positionId=100007700004, experience=3年以上 |
| 5123 | tongyi | 100011240003 | 通义实验室 | AI创新事业部-世界模型算法专家/高级专家 (World Model)-未来生活实验室 | 北京, 杭州 | department, salary | requirements=1.  计算机、人工智能、自动化等相关专业。 2.  在多模态大模型和生成式模型（扩散/自回归模型）上有资深背景，对前沿进展和领域问题有深入理解。 3. 具有主流大模型的实战经验 (视频生成/VLM/LLM/LMM)，有国际高影响力的项目成果。 4.  对 AGI 有极强的热情，能够从第一性原理出发解决世界模型领域问题。, education=硕士, url=https://careers-tongyi.alibaba.com/off-campus/position-detail?positionId=100011240003, experience=3年以上 |
| 23085 | xiaohongshu | 18866 | 小红书 | 电商数据科学-智能供给 | 北京市，上海市 | experience, education, salary | requirements=1. 本科及以上学历，计算机、统计学、数学、数据科学或相关专业； 2. 2年以上数据科学或机器学习相关工作经验； 3. 有电商平台数据科学实战经验，熟悉选品、供给、商家成长或营销等核心场景； 4. 扎实的机器学习与统计学基础，熟练掌握SQL、Python/R，具备独立建模与模型调优能力； 5. 具备良好的业务理解能力，能将业务问题拆解为数据科学问题并推动落地； 6. 善于沟通，工作积极主动，具备强烈的好奇心与自我驱动力。, education=, url=https://job.xiaohongshu.com/social/position/18866, experience= |
| 23086 | xiaohongshu | 15733 | 小红书 | PE工程师-客户端基础技术 | 北京市，上海市 | experience, education, salary | requirements=【任职资格】 1、计算机/统计学/数学等相关专业统招本科以上学历，具有客户端基建/AI agent/APM系统开发/技术类数据分析等经验者优先； 2、在相关领域深耕3年以上，具备较完善的能力体系，能独立负责复杂模块的迭代演进； 3、熟练使用Java/OC/Swift/SQL/Python等开发或数据分析工具； 4、对数据敏感，逻辑严谨，并具备较强的学习能力、沟通能力，能够迅速理解业务需求、找到问题根因； 5、已经将各种 AI 产品充分融入你的工作流，致力于把自己从规则明确且重复的工作任务中释放出来，“一人成军”并产出真正的成果与影响力。  加分项： 1、熟悉Linux环境，理解网络、操作系统、分布式系统、数据结构与算法、JVM等核心原理； 2、熟悉 Kafka，Flink，Clickhouse 等技术，熟悉常见的数据库和缓存技术，如 MySQL、PostgreSQL、Redis； 3、熟悉常见的APP性能优化解决方案，有大型互联网应用性能优化经验； 4、有人工智能端侧部署经验者。, education=, url=https://job.xiaohongshu.com/social/position/15733, experience= |

## description_too_short（15）

| 行号 | platform | job_id | company | title | location | 详情 |
| ---: | --- | --- | --- | --- | --- | --- |
| 5534 | feishu | 7593245670041471238 | 智谱AI | AI产品实习生-上海 | 上海 | requirements=-, education=, url=https://zhipu-ai.jobs.feishu.cn/index/position/7593245670041471238/detail, experience=, length=2 |
| 5618 | feishu | 7527184302761855282 | 智谱AI | 产品测试 | 北京 | requirements=测试测试, education=, url=https://zhipu-ai.jobs.feishu.cn/index/position/7527184302761855282/detail, experience=, length=8 |
| 24087 | jd | 217522 | 京东 | 人才储备岗 | 北京市 | requirements=人才储备  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=217522, experience=, length=38 |
| 24322 | jd | 219062 | 京东 | 关务运营岗 | 北京市 | requirements=关务运营  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=219062, experience=, length=38 |
| 2725 | netease | 76904 | 网易 | 资深/高级游戏营销策划--燕云十六声 | 杭州市 | requirements=1, education=不限, url=https://hr.163.com/job-detail.html?id=76904, experience=不限, length=2 |
| 2907 | netease | 68165 | 网易 | 广州程序类岗位专项 | 广州市 | requirements=服务器开发/客户端开发等, education=不限, url=https://hr.163.com/job-detail.html?id=68165, experience=3-5年, length=24 |
| 23333 | xiaohongshu | 18147 | 小红书 | 电商运营高阶 | 上海市 | requirements=/, education=, url=https://job.xiaohongshu.com/social/position/18147, experience=, length=2 |
| 23345 | xiaohongshu | 18479 | 小红书 | 社区推荐策略产品经理 | 北京市，上海市 | requirements=推荐策略, education=, url=https://job.xiaohongshu.com/social/position/18479, experience=, length=8 |

## description_and_requirements_empty（2）

| 行号 | platform | job_id | company | title | location | 详情 |
| ---: | --- | --- | --- | --- | --- | --- |
| 5730 | feishu | 7656749825794476315 | 商汤科技 | 大模型算法实习生-金融方向 | 北京, 深圳, 上海 | requirements= , education=, url=https://sensetime.jobs.feishu.cn/index/position/7656749825794476315/detail, experience= |
| 5782 | feishu | 7647817236132481331 | 商汤科技 | 大模型算法实习生-数据生产与文档解析 | 深圳 | requirements=, education=, url=https://sensetime.jobs.feishu.cn/index/position/7647817236132481331/detail, experience= |

## invalid_or_missing_url（0）

无样例。

## unparseable_education（21874）

| 行号 | platform | job_id | company | title | location | 详情 |
| ---: | --- | --- | --- | --- | --- | --- |
| 18504 | baidu | 7fe46777-234a-4956-a5dd-98c5ec02e493 | 百度 | 经营分析师（J101391） | 北京市 | requirements=-有模型产品相关数据分析、商业分析，或模型成本优化工作经验优先，3年以上数据分析经验 -基本功扎实，熟练使用MySQL、python、EXCEL、Power BI、Tableau等分析工具，具备大数据获取和分析经验 -熟练独立编写商业数据分析报告，及时发现和分析其中隐含的变化和问题，具备良好的商业敏感度和创新意识，快速识别商业问题和机会 -数据敏感度强，逻辑思维能力出色，学习能力及商业理解能力强，有足够的自驱力，良好的跨团队沟通合作能力，能够协调资源，推动解决问题 -本科及以上学历，数据、统计、经济、商业分析等相关专业优先 -严谨细致，综合能力强，责任心强，有owner意识，具备较强的执行力和抗压力, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/7fe46777-234a-4956-a5dd-98c5ec02e493, experience= |
| 18505 | baidu | 91fc2cef-4b6d-4127-b9cb-2e1266b9670f | 百度 | 公有云销售经理（J101343） | 北京市 | requirements=-经验要求：2年以上To B销售经验，有云计算/AI行业销售经验者优先 -行业认知：对云计算有基本理解，对大模型/AI应用趋势有敏感度和学习意愿 -客户能力：具备政企客户开发经验，能独立完成从客户触达、需求挖掘、方案讲解到商务谈判的全流程 -执行力：目标导向，抗压能力强，能适应高频客户拜访和快节奏的业务推进 -协同意识：具备跨团队协作意识，能高效配合解决方案、产研、交付等团队推动项目落地, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/91fc2cef-4b6d-4127-b9cb-2e1266b9670f, experience= |
| 6854 | bytedance | 7657467065993218309 | 字节跳动 | 用户增长产品运营（智能投放方向）-TikTok | 北京 | requirements=1、本科及以上学历，具备产品运营、商业化产品、广告产品运营或相关领域工作经验； 2、对广告投放/智能投放/AI投放有较强兴趣，能快速建立产品能力与业务价值之间的连接； 3、具备较强的结构化思考和需求抽象能力，能从零散反馈中识别问题本质和产品机会； 4、具备优秀的沟通表达与跨团队协作能力，能在产品、业务、运营及外部合作方之间高效推动项目进展。, education=, url=https://jobs.bytedance.com/experienced/position/7657467065993218309/detail, experience= |
| 6855 | bytedance | 7651892495110850821 | 字节跳动 | 推荐策略产品经理（用户增长）-TikTok | 北京 | requirements=1、本科及以上学历，丰富的互联网产品经验，有流量推荐策略、内容推荐策略经验者优先； 2、深入理解推荐机制流程以及算法基本原理，和推荐算法团队协作，完成策略效果验证与迭代； 3、具备较强的数据分析能力，能通过数据发现问题、验证假设并推动产品决策； 4、逻辑清晰、自驱力强，具备良好的跨团队沟通和项目推进能力。, education=, url=https://jobs.bytedance.com/experienced/position/7651892495110850821/detail, experience= |
| 5859 | didi | JR2026062600M | 滴滴 | 商家营销产品运营 | 上海市 | requirements=- 3年以上互联网产品运营、商家营销工具运营相关经验，有本地生活/电商相关商家营销工具运营经验者优先 - 具备较强的商家视角、数据分析能力和产品运营能力，能够将商家反馈和业务问题转化为清晰的产品优化需求 - 具备良好的跨团队协同和项目推动能力，能够协同产品、算法、研发、BD和区域运营等团队解决复杂问题 - 英语可作为工作语言，有海外业务或拉美市场经验者优先, education=, url=https://talent.didiglobal.com/social/p/64826, experience= |
| 5860 | didi | JR2026070600J | 滴滴 | 大客户销售经理 | 上海市 | requirements=1、统招本科及以上学历优先（优秀人才可放低标准），拥有5年以上To B大客户销售经验，有商旅、企业管理软件、SaaS类产品及系统服务解决方案行业销售经验者优先； 2、具有项目管控经验，能够独立为客户定制方案，并通过客户需求的不断挖掘积极改进销售策略； 3、具备良好的沟通和表达能力，掌握一定的顾问式营销方法与技能，能够通过有效地演讲和谈判呈现公司产品和服务，赢得客户的认可并与客户保持长期友好的合作关系； 4、熟练操作office办公软件，擅长PPT方案制作。 5、热爱销售工作，具备快速学习能力；有良好的团队合作意识、较强的抗压性；自我有较高的要求，追求卓越，愿意不断投入来提升自己的能力和专业度。, education=, url=https://talent.didiglobal.com/social/p/65010, experience= |
| 5297 | feishu | 7658219588165699849 | MiniMax | AI 招聘专家 - 基座模型技术方向 | 北京, 上海 | requirements=1、学历与经验背景： 本科及以上学历（计算机、人工智能、人力资源等相关专业优先），3年以上互联网大厂、硬科技或顶级 AI 独角兽高端技术招聘（高招）经验；具备基座模型、AGI 赛道或海外技术人才寻访经验者优先。 2、技术理解力与海外寻访能力： 对 AI 基础大模型、AI Infra（基础设施）有基本的行业认知，能够读懂技术人才的学术论文背景/开源项目贡献；具备优秀的英语沟通能力（或海外留学/工作背景），能够流畅对接全球多元化背景的候选人。3、具备卓越的沟通协调能力和复杂问题解决能力，拥有较高的人际敏感度与雇主品牌影响力，能与顶尖科学家、技术专家建立平等且深度的对话。 4、自驱力与抗压： 热爱招聘工作，具备极强的自我驱动力、结果导向意识和抗压能力，乐于在高动态、高挑战的 AGI 变革期接受挑战。 5、接受具备硬核技术寻访能力的乙方（顶级猎头公司 AI/高科技方向）转甲方招聘背景。, education=, url=https://vrfi1sk8a0.jobs.feishu.cn/index/position/7658219588165699849/detail, experience= |
| 5298 | feishu | 7657846537234139442 | MiniMax | 云资源 FinOps 技术专家 | 北京, 上海 | requirements=1. 5 年以上云成本 / FinOps / 资源运营经验，有**多云（阿里云 / 腾讯云等）**成本优化的一线实战。 2. 精通云计费模型、成本分摊、预留 / 节省计划 / 竞价、用量分析；扎实的数据分析能力（SQL / BI / 脚本）。 3. 懂基础设施资源（计算 / 存储 / 网络 / GPU）的成本结构与优化手段。 4. coding / 自动化能力（Python 等）——能造成本分析 / 治理工具，不是纯 Excel。 5. 强跨团队协同与价值表达：能以"帮你省钱"的服务姿态推动降本，把成本合理性讲清楚。  加分 FinOps 相关认证；GPU 算力成本优化经验；成本 / 用量平台建设；相关开源贡献。, education=, url=https://vrfi1sk8a0.jobs.feishu.cn/index/position/7657846537234139442/detail, experience= |
| 23929 | jd | 220268 | 京东 | 自动驾驶仿真测试工程师 | 北京市 | requirements=1、大学本科及以上学历，电子、通信、计算机、机器人等相关专业； 2、熟悉ubuntu系统和python/C++语言，能编写测试代码和测试工具，有HIL上机位工具软件开发经测试验优先； 3、精通至少一种主流自动驾驶仿真软件，如VTD、CarMaker、Prescan、Carla、Simulink、SUMO等 4、具备较好的逻辑思维、较好的沟通与表达能力，做事细致严谨，强烈的责任心和敬业精神，能吃苦耐劳； 5、3年以上工作经验，了解车辆原理，熟悉自动驾驶测试方法和仿真评测体系；  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=220268, experience= |
| 23930 | jd | 214419 | 京东 | 系统方案 | 北京市 | requirements=职位描述： 负责供应链业务的系统标准化、配置化建设，通过市场调研推进系统产品化，缩短项目导入周期； 负责面向客群提供制定系统解决方案，输出行业系统能力建设文档，统筹产研资源落地交付； 统筹UAT测试用例编写及计划确认，组织协调测试，输出测试报告并跟进功能上线运营； 负责新增功能的系统操作文档梳理、培训及上线初期仓运配系统支持； 承接复杂供应链项目落地，及时识别风险并推动解决。 岗位要求： 计算机、物流等相关专业，统招本科及以上学历； 5年以上OMS/WMS/TMS系统规划、实施或产品经理经验； 具备：项目交付应经验，具有一定ERP实施经验，熟练运用实施方法论技能。 熟悉系统实施流程，具备全流程项目管理能力，能独立承接并推进项目；具备：【PMP】证书优先， 性格开朗，具备良好的沟通与表达能力； 能输出高质量的BRD需求文档 符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=214419, experience= |
| 21674 | kuaishou | 28301 | 快手 | 本地推投放产品专家（商业策略）-【生活服务】 | 北京 | requirements=1、本科及以上学历，3-5年产品工作经验，有广告投放经验、智能化策略经验或本地生活相关行业经验优先； 2、对本地行业有一定了解，能独立完善需求调研、数据分析、产品设计工作，具备项目管理能力； 3、具备敏锐的商业洞察力、较强自驱力、较强的数据分析能力、较好的思维逻辑能力，有独立分析和解决问题的能力； 4、有较强的沟通能力和理解能力，工作细致有耐心，沟通清晰有重点，喜欢挑战，追求极致，有良好的自我管理能力。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/28301, experience=3-5年 |
| 21675 | kuaishou | 28180 | 快手 | 策略产品专家（本地推）-【生活服务】 | 北京 | requirements=1、本科及以上学历，3-5年产品工作经验，有广告投放经验、智能化策略、字节和美团等本地生活相关行业经验优先； 2、对本地行业有一定了解，能独立完善需求调研、数据分析、产品设计工作，具备项目管理能力； 3、具备敏锐的商业洞察力、较强自驱力、较强的数据分析能力、较好的思维逻辑能力，有独立分析和解决问题的能力； 4、有较强的沟通能力和理解能力，工作细致有耐心，沟通清晰有重点，喜欢挑战，追求极致，有良好的自我管理能力。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/28180, experience=3-5年 |
| 20004 | meituan | 3583256658 | 美团 | 下沉市场 - 履约策略运营 | 北京市 | requirements=1.有丰富物流或零售运营经验，在O2O、互联网电商等相关行业，独立负责过复杂业务的供给运营或策略运营，并有成功案例； 2.数据提取、处理及分析方面具备成熟的工作经验及专业能力，具备独立撰写报告能力 3.有较好的推动落地能力和团队协同能力 3.工作责任心强，自驱力强，善于模式创新并有创新落地能力。, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=3583256658&highlightType=social, experience=3年 |
| 20005 | meituan | 3585587425 | 美团 | 下沉市场 - 履约策略运营专家 | 北京市 | requirements=1、3年以上即时配送/本地生活行业骑手运营或活动运营经验，深刻理解下沉市场运营逻辑 2、出色的数据分析与问题诊断能力，熟悉SQL或主流BI工具优先 3、强大的策略规划与落地执行能力，有骑手招募、留存激励等完整操盘经验 4、敏锐的市场洞察与商业敏感度，能快速识别运营机会和风险 5、优秀的沟通协调与跨部门影响力 6、扎实的项目管理能力，能同时推进多个活动项目 7、具备AI工具实际应用经验，能将AI融入日常工作提升效率。有参与AI体系建设或AI辅助运营工具搭建经验优先, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=3585587425&highlightType=social, experience=1年 |
| 2066 | netease | 77302 | 网易 | 资深GUI设计师（无限大） | 杭州市 | requirements=1.有3年以上（近期）移动端游戏项目开发经验，参与设计过多套系统GUI界面设计； 2.有一定手绘能力，能独立产出界面相关的功能图标及相关绘制工作； 3.有一定动效设计能力，协同动效设计师共同完成最终动态表现； 4.有Unity设计开发经验，MMO项目设计经验者优先考虑； 5.对工作认真负责，沟通能力良好，一定抗压能力。, education=其他, url=https://hr.163.com/job-detail.html?id=77302, experience=5-10年 |
| 2631 | netease | 76578 | 网易 | 资深GUI设计师（无限大） | 杭州市 | requirements=1.有3年以上（近期）移动端游戏项目开发经验，参与设计过多套系统GUI界面设计； 2.有一定手绘能力，能独立产出界面相关的功能图标及相关绘制工作； 3.有一定动效设计能力，协同动效设计师共同完成最终动态表现； 4.有Unity设计开发经验，MMO项目设计经验者优先考虑； 5.对工作认真负责，沟通能力良好，一定抗压能力。, education=其他, url=https://hr.163.com/job-detail.html?id=76578, experience=5-10年 |
| 1 | tencent | 2034611270900154368 | 腾讯 | 腾讯云-MaaS高级后台研发工程师 | 深圳 | requirements=1.本科及以上学历，计算机、软件工程、人工智能等相关专业，3 年及以上云原生/AI工程化研发经验； 2.精通至少一种主流语言（Golang/Java/Python），具备扎实的数据结构、算法、操作系统、网络基础，有高并发分布式系统实践优先； 3.熟悉云原生技术栈：K8s、Docker、微服务、RPC/HTTP、消息队列、数据库、缓存，有云厂商或中间件研发经验优先； 4.了解大模型全流程：训练、微调、RAG、推理引擎、量化、蒸馏、向量数据库等，有MaaS/LLM Inference服务开发经验优先； 5.熟悉AI Infra：GPU使用与优化、异构算力纳管、分布式任务调度、性能压测与调优，有大规模模型服务上线运维经验优先； 6.具备良好的系统设计、问题定位与跨团队协作能力，能独立负责复杂模块 / 系统，执行力强； 7.对AGI与MaaS有强烈热情，学习能力强，关注混元、DeepSeek 等主流模型及行业竞品，愿意长期深耕 AI 工程化领域； 8.有AI 安全合规、内容审核、企业级私有化交付、金融/政务等高安全要求场景经验者优先。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2034611270900154368, experience=三年以上工作经验 |
| 2 | tencent | 2067104290106945536 | 腾讯 | 光子 AI-大语言模型Coding算法专家 | 深圳 | requirements=1.硕士及以上学历，优秀的代码能力、精通常用数据结构和算法； 2.扎实的深度学习算法基础，熟悉深度学习框架和分布式训练推理加速； 3.出色的问题分析和解决能力，能深入解决大模型训练和应用存在的问题； 4.责任心强，良好的业务意识，团队合作能力和沟通协调能力。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2067104290106945536, experience=五年以上工作经验 |
| 23085 | xiaohongshu | 18866 | 小红书 | 电商数据科学-智能供给 | 北京市，上海市 | requirements=1. 本科及以上学历，计算机、统计学、数学、数据科学或相关专业； 2. 2年以上数据科学或机器学习相关工作经验； 3. 有电商平台数据科学实战经验，熟悉选品、供给、商家成长或营销等核心场景； 4. 扎实的机器学习与统计学基础，熟练掌握SQL、Python/R，具备独立建模与模型调优能力； 5. 具备良好的业务理解能力，能将业务问题拆解为数据科学问题并推动落地； 6. 善于沟通，工作积极主动，具备强烈的好奇心与自我驱动力。, education=, url=https://job.xiaohongshu.com/social/position/18866, experience= |
| 23086 | xiaohongshu | 15733 | 小红书 | PE工程师-客户端基础技术 | 北京市，上海市 | requirements=【任职资格】 1、计算机/统计学/数学等相关专业统招本科以上学历，具有客户端基建/AI agent/APM系统开发/技术类数据分析等经验者优先； 2、在相关领域深耕3年以上，具备较完善的能力体系，能独立负责复杂模块的迭代演进； 3、熟练使用Java/OC/Swift/SQL/Python等开发或数据分析工具； 4、对数据敏感，逻辑严谨，并具备较强的学习能力、沟通能力，能够迅速理解业务需求、找到问题根因； 5、已经将各种 AI 产品充分融入你的工作流，致力于把自己从规则明确且重复的工作任务中释放出来，“一人成军”并产出真正的成果与影响力。  加分项： 1、熟悉Linux环境，理解网络、操作系统、分布式系统、数据结构与算法、JVM等核心原理； 2、熟悉 Kafka，Flink，Clickhouse 等技术，熟悉常见的数据库和缓存技术，如 MySQL、PostgreSQL、Redis； 3、熟悉常见的APP性能优化解决方案，有大型互联网应用性能优化经验； 4、有人工智能端侧部署经验者。, education=, url=https://job.xiaohongshu.com/social/position/15733, experience= |

## unparseable_experience_years（19360）

| 行号 | platform | job_id | company | title | location | 详情 |
| ---: | --- | --- | --- | --- | --- | --- |
| 4865 | aliyun | 100013803004 | 阿里云 | 诚云科技-IDC运维工程师（资产）-中卫/乌兰察布/呼和浩特/廊坊/桐庐/宁波/嘉兴 | 廊坊, 乌兰察布, 嘉兴, 中卫, 呼和浩特, 杭州, 宁波 | requirements=1、2025届或2026届毕业生，有资产管理经验优先 2、具备良好的学习能力和执行力，能够将公司的资产管理要求准确同步至机房现场； 3、具备良好的管理能力，能够发现业务中的风险点和漏洞，并提出优化建议。, education=本科, url=https://careers.aliyun.com/off-campus/position-detail?positionId=100013803004, experience={'from': None, 'to': 0} |
| 4993 | aliyun | 100004323001 | 阿里云 | 诚云科技-IDC运维工程师（设施）-南京/上海/杭州/北京/中卫/惠州/常熟/平湖 | 北京, 嘉兴, 中卫, 常熟, 杭州, 南京, 上海 | requirements=1、暖通/电气相关专业，有数据中心基础设施运维经验优先； 2、具备良好的学习能力和执行力，快速学习和理解公司的设施管理要求 3、具备良好的问题发现和解决能力，能够发现业务中的风险点和漏洞，并提出优化建议。 4、持续建立并推广标准化的运维体系和流程，降低运维风险，提升运营效率； 5、能够驱动供应商在日常运维过程中提升配合意愿度来达成业务目标；, education=本科, url=https://careers.aliyun.com/off-campus/position-detail?positionId=100004323001, experience={'from': None, 'to': 0} |
| 18504 | baidu | 7fe46777-234a-4956-a5dd-98c5ec02e493 | 百度 | 经营分析师（J101391） | 北京市 | requirements=-有模型产品相关数据分析、商业分析，或模型成本优化工作经验优先，3年以上数据分析经验 -基本功扎实，熟练使用MySQL、python、EXCEL、Power BI、Tableau等分析工具，具备大数据获取和分析经验 -熟练独立编写商业数据分析报告，及时发现和分析其中隐含的变化和问题，具备良好的商业敏感度和创新意识，快速识别商业问题和机会 -数据敏感度强，逻辑思维能力出色，学习能力及商业理解能力强，有足够的自驱力，良好的跨团队沟通合作能力，能够协调资源，推动解决问题 -本科及以上学历，数据、统计、经济、商业分析等相关专业优先 -严谨细致，综合能力强，责任心强，有owner意识，具备较强的执行力和抗压力, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/7fe46777-234a-4956-a5dd-98c5ec02e493, experience= |
| 18505 | baidu | 91fc2cef-4b6d-4127-b9cb-2e1266b9670f | 百度 | 公有云销售经理（J101343） | 北京市 | requirements=-经验要求：2年以上To B销售经验，有云计算/AI行业销售经验者优先 -行业认知：对云计算有基本理解，对大模型/AI应用趋势有敏感度和学习意愿 -客户能力：具备政企客户开发经验，能独立完成从客户触达、需求挖掘、方案讲解到商务谈判的全流程 -执行力：目标导向，抗压能力强，能适应高频客户拜访和快节奏的业务推进 -协同意识：具备跨团队协作意识，能高效配合解决方案、产研、交付等团队推动项目落地, education=, url=https://talent.baidu.com/jobs/detail/SOCIAL/91fc2cef-4b6d-4127-b9cb-2e1266b9670f, experience= |
| 6854 | bytedance | 7657467065993218309 | 字节跳动 | 用户增长产品运营（智能投放方向）-TikTok | 北京 | requirements=1、本科及以上学历，具备产品运营、商业化产品、广告产品运营或相关领域工作经验； 2、对广告投放/智能投放/AI投放有较强兴趣，能快速建立产品能力与业务价值之间的连接； 3、具备较强的结构化思考和需求抽象能力，能从零散反馈中识别问题本质和产品机会； 4、具备优秀的沟通表达与跨团队协作能力，能在产品、业务、运营及外部合作方之间高效推动项目进展。, education=, url=https://jobs.bytedance.com/experienced/position/7657467065993218309/detail, experience= |
| 6855 | bytedance | 7651892495110850821 | 字节跳动 | 推荐策略产品经理（用户增长）-TikTok | 北京 | requirements=1、本科及以上学历，丰富的互联网产品经验，有流量推荐策略、内容推荐策略经验者优先； 2、深入理解推荐机制流程以及算法基本原理，和推荐算法团队协作，完成策略效果验证与迭代； 3、具备较强的数据分析能力，能通过数据发现问题、验证假设并推动产品决策； 4、逻辑清晰、自驱力强，具备良好的跨团队沟通和项目推进能力。, education=, url=https://jobs.bytedance.com/experienced/position/7651892495110850821/detail, experience= |
| 5859 | didi | JR2026062600M | 滴滴 | 商家营销产品运营 | 上海市 | requirements=- 3年以上互联网产品运营、商家营销工具运营相关经验，有本地生活/电商相关商家营销工具运营经验者优先 - 具备较强的商家视角、数据分析能力和产品运营能力，能够将商家反馈和业务问题转化为清晰的产品优化需求 - 具备良好的跨团队协同和项目推动能力，能够协同产品、算法、研发、BD和区域运营等团队解决复杂问题 - 英语可作为工作语言，有海外业务或拉美市场经验者优先, education=, url=https://talent.didiglobal.com/social/p/64826, experience= |
| 5860 | didi | JR2026070600J | 滴滴 | 大客户销售经理 | 上海市 | requirements=1、统招本科及以上学历优先（优秀人才可放低标准），拥有5年以上To B大客户销售经验，有商旅、企业管理软件、SaaS类产品及系统服务解决方案行业销售经验者优先； 2、具有项目管控经验，能够独立为客户定制方案，并通过客户需求的不断挖掘积极改进销售策略； 3、具备良好的沟通和表达能力，掌握一定的顾问式营销方法与技能，能够通过有效地演讲和谈判呈现公司产品和服务，赢得客户的认可并与客户保持长期友好的合作关系； 4、熟练操作office办公软件，擅长PPT方案制作。 5、热爱销售工作，具备快速学习能力；有良好的团队合作意识、较强的抗压性；自我有较高的要求，追求卓越，愿意不断投入来提升自己的能力和专业度。, education=, url=https://talent.didiglobal.com/social/p/65010, experience= |
| 5297 | feishu | 7658219588165699849 | MiniMax | AI 招聘专家 - 基座模型技术方向 | 北京, 上海 | requirements=1、学历与经验背景： 本科及以上学历（计算机、人工智能、人力资源等相关专业优先），3年以上互联网大厂、硬科技或顶级 AI 独角兽高端技术招聘（高招）经验；具备基座模型、AGI 赛道或海外技术人才寻访经验者优先。 2、技术理解力与海外寻访能力： 对 AI 基础大模型、AI Infra（基础设施）有基本的行业认知，能够读懂技术人才的学术论文背景/开源项目贡献；具备优秀的英语沟通能力（或海外留学/工作背景），能够流畅对接全球多元化背景的候选人。3、具备卓越的沟通协调能力和复杂问题解决能力，拥有较高的人际敏感度与雇主品牌影响力，能与顶尖科学家、技术专家建立平等且深度的对话。 4、自驱力与抗压： 热爱招聘工作，具备极强的自我驱动力、结果导向意识和抗压能力，乐于在高动态、高挑战的 AGI 变革期接受挑战。 5、接受具备硬核技术寻访能力的乙方（顶级猎头公司 AI/高科技方向）转甲方招聘背景。, education=, url=https://vrfi1sk8a0.jobs.feishu.cn/index/position/7658219588165699849/detail, experience= |
| 5298 | feishu | 7657846537234139442 | MiniMax | 云资源 FinOps 技术专家 | 北京, 上海 | requirements=1. 5 年以上云成本 / FinOps / 资源运营经验，有**多云（阿里云 / 腾讯云等）**成本优化的一线实战。 2. 精通云计费模型、成本分摊、预留 / 节省计划 / 竞价、用量分析；扎实的数据分析能力（SQL / BI / 脚本）。 3. 懂基础设施资源（计算 / 存储 / 网络 / GPU）的成本结构与优化手段。 4. coding / 自动化能力（Python 等）——能造成本分析 / 治理工具，不是纯 Excel。 5. 强跨团队协同与价值表达：能以"帮你省钱"的服务姿态推动降本，把成本合理性讲清楚。  加分 FinOps 相关认证；GPU 算力成本优化经验；成本 / 用量平台建设；相关开源贡献。, education=, url=https://vrfi1sk8a0.jobs.feishu.cn/index/position/7657846537234139442/detail, experience= |
| 23929 | jd | 220268 | 京东 | 自动驾驶仿真测试工程师 | 北京市 | requirements=1、大学本科及以上学历，电子、通信、计算机、机器人等相关专业； 2、熟悉ubuntu系统和python/C++语言，能编写测试代码和测试工具，有HIL上机位工具软件开发经测试验优先； 3、精通至少一种主流自动驾驶仿真软件，如VTD、CarMaker、Prescan、Carla、Simulink、SUMO等 4、具备较好的逻辑思维、较好的沟通与表达能力，做事细致严谨，强烈的责任心和敬业精神，能吃苦耐劳； 5、3年以上工作经验，了解车辆原理，熟悉自动驾驶测试方法和仿真评测体系；  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=220268, experience= |
| 23930 | jd | 214419 | 京东 | 系统方案 | 北京市 | requirements=职位描述： 负责供应链业务的系统标准化、配置化建设，通过市场调研推进系统产品化，缩短项目导入周期； 负责面向客群提供制定系统解决方案，输出行业系统能力建设文档，统筹产研资源落地交付； 统筹UAT测试用例编写及计划确认，组织协调测试，输出测试报告并跟进功能上线运营； 负责新增功能的系统操作文档梳理、培训及上线初期仓运配系统支持； 承接复杂供应链项目落地，及时识别风险并推动解决。 岗位要求： 计算机、物流等相关专业，统招本科及以上学历； 5年以上OMS/WMS/TMS系统规划、实施或产品经理经验； 具备：项目交付应经验，具有一定ERP实施经验，熟练运用实施方法论技能。 熟悉系统实施流程，具备全流程项目管理能力，能独立承接并推进项目；具备：【PMP】证书优先， 性格开朗，具备良好的沟通与表达能力； 能输出高质量的BRD需求文档 符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, education=, url=https://zhaopin.jd.com/web/job-info-detail?requementId=214419, experience= |
| 21695 | kuaishou | 27294 | 快手 | 商业分析师（渠道策略）-【生活服务】 | 北京 | requirements=1、本科及以上学历，应用数学、统计学等相关专业优先考虑； 2、2年及以上互联网数据分析工作经验，短视频、电商相关行业从业者优先； 3、具备良好的跨部门沟通协作能力，学习能力强，可快速理解并把握业务需求，善于发现问题解决问题； 4、有较强的分析能力，能够独立开展数据分析和建立分析模型； 5、热情，充满好奇心，上进心强，能承受一定的工作压力。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/27294, experience=不限 |
| 21742 | kuaishou | 29348 | 快手 | 产品运营（搜索方向）-【生活服务】 | 北京 | requirements=1、本科及以上学历，3-5年搜索推荐相关运营经验，有生活服务相关工作经验更佳； 2、思维清晰，有良好的数据分析能力，具备较好的跨部门沟通能力和资源协调能力； 3、目标导向，能快速学习，具备较好的抗压能力和细节把控能力。, education=, url=https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/29348, experience=不限 |
| 20010 | meituan | 4566998937 | 美团 | Agent工程师（商业智能） | 北京市,上海市 | requirements=1.计算机、人工智能或相关专业本科及以上学历。 2. 具备大模型或智能体相关工程开发经验，理解 LLM 底层工作机制与 Agent 系统核心组件 3.对主流开源 Agent 框架有源码阅读与使用经验，能从架构层面分析其设计取舍。以下为典型参考（需至少深入过 2-3 个）： 典型框架：Claude Code / Agent SDK、OpenAI Agents SDK / Codex、CrewAI、LangGraph、OpenClaw、Hermes、Dify / Mastra / Nanobot 等 关注机制：Agentic Loop、上下文工程与压缩策略、多 Agent 协作与委托、记忆系统（短期/长期）、闭环自进化能力、Observability / Tracing、Human-in-the-loop 审批机制、Skill 体系与工具编排、状态持久化与断点续跑、Sandbox 安全执行 等 4. 具备良好的逻辑思维与沟通能力，能够独立完成技术方案设计并推动落地。, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=4566998937&highlightType=social, experience=不限 |
| 20012 | meituan | 4556168293 | 美团 | 智能体（Agent）算法工程师 | 北京市 | requirements=（1）有好奇心，敢想敢做，责任心强。  （2）对AI搜索、LLM后训练、Agent决策有深入了解。  （3）有Agent系统或对话系统完整项目经验，能把控技术方案与项目进度。  （4）有OpenClaw/Claude Code/Codex深度使用经验与产出优先。  （5）熟悉Agentic RL、Tool-Use训练、Reward Model设计者优先。  （6）GitHub高Star、AI原生项目或向OpenClaw/OpenCode提交过核心PR者优先。, education=, url=https://zhaopin.meituan.com/web/position/detail?jobUnionId=4556168293&highlightType=social, experience=不限 |
| 1924 | netease | 77326 | 网易 | UGC游戏平台开发工程师 | 杭州市 | requirements=1、本科及以上学历，计算机相关专业，1-3年游戏或相关领域开发经验； 2、良好的代码风格和编程习惯，熟悉至少一门主流语言（C++/Python/Lua/TypeScript等）； 3、熟练掌握常用的数据结构和算法，熟悉游戏相关的3D知识； 4、熟悉AI/LLM/Agent工作流，有实际AI Agent框架搭建、工作流编排评估经验者优先； 5、了解游戏GamePlay开发，有Roblox、MC等UGC平台游戏开发经验者优先。, education=不限, url=https://hr.163.com/job-detail.html?id=77326, experience=不限 |
| 1927 | netease | 74751 | 网易 | AI向美术设计实习生（市场营销方向） | 上海市 | requirements=1.有AI视频制作经验，可以熟练使用可灵、Seedance、VEO 等主流AI视频生成工具，请在作品集中附带相关案例； 2.设计、美术或相关专业在校生，具备扎实的视觉设计基础和良好的审美把控能力； 3.深入了解 SOC（开放世界生存制作）品类 或 微恐射击MMO 等题材，能准确捕捉和还原该品类受众偏好的视觉氛围； 4.思维活跃，具备良好的沟通协调能力和团队协作精神，面对快节奏的营销需求能保持积极的执行力。 加分项： 1.《七日世界》的忠实玩家，对游戏世界观、异常物设计及核心玩法有深刻理解。 2.有成熟的、由AI辅助生成的商业化项目经验或高质量个人作品集, education=不限, url=https://hr.163.com/job-detail.html?id=74751, experience=不限 |
| 34 | tencent | 2034823219160182784 | 腾讯 | 微信小游戏-客户端开发工程师-全球化 | 深圳 | requirements=1.大学本科及以上学历，计算机相关专业，具备扎实的计算机基础，精通算法、数据结构及操作系统原理； 2.3年以上iOS或Android开发经验，精通Objective-C/Swift或Java/Kotlin，有大型SDK开发或跨平台框架（如Flutter, React Native 引擎层）经验者优先； 3.熟练掌握Claude Code、Codex、Codebuddy等AI编程工具与范式； 4.有游戏领域经验更好，熟悉OpenGL ES/WebGL规范，对渲染流水线有理解，有Metal或Vulkan实际开发经验者，或熟悉游戏引擎Cocos, LayaAir, Unity底层原理者优先； 5.具备优秀的分析和解决复杂问题的能力，对新技术充满好奇心；有良好的沟通能力和团队协作精神，能适应小团队快速迭代的节奏，有海外产品研发/性能优化经验者优先。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2034823219160182784, experience=不限 |
| 36 | tencent | 2069251728867504128 | 腾讯 | 微信小游戏-客户端开发工程师-全球化 | 深圳 | requirements=1.大学本科及以上学历，计算机相关专业，具备扎实的计算机基础，精通算法、数据结构及操作系统原理； 2.3年以上iOS或Android开发经验，精通Objective-C/Swift或Java/Kotlin，有大型SDK开发或跨平台框架（如Flutter, React Native 引擎层）经验者优先； 3.熟练掌握Claude Code、Codex、Codebuddy等AI编程工具与范式； 4.有游戏领域经验更好，熟悉OpenGL ES/WebGL规范，对渲染流水线有理解，有Metal或Vulkan实际开发经验者，或熟悉游戏引擎Cocos, LayaAir, Unity底层原理者优先； 5.具备优秀的分析和解决复杂问题的能力，对新技术充满好奇心；有良好的沟通能力和团队协作精神，能适应小团队快速迭代的节奏，有海外产品研发/性能优化经验者优先。, education=, url=http://careers.tencent.com/jobdesc.html?postId=2069251728867504128, experience=不限 |
| 23085 | xiaohongshu | 18866 | 小红书 | 电商数据科学-智能供给 | 北京市，上海市 | requirements=1. 本科及以上学历，计算机、统计学、数学、数据科学或相关专业； 2. 2年以上数据科学或机器学习相关工作经验； 3. 有电商平台数据科学实战经验，熟悉选品、供给、商家成长或营销等核心场景； 4. 扎实的机器学习与统计学基础，熟练掌握SQL、Python/R，具备独立建模与模型调优能力； 5. 具备良好的业务理解能力，能将业务问题拆解为数据科学问题并推动落地； 6. 善于沟通，工作积极主动，具备强烈的好奇心与自我驱动力。, education=, url=https://job.xiaohongshu.com/social/position/18866, experience= |
| 23086 | xiaohongshu | 15733 | 小红书 | PE工程师-客户端基础技术 | 北京市，上海市 | requirements=【任职资格】 1、计算机/统计学/数学等相关专业统招本科以上学历，具有客户端基建/AI agent/APM系统开发/技术类数据分析等经验者优先； 2、在相关领域深耕3年以上，具备较完善的能力体系，能独立负责复杂模块的迭代演进； 3、熟练使用Java/OC/Swift/SQL/Python等开发或数据分析工具； 4、对数据敏感，逻辑严谨，并具备较强的学习能力、沟通能力，能够迅速理解业务需求、找到问题根因； 5、已经将各种 AI 产品充分融入你的工作流，致力于把自己从规则明确且重复的工作任务中释放出来，“一人成军”并产出真正的成果与影响力。  加分项： 1、熟悉Linux环境，理解网络、操作系统、分布式系统、数据结构与算法、JVM等核心原理； 2、熟悉 Kafka，Flink，Clickhouse 等技术，熟悉常见的数据库和缓存技术，如 MySQL、PostgreSQL、Redis； 3、熟悉常见的APP性能优化解决方案，有大型互联网应用性能优化经验； 4、有人工智能端侧部署经验者。, education=, url=https://job.xiaohongshu.com/social/position/15733, experience= |

## unparseable_scraped_at（0）

无样例。

## duplicate_platform_job_id（0）

重复组数：0

无样例。

## suspected_duplicate_company_title_location（441）

重复组数：370

| 重复键 | 出现次数 | 行号 | URL |
| --- | ---: | --- | --- |
| title=微信-ai应用开发工程师, location=广州, company=腾讯, description=1.负责微信后台的基础功能开发，涉及到朋友圈、微信豆、听一听、红包封面等微信基础功能开发； 2.负责微信 ai平台中分布式计算平台、特征生成平台、大模型推理平台等中台功能开发。 | 2 | 30, 1173 | http://careers.tencent.com/jobdesc.html?postId=2040982131504738304<br>http://careers.tencent.com/jobdesc.html?postId=2040982129101406208 |
| title=资深招聘hr-职能, location=杭州市, company=网易, description=1、支持社招工作，根据部门业务规划，完成招聘目标； 2、用互联网产品的思维支持事业部招聘运营工作，通过流程优化、面试官赋能等动作，不断提升招聘的质量与效率； 3、用互联网运营的思维去丰富我们的人才库，支持高端人才的挖猎，根据业务人才战略及部署，定向挖掘特优人才，不断完善人才地图，迅速搭建人才体系以应对市场挑战； 4、分析招聘数据，发现问题，提出自己的想法，并敢于去实践，不畏艰难。 | 2 | 1984, 3405 | https://hr.163.com/job-detail.html?id=76395<br>https://hr.163.com/job-detail.html?id=72696 |
| title=财务bp, location=上海, company=minimax, description=1. 作为业务的财务搭档，深入业务、参与经营会议，输出财务视角的判断与建议 2. 负责所辖业务线月度 p&l 编制、滚动预测与差异分析，驱动业务完成预算目标 3. 搭建业务经济模型，持续监控关键指标健康度 4. 主导业务预算编制与全过程管控，识别资源浪费与降本机会 5. 对业务新项目、新策略、新产品进行事前财务评估（投入产出 / roi / npv / 盈亏平衡），出具立项财务意见 6. 与业务共建关键业务规则（定价、返点、考核口径、激励机制等），确保业务动作与财务结果对齐 7. 向管理层定期输出经营分析报告，揭示风险、捕捉机会、推动改善 | 2 | 5312, 5329 | https://vrfi1sk8a0.jobs.feishu.cn/index/position/7651896987210664246/detail<br>https://vrfi1sk8a0.jobs.feishu.cn/index/position/7646753918701144347/detail |
| title=资深研发工程师, location=北京市, company=滴滴, description=1、参与外卖业务系统的用户营销方向的服务端业务架构设计与开发 2、理解业务和承接需求，主导和实施服务端核心功能开发和性能优化 3、主导和参与业务核心逻辑重构、结合项目研究新技术 | 2 | 5958, 6669 | https://talent.didiglobal.com/social/p/64656<br>https://talent.didiglobal.com/social/p/64346 |
| title=社区产品经理（抖省省）-抖音生活服务, location=北京, company=字节跳动, description=1、社区从0到1建设：主导「抖省省」本地吃喝玩乐内容社区的产品规划与架构设计，从发现美好生活、分享探店避坑的年轻化视角出发，打造高活跃、强种草、有温度的本地生活内容阵地； 2、产品创新与体验打磨：打破传统本地生活产品的工具感，探索图文、短视频、互动组件等多元化内容体裁与创新玩法（如个性化榜单、打卡地图、兴趣圈子等），为年轻用户提供有趣、有用且极致流畅的浏览与互动体验； 3、内容生态与分发策略：具备生态视角，协同运营制定创作者入驻与内容沉淀的产品机制，协同算法团队优化搜推联动策略（“推后搜”、“搜后推”），提升优质内容的分发效率及从“种草”到“到店/交易”的转化渗透率； 4、用户心理与趋势洞察：深入研究新时代及年轻客群在餐饮、休闲娱乐等领域的消费趋势与社交行为模式，将时下热点敏捷转化为产品落地； 5、数据驱动与跨组协同：建立社区健康度与业务漏斗转化指标体系，与运营、内容生态、推荐算法及商业化团队紧密配合，实现社区内容规模与商业变现的双向共赢。 | 2 | 6919, 10995 | https://jobs.bytedance.com/experienced/position/7631808185550096645/detail<br>https://jobs.bytedance.com/experienced/position/7631807594580363525/detail |
| title=databuilder 产品经理（j95916）, location=北京市, company=百度, description=-负责大模型应用数据准备平台整体规划、产品设计与落地运营，围绕数据采集、清洗、标注、治理、特征工程、向量数据构建等核心环节，制定ai 原生数据产品路线图与产品策略 -深度参与数据中台与数据治理体系建设，负责数据标准、元数据管理、数据质量、数据安全、数据权限等产品能力设计，构建面向大模型场景的高质量、高可信、高可用数据底座 -开展市场与用户调研，挖掘业务侧、算法侧、研发侧对大模型数据加工、数据治理、数据服务的真实需求，输出高质量 prd 与产品方案，持续提升数据产品易用性与效率 -协同数据研发、ai 工程、架构、测试、市场、销售等团队，推动数据中台能力、数据治理工具、大模型数据平台的研发落地、联调测试与上线交付 -负责产品上线后数据埋点、效果跟踪与深度数据分析，围绕数据产出效率、数据质量、模型效果等指标持续迭代优化 -配合市场与销售团队，输出产品方案、最佳实践与客户化支撑，推动数据产品与 ai 能力的商业化落地与推广 | 2 | 18510, 18512 | https://talent.baidu.com/jobs/detail/SOCIAL/4cf88973-571c-4dd8-8e17-229eb1bbf7e7<br>https://talent.baidu.com/jobs/detail/SOCIAL/80e86000-3c46-422d-b864-28e8d2fa17cb |
| title=酒类品牌旗舰店运营, location=北京市, company=美团, description=1.负责白酒品牌旗舰店的引入和日常运营工作 2.负责制定所负责品牌旗舰店的销售及推广计划 3.负责迭代品牌旗舰店的运营策略并总结认知 4.负责项目的数据分析和业绩评估，及时调整策略以实现业绩目标 岗位亮点 1.可以获得酒类头部品牌合作机会，提升自身行业资源 2.可以在酒类品牌旗舰店在即时零售场景的运营中展现自己的才华，实现个人职业发展； | 2 | 20072, 20726 | https://zhaopin.meituan.com/web/position/detail?jobUnionId=4585744479&highlightType=social<br>https://zhaopin.meituan.com/web/position/detail?jobUnionId=4344667660&highlightType=social |
| title=结算产品经理-【生活服务】, location=北京, company=快手, description=1、负责生活服务业务交易的账户、计费、分账、结算、发票、保证金、返佣相关能力设计和完善，对结算时效、准确性、安全性负责，对商家、达人、服务商的对账体验负责； 2、通过对业务和产品痛点分析，制定产品具体目标和相应的路径拆解，设计完整闭环的解决方案； 3、对上下游有清晰认知，对接业务及财务，保障数据的一致性和准确性，实现新业务的线上化计费和结算； 4、通过数据分析提炼、客户需求挖掘等手段不断优化产品性能，达成提效降本目标。 | 2 | 21783, 21806 | https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/20837<br>https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/30196 |
| title=跨境物流后端架构师（ai全栈）, location=杭州市，上海市, company=小红书, description=【关于团队与业务】 "中国有好货"——这不仅仅是一句slogan，更是小红书的使命。 redshop（小红书跨境电商）正在将社区"种草"的信任延伸为全球交易闭环，而物流履约是其中至关重要的一环。 作为redshop跨境物流方向的研发poc，你将负责从0到1搭建面向全球多市场的物流履约基础设施。你将直面跨境物流中复杂的链路与规则差异——从仓储、清关、干线、尾程派送到逆向退货，支撑全球用户"买得到、送得到、退得回"的确定性体验。 这里有多物流商接入、路由策略、实时追踪、费用对账等真实的高难度技术命题。我们期待与你一起，用技术打通中国好货出海"最后一公里"。 【岗位职责——你将负责什么？】 - 跨境物流履约体系建设：负责redshop跨境物流系统的设计与研发，包括多物流商路由、运单管理、物流轨迹追踪、时效预估、逆向退货等核心模块，构建稳定高效的物流履约中台。 - 全球多市场物流能力接入：支持不同国家/地区的物流模式落地（国内直发、海外仓一件代发、本地配送等），灵活适配各市场的物流商与合规要求。 - 物流数据与智能化建设：建设物流数据中台，实现物流成本核算、时效大盘、异常预警、履约sla监控等能力，推动物流决策的智能化。 - 逆向物流与售后体验：搭建跨境退货与售后履约链路，解决逆向物流中的时效、成本、报关等难题，提升全球用户的售后体验。 - 跨团队协作与方向牵引：作为物流方向的poc，承担需求沟通、技术方案评审、进度推进、方向规划等工作，牵引团队在物流领域的持续深耕。 | 2 | 23105, 23265 | https://job.xiaohongshu.com/social/position/20014<br>https://job.xiaohongshu.com/social/position/21146 |
| title=机械工程师, location=北京市, company=京东, description=1、负责agv等机器人相关机械选型，机械原理图设计，bom表等图纸资料绘制； 2、负责产品开发、调试、维护，生产、交付等各项软件相关工作和相关文档的撰写； 3、参与现场调试，问题排查，产品改进等产品维护工作； 4、配合软件和硬件工程师完成相关功能调试和测试； 5、售后支持：协助售后部门进行项目售后技术支持。； | 2 | 23962, 24082 | https://zhaopin.jd.com/web/job-info-detail?requementId=218143<br>https://zhaopin.jd.com/web/job-info-detail?requementId=217303 |

## manifest_incomplete_platforms（3）

| platform | complete | status | stopped_by |
| --- | --- | --- | --- |
| aliyun | False | partial | empty_page |
| didi | False | partial | incomplete_list |
| meituan | False | partial | detail_errors |

## manifest_abnormal_stopped_by（4）

| platform | complete | status | stopped_by |
| --- | --- | --- | --- |
| feishu | True | success | all_companies_complete |
| didi | False | partial | incomplete_list |
| bytedance | True | success | all_city_totals_reached |
| meituan | False | partial | detail_errors |
