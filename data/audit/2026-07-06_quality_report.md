# RawJobPosting 数据质量报告

- 生成时间：2026-07-06T14:51:50+08:00
- 输入文件：`data/raw/2026-07-06.json`
- 总岗位数：22907
- 计数口径：缺失字段按缺失字段值计数；重复按同一键中超过首条的额外记录数计数。
- 短描述定义：去除首尾空白后少于 50 个字符。

## 按 platform 统计

| platform | 数量 |
| --- | ---: |
| aliyun | 464 |
| baidu | 1520 |
| bytedance | 9429 |
| didi | 945 |
| dingtalk | 102 |
| feishu | 487 |
| jd | 1295 |
| kuaishou | 1409 |
| meituan | 1673 |
| netease | 2402 |
| quark | 331 |
| tencent | 1943 |
| tongyi | 74 |
| xiaohongshu | 833 |

## 问题汇总

| 问题 | 数量 |
| --- | ---: |
| missing_required_fields | 0 |
| missing_optional_fields | 59973 |
| description_too_short | 20 |
| description_and_requirements_empty | 0 |
| invalid_or_missing_url | 0 |
| duplicate_platform_job_id | 0 |
| suspected_duplicate_company_title_location | 438 |

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

总缺失字段值：59973

| 缺失字段 | 数量 |
| --- | ---: |
| department | 995 |
| experience | 14588 |
| education | 19525 |
| salary | 22907 |
| requirements | 1958 |

### 按平台岗位样例（每个平台 2 条，不足则全部）

| 行号 | platform | job_id | company | title | location | 缺失字段 | 详情 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 4677 | aliyun | 100015483015 | 阿里云 | 阿里云智能-AI Agent 研发专家-Agentic System 研发方向 | 杭州 | salary | requirements=本科及以上学历，计算机、软件工程、人工智能等相关专业； 具备扎实的计算机基础和良好的VibeCoding能力，熟悉 Python / TypeScript / Go / Rust 中至少一种编程语言； 熟悉云原生、微服务、分布式系统、服务治理、CI/CD、观测告警等工程体系； 熟悉大模型应用开发相关技术，理解 Prompt、RAG、Function Calling、Tool Use、Memory、Planning 等核心机制； 具备 Agent 或大模型应用相关项目经验，能够独立完成系统设计、模块开发与问题排查； 具备良好的沟通协作能力和较强的业务理解能力，能够推动复杂项目落地。 |
| 4678 | aliyun | 100011323001 | 阿里云 | 阿里云智能-公共云迁移交付专家-迁移专家组 | 北京, 杭州, 上海 | salary | requirements=• 3年以上技术架构规划和设计落地经验， • 2年以上对应行业大中型企业的售前、研发项目或交付项目经验 • 具备良好的英语听说读写能力，英语可作为工作语言 • 对AWS、Azure、GCP的主流公共云产品能力有深入了解，熟悉容器、消息中间件、大数据、搜索、AI 等云产品，掌握典型场景的技术架构方案特别是云迁移方案，具备重大项目架构设计/优化、产品部署测试、技术问题处理能力。 • 熟悉Java, Python, Go或其他主流语言，有云计算厂商 OpenAPI 的开发经验，有 AI项目交付经验 • 能高质量完成面向客户中高层的方案汇报，影响客户技术和方案选型。 • 掌握跨产品的系统架构，能基于此做方案设计或问题排查 • 有良好的沟通协调能力，能够与各个产品团队紧密合作，有过横向项目支持经验的优先 • 国际化视野：对国际云厂商、行业生态的发展趋势有思考和理解，通过客户需求推动阿里云能力提升，打造阿里云行业竞争壁垒；能与来自不同国家和文化背景的团队工作协同，推动项目拿到结果，可以带领多元文化团队作战攻坚并拿到结果。 |
| 16178 | baidu | 91fc2cef-4b6d-4127-b9cb-2e1266b9670f | 百度 | 公有云销售经理（J101343） | 北京市 | experience, education, salary | requirements=-经验要求：2年以上To B销售经验，有云计算/AI行业销售经验者优先 -行业认知：对云计算有基本理解，对大模型/AI应用趋势有敏感度和学习意愿 -客户能力：具备政企客户开发经验，能独立完成从客户触达、需求挖掘、方案讲解到商务谈判的全流程 -执行力：目标导向，抗压能力强，能适应高频客户拜访和快节奏的业务推进 -协同意识：具备跨团队协作意识，能高效配合解决方案、产研、交付等团队推动项目落地 |
| 16179 | baidu | b286456b-922b-4ff3-9da0-0e8855443ba0 | 百度 | AI应用工程师（J101300） | 北京市 | experience, salary | requirements=-计算机、软件工程、人工智能等相关专业优先 -2年以上软件开发经验，具备扎实的工程开发能力，熟悉Python、Go等至少一种开发语言 -熟悉大模型应用开发，了解提示词工程、Agent架构、向量库、知识库等技术体系 -具备良好的系统集成能力，能够完成API对接、业务流程编排及自动化方案设计 -具备较强的业务理解力，能够将业务需求转化为AI开发方案 -具有AI应用、智能助手、工作流自动化等项目实践经验者优先 |
| 6749 | bytedance | 7655617655998974261 | 字节跳动 | 招聘专家-研发中台（北京） | 北京 | experience, education, salary | requirements=1、本科及以上学历，3年以上招聘经验，有技术岗位招聘经验优先； 2、具备优秀的沟通协调能力和解决问题能力，较高的人际敏感度和影响力； 3、对招聘有浓厚兴趣，有自我驱动力，乐于接受挑战。 |
| 6750 | bytedance | 7646408742993217845 | 字节跳动 | 大模型服务治理工程师-Data AML | 北京 | experience, education, salary | requirements=1、熟练掌握C++，Python，Rust等一门或多门编程语言，编程风格良好，有框架设计和抽象能力； 2、对分布式系统、异构推理有浓厚兴趣，乐于解决问题，擅长用工程化、自动化的方式优化效率问题； 3、有一定的在线业务稳定性、成本治理优化经验； 4、具备良好的团队协作与沟通能力，有较强的责任心。 |
| 5804 | didi | JR2026060100G | 滴滴 | 风险策略分析师 | 上海市 | experience, education, salary | requirements=1、本科及以上学历，统计、金融、数学、计算机优先，有扎实的数理基础； 2、3年及以上消费金融风控策略经验，以及授信及额度管理经验 3、熟练基本的数据分析工具，能够应用R、hive、Python等统计分析软件完成数据的获取和分析； 4、具有良好的逻辑思维能力，优秀的分析解决问题能力，良好的沟通能力，自我驱动力，责任心 |
| 5805 | didi | JR20260602008 | 滴滴 | 资深数据研发工程师 | 北京市 | experience, education, salary | requirements=1、基础功底扎实，熟悉常用的数据结构算法，熟悉 C/C++、Java等一种编程语言，熟悉 Linux 开发环境； 2、熟悉大数据处理、实时处理技术，如Spark、Flink、Kafka，Hive等，具备一定的大数据开发经验； 3、熟悉常见的数据建模方法与特征生产等相关知识，具备较强的业务理解和抽象能力，分析问题解决问题能力； 4、有特征工程、特征平台等相关经验优先； 5、计算机相关专业本科及以上学历，3年及以上工作经验； 6、具备较好的ai应用实践经验优先； |
| 5215 | dingtalk | 100021460003 | 钉钉 | 悟空事业部-客户成功经理-北上广深杭 | 北京, 深圳, 杭州, 广州, 上海 | department, salary | requirements=1. 拥有3年以上大型客户咨询/业务交付与服务经验，或具备技术、产品、业务、项目管理等相关经验，或拥有大型客户BD、解决方案经验；具备咨询项目经验、熟悉AI在企业服务领域应用者优先。 2. 具备独立负责大型客户的丰富经验，拥有出色的客户沟通能力，能够有效协同内部各部门与各级关键客户，基于咨询策略与AI分析，达成共同决策。 3. 具备优秀的沟通&表达能力、强大的抗压能力和出色的团队协作精神，逻辑思维严谨，书面表达与输出能力强，能够高效运用AI工具辅助工作。 4. 曾在大型互联网、咨询公司任职，拥有云计算、大数据、saas等背景经验，且在AI相关领域有实践经验者优先；具备跨行业、区域性服务经验，善于运用AI技术解决不同场景问题者优先。 |
| 5216 | dingtalk | 100000940018 | 钉钉 | 钉钉-Java服务端开发-AI产品方向 | 杭州 | department, salary | requirements=1、本科及以上计算机相关专业，Java基础扎实，熟悉各类常用框架和中间件。  2、有丰富的Linux下开发经验，具备高并发分布式系统研发经验，有丰富的线上系统经验。  3、稳定性意识强，较强的工作责任心和良好的沟通协调能力，能在压力下独立解决问题。有创业之心，客户第一，具备良好的自驱力。  4、有客户关系管理产品研发经验者优先，有平台或中台建设经验优先； |
| 5317 | feishu | 7658219588165699849 | MiniMax | AI 招聘专家 - 基座模型技术方向 | 北京, 上海 | department, experience, education, salary | requirements=1、学历与经验背景： 本科及以上学历（计算机、人工智能、人力资源等相关专业优先），3年以上互联网大厂、硬科技或顶级 AI 独角兽高端技术招聘（高招）经验；具备基座模型、AGI 赛道或海外技术人才寻访经验者优先。 2、技术理解力与海外寻访能力： 对 AI 基础大模型、AI Infra（基础设施）有基本的行业认知，能够读懂技术人才的学术论文背景/开源项目贡献；具备优秀的英语沟通能力（或海外留学/工作背景），能够流畅对接全球多元化背景的候选人。3、具备卓越的沟通协调能力和复杂问题解决能力，拥有较高的人际敏感度与雇主品牌影响力，能与顶尖科学家、技术专家建立平等且深度的对话。 4、自驱力与抗压： 热爱招聘工作，具备极强的自我驱动力、结果导向意识和抗压能力，乐于在高动态、高挑战的 AGI 变革期接受挑战。 5、接受具备硬核技术寻访能力的乙方（顶级猎头公司 AI/高科技方向）转甲方招聘背景。 |
| 5318 | feishu | 7657846537234139442 | MiniMax | 云资源 FinOps 技术专家 | 北京, 上海 | department, experience, education, salary | requirements=1. 5 年以上云成本 / FinOps / 资源运营经验，有**多云（阿里云 / 腾讯云等）**成本优化的一线实战。 2. 精通云计费模型、成本分摊、预留 / 节省计划 / 竞价、用量分析；扎实的数据分析能力（SQL / BI / 脚本）。 3. 懂基础设施资源（计算 / 存储 / 网络 / GPU）的成本结构与优化手段。 4. coding / 自动化能力（Python 等）——能造成本分析 / 治理工具，不是纯 Excel。 5. 强跨团队协同与价值表达：能以"帮你省钱"的服务姿态推动降本，把成本合理性讲清楚。  加分 FinOps 相关认证；GPU 算力成本优化经验；成本 / 用量平台建设；相关开源贡献。 |
| 21613 | jd | 219984 | 京东 | 体检院区医师 | 北京市 | experience, education, salary | requirements=1. 教育背景 学历要求：本科及以上学历，临床医学或相关专业；2. 工作经验 工作经验：具备3年以上临床妇科诊疗工作经验，熟悉常见病、多发病的诊疗流程；具备独立处理门诊病例的能力；有体检中心或健康管理机构工作经验者优先；3. 能力要求 临床技能：熟练掌握体检检查、诊断及治疗操作规范；能够规范书写病历，合理开具检查与处方；具备超声等影像学检查读片能力者优先； 业务理解：了解健康体检行业特点，能够结合体检报告进行健康风险评估与指导；具备良好的医患沟通能力，能够清晰解答客户健康咨询； 4. 基本素质 团队协作：具备良好的沟通能力和团队合作精神，能够与体检团队高效配合； 责任心：具有强烈的责任心，对医疗服务质量负责，严格遵守医疗规范与伦理； 问题解决：具备独立分析和解决问题的能力，能够妥善处理临床工作中的各类情况； 服务意识：具备良好的服务意识与同理心，关注客户健康需求； 学习能力：具备持续学习能力，关注医学领域最新进展，不断提升专业水平。  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。 |
| 21614 | jd | 219444 | 京东 | 口腔医师 | 北京市 | experience, education, salary | requirements=1. 学历要求：本科及以上学历，临床医学、口腔医学等相关专业；   2. 工作经验：具备口腔临床工作经验，熟悉口腔常见病、多发病的诊断与治疗，有独立接诊能力；   3. 能力要求：掌握口腔基础操作技能，能够规范完成口腔检查、病历书写及治疗操作；具备良好的临床判断能力和操作规范性；   4. 基本素质：具备良好的沟通能力，能够与患者有效交流，建立信任关系；具有强烈的责任心和服务意识，注重医疗安全；具备团队合作精神，能够配合团队完成诊疗工作；具备良好的抗压能力，适应门诊工作节奏。  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。 |
| 19371 | kuaishou | 30893 | 快手 | 海外数据分析师-【KSIB】 | 北京 | education, salary | requirements=1、拥有统计学、运筹学、计算机等理工科类或商科类相关专业的本科及以上学历； 2、概率统计基础扎实，了解 AB 实验，熟悉 Hive 或 SQL，熟练使用 R/Python/Tableau 等分析工具； 3、具有良好的商业分析能力和商业敏感度，能够快速学习了解业务知识，能够将模糊的商业问题转化为具体的分析课题并解决； 4、出色的逻辑能力和表达能力，自驱、目标导向，善于和业务团队沟通，能够跨部门组织协调，推动问题解决。 |
| 19372 | kuaishou | 31462 | 快手 | 运营活动招商-【主站】 | 北京 | education, salary | requirements=1、本科及以上学历，3年以上招商/商业化变现相关经验，有完整的千万级以上招商项目从0到1的执行落地经验； 2、有互联网行业（短视频/直播/内容社区/社交平台优先）招商、商业化或运营相关工作经验，熟悉互联网内容产品的商业化逻辑；  3、对数据高度敏感，能独立搭建数据分析框架进行业务数据拆解与归因分析，并能合理使用AI工具提升信息整理、数据解读、策略推演和复盘沉淀效率，以数据驱动招商策略制定和成本决策；  4、加分项：有内容/活动IP商业化变现经验，理解"内容即广告"的植入式招商模式；有大型专项活动（年度级S+项目）招商统筹经验，熟悉专项从目标设定到交付复盘的全流程；有客户资源积累（品牌方/代理商/行业直客优先）。 |
| 17698 | meituan | 4606822362 | 美团 | 美团外卖-大区生态运营（餐饮方向） | 北京市 | education, salary | requirements=1.熟悉业务和行业发展，具备生态视野和规划能力，理解媒体传播规律。 2.具备各部门的协同能力，能整合各方资源，解决关键问题以及推动正向案例的输出。 3.有较强的社会责任感及共情能力，能够及时发现商户经营的一些正面案例及真实的问题，并高效推动落地。 4.具备一定的整合营销策划、活动策划及危机处理能力。 |
| 17699 | meituan | 4601955918 | 美团 | 外卖行业运营 | 北京市 | education, salary | requirements=1、5年以上互联网广告、本地生活平台或效果营销相关经验，其中至少2年具备团队管理或跨职能复杂项目统筹经验，能主导端到端策略落地，并在快节奏环境中保持高效输出；具备将 AI 工具融入日常工作流的实践经验，能带领团队探索 AI 辅助运营提效的落地路径。 2、具备扎实的数据分析能力，熟练使用数据分析工具及 AI 辅助分析手段（如大模型自然语言问数、AI 智能归因分析工具），能独立完成从数据提取到业务洞察的全链路分析，并以数据驱动策略迭代与决策。 3、对餐饮行业有深刻理解，熟悉连锁品牌、区域龙头、中小商户等不同客群的经营逻辑、营销诉求与决策链路，能借助 AI 工具批量生成客户画像与行业洞察报告，具备前瞻性行业洞察力，能预判品类演进方向并提前布局运营抓手。 4、具备极强的跨部门协同与推动力，善于在产品、运营、销售、技术等多方角色间建立共识、整合资源、对齐目标；熟练使用 AI 辅助会议纪要生成、任务拆解等工具提升协同效率，同时拥有优秀的沟通表达与影响力，能向上汇报、向下赋能、横向协同。 5、有韧性，面对激烈竞争、业绩压力或突发变化时，能快速调整策略、稳定团队、聚焦核心，始终以结果为导向推进工作。对 AI 工具保持持续学习热情，能主动探索新工具并应用于实际业务场景。 |
| 1944 | netease | 69082 | 网易 | 【平台】海外广告投放（海外交易平台） | 广州市 | salary | requirements=1、本科以上学历，有至少3年谷歌广告投放经验，有独立站投放经验者优先； 2、熟悉Facebook/Google等媒体的广告竞价机制，具有丰富海外市场拓展和市场网络营销经验； 3、逻辑清晰，善于分析，能够快速基于数据以及市场变化及时调整推广策略； 4、思路开阔，挖掘产品卖点内容，结合海外实际输出广告创意； 5、喜爱玩游戏，对游戏类型了解涉猎广的优先。 |
| 1945 | netease | 76669 | 网易 | 【平台】音视频开发工程师（编解码） | 广州市 | salary | requirements=• 扎实的计算机基础，优秀的 C/C++ 编程能力和编码习惯，熟悉多线程、协程和 socket 编程。 • 在音视频编解码领域有丰富的开发和优化经验，熟悉码率控制、采集、渲染等模块；有跨平台（Win/Android/macOS/iOS/Linux）开发经验者优先。 • 熟悉硬件编解码者优先： -硬编：NVIDIA NVENC / AMD AMF / Intel QSV / MediaCodec / VideoToolbox -硬解：NVDEC / DXVA(DX11VA) / MediaCodec / VideoToolbox • 有图形（GPU）开发经验者优先：帧预处理（色彩转换、缩放等），倾向零拷贝链路（如 D3D11/Metal/OpenGL ES 纹理共享）。 • 有跨平台音视频采集经验者优先（屏幕/摄像头/音频采集，覆盖 Win/Android/macOS/iOS/Linux）。 • 熟悉常见音视频传输协议，了解常用框架及库，如 WebRTC、FFmpeg 等。 • 熟练使用 AI 编程工具者优先（如 Codex、Claude Code 等 AI Agent，能借助 AI 提升开发效率）。 • 良好的学习能力，团队合作精神与责任心。 |
| 4346 | quark | 100013240005 | 夸克 | 千问事业部-llm/omni算法专家(全模态语音助手方向)-北京/杭州 | 北京, 杭州 | department, salary | requirements=1、计算机科学、人工智能、数学、电子信息工程或相关专业硕士及以上学历。 2、深入理解Transformer架构，熟悉SFT/RLHF/DPO/PPO/GRPO等算法原理及使用边界。 3、熟悉大模型训练与推理，熟悉至少一种主流训练框架：如Swift、Megatron、LlamaFactory、Trl等。 4、具备LLM/VLM/Omni等方向的研发经验，兼具扎实相关理论基础与实践能力。 |
| 4347 | quark | 7000039708 | 夸克 | 千问事业部-夸克&千问-AI图像和视频内容营销/运营-北京 | 北京 | department, salary | requirements=1、3 年以上内容平台、达人运营或内容合作经验，有独立负责一块内容或达人业务的实际经历； 2、对 AI 内容有成熟理解，能够判断 AI 内容的能力边界、适用场景以及对业务的实际价值；能迅速通过内容找到合适的达人画像和内容推广方向； 3、熟悉达人生态与合作模式，理解不同层级达人的创作方式与商业诉求，同时有很强的内容理解、审美和判断力 4、具备从内容策略制定到执行落地的完整能力，有较强的自驱力，对内容结果负责而非仅执行需求；具备良好的数据意识与跨团队协作能力，能在不确定环境中推动内容方案落地。  加分项 *有 AI 图片、AI 视频创作经验，或运营过小红书、抖音、B站、X（Twitter）等内容账号，并有爆款案例。 *长期关注全球 AI 行业动态，对海外 AI 社区和产品保持持续关注，能够快速捕捉新模型、新玩法并落地应用。 |
| 1 | tencent | 2059455036769091584 | 腾讯 | 混元 AI 产品经理（北京/深圳） | 北京 | education, salary, requirements | requirements= |
| 2 | tencent | 2028730347814027264 | 腾讯 | 高性能计算专家（深圳/北京） | 北京 | education, salary, requirements | requirements= |
| 5141 | tongyi | 100007700004 | 通义实验室 | Token Foundry-算法专家-多语言同传大模型 | 北京, 杭州 | department, salary | requirements=1. 研究生以上学历，熟悉Pytorch、Tensorflow等至少一种深度学习框架； 2. 熟悉机器学习，有语音语言方向研究经历。实际参与过大模型预训练、微调、偏好对齐中至少一项，熟悉相关流程； 3.良好的技术洞察力和优秀的业务分析能力，能应对多样的业务算法需求。乐于合作，能够与工程、产品等团队协同。对大模型应用、AGI有很强的技术热情。 4.良好的科研能力，在所在领域有高影响力的技术成果和沉淀优先（如论文、开源项目等）优先； 5.有多语言多模态大模型技术背景优先。 |
| 5142 | tongyi | 100011240003 | 通义实验室 | AI创新事业部-世界模型算法专家/高级专家 (World Model)-未来生活实验室 | 北京, 杭州 | department, salary | requirements=1.  计算机、人工智能、自动化等相关专业。 2.  在多模态大模型和生成式模型（扩散/自回归模型）上有资深背景，对前沿进展和领域问题有深入理解。 3. 具有主流大模型的实战经验 (视频生成/VLM/LLM/LMM)，有国际高影响力的项目成果。 4.  对 AGI 有极强的热情，能够从第一性原理出发解决世界模型领域问题。 |
| 20780 | xiaohongshu | 17846 | 小红书 | AI Native开发-广告素材AIGC | 北京市，上海市 | experience, education, salary | requirements=学历与经验： 本科及以上学历，计算机、人工智能、电子信息等相关专业； 技术功底： 1. 本科及以上学历，计算机、人工智能、电子信息等相关专业； 2. 具备优秀的审美能力和创意嗅觉，对小红书等内容社区的视觉风格、文案调性有一定洞察； 3. 对广告效果营销有较好的理解，能从业务视角思考技术方案的价值； 4. 具备出色的问题分析与解决能力，良好的沟通协调能力和团队合作精神，对技术驱动创意充满热情； |
| 20781 | xiaohongshu | 15940 | 小红书 |  Serverless 研发工程师-引擎架构 | 北京市，上海市 | experience, education, salary | requirements=工程基础 熟练掌握 Java 或 Go，具备扎实的编程功底与大规模分布式系统开发经验；深入理解操作系统、网络、存储基本原理，对系统性能调优、高并发、高可用系统设计与上线经验者优先。  云原生与 PaaS 平台工程 深入理解 Kubernetes 核心机制（调度器、Operator、CRD、服务网格），有平台层改造或自研经验，或有 AWS Lambda、Google Cloud Run、阿里云 SAE 等平台的使用及原理理解者优先。  搜索与索引平台经验（加分） 有搜索平台或索引系统的核心研发经验，理解倒排索引、向量索引、分布式检索的基本原理；熟悉大规模索引的构建流程与时效性保障，有实时/离线索引更新、多副本一致性、索引灰度切换等工程实践者优先；了解 Elasticsearch、Milvus 或自研检索引擎设计取舍者加分。  AI 基础计算平台（加分） 熟悉 GPU 集群管理与异构算力调度，有 Ray、Volcano、Slurm 等分布式调度框架使用或改造经验者优先；有 kv cache 共享、prefill/decode 分离、speculative decoding 等推理调度优化工程实践者加分；有 AIOps 实践经验（智能告警、根因分析、容量预测）或将 AI 能力集成进平台工具链经验者加分。 |

### department（995）

| 行号 | platform | job_id | company | title | location | 缺失字段 | 详情 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 4346 | quark | 100013240005 | 夸克 | 千问事业部-llm/omni算法专家(全模态语音助手方向)-北京/杭州 | 北京, 杭州 | department, salary | requirements=1、计算机科学、人工智能、数学、电子信息工程或相关专业硕士及以上学历。 2、深入理解Transformer架构，熟悉SFT/RLHF/DPO/PPO/GRPO等算法原理及使用边界。 3、熟悉大模型训练与推理，熟悉至少一种主流训练框架：如Swift、Megatron、LlamaFactory、Trl等。 4、具备LLM/VLM/Omni等方向的研发经验，兼具扎实相关理论基础与实践能力。 |
| 4347 | quark | 7000039708 | 夸克 | 千问事业部-夸克&千问-AI图像和视频内容营销/运营-北京 | 北京 | department, salary | requirements=1、3 年以上内容平台、达人运营或内容合作经验，有独立负责一块内容或达人业务的实际经历； 2、对 AI 内容有成熟理解，能够判断 AI 内容的能力边界、适用场景以及对业务的实际价值；能迅速通过内容找到合适的达人画像和内容推广方向； 3、熟悉达人生态与合作模式，理解不同层级达人的创作方式与商业诉求，同时有很强的内容理解、审美和判断力 4、具备从内容策略制定到执行落地的完整能力，有较强的自驱力，对内容结果负责而非仅执行需求；具备良好的数据意识与跨团队协作能力，能在不确定环境中推动内容方案落地。  加分项 *有 AI 图片、AI 视频创作经验，或运营过小红书、抖音、B站、X（Twitter）等内容账号，并有爆款案例。 *长期关注全球 AI 行业动态，对海外 AI 社区和产品保持持续关注，能够快速捕捉新模型、新玩法并落地应用。 |
| 4348 | quark | 100010100029 | 夸克 | 千问事业部-Android高级开发工程师（UC浏览器 ）-北京/广州 | 北京, 广州 | department, salary | requirements=1.  统招本科及以上学历，3年以上安卓应用开发经验，软件工程、计算机、通信相关专业，基础知识扎实，熟练掌握数据结构，网络等基础知识；良好的编码风格；  2. 精通Kotlin、Java，熟悉常用设计模式，深入理解面向对象的设计思想； 3. 精通UI开发，动画开发，熟练各种UI组件并了解其原理；  4. 精通多线程、网络异步交互等功能的开发技术； 5. 熟练使用常用图片、网络等框架，并能够进行问题排查和解决；  6. 熟练Android性能分析工具，有UI卡顿、APP启动、内存、WebView等性能优化经验优先；  7. 有良好的沟通表达能力，积极乐观； 8. 有超级APP开发经验者优先； 9. 有跨端技术经验（Flutter/React Native/KMP等）者优先；  在这里，你将获得： 行业前列的技术平台：技术纵深扎实，场景宽度充足。 AI 变革先锋机会：AI 改造业务起点，创新空间大。 顶级 AI 资源：大模型 token 福利充足，AI 编程工具自由使用。 完善成长体系：新人专属导师，快速融入团队。 |
| 4349 | quark | 100014900004 | 夸克 | 千问事业部-数据挖掘工程师-北京 | 北京 | department, salary | requirements=1. 教育背景： 计算机、数学、统计学或相关专业本科及以上学历。 2. 经验要求： 具有3年以上相关工作经验，有大型互联网公司数据科学或算法工程经验者优先。 有广告系统、DMP平台落地经验者优先。 3. 算法能力： 熟悉常用的机器学习算法（LR, GBDT, XGBoost, RF等）及深度学习框架，有图算法(Label Propagation、Connected Components、GraphSAGE等)工程实践经验者优先。 4. 工程能力： 编码能力强，能熟练应用SQL，掌握Java/Scala/Python其中至少一种语言。熟悉大数据生态(Spark/Hadoop/Hive)，熟悉及掌握阿里云DataWorks/MaxCompute等大数据技术平台的技术原理和应用者优先，有Flink实时计算开发经验者优先，熟悉图数据库使用者优先。 5. 业务思维： 具备良好的数据敏感度和业务理解力，能从业务痛点出发进行技术选型，具备将技术价值转化为业务价值的能力。 6. 软性素质： 工作认真负责，有快速学习的能力，热爱数据工作，主动积极，有好奇心。具备优秀的跨团队沟通协作能力，能独立推动复杂项目落地。  在这里，你将获得： 千亿级数据仓库建设：深度参与互联网核心内容与变现业务的数据链路建设，打造完整数据闭环。 全栈技术场景：覆盖离线处理、实时计算、数据分析与算法挖掘，技术发挥空间充足。 业务核心驱动：数据直接赋能广告商业化决策与内容运营增长，价值感强 |
| 4350 | quark | 7000034305 | 夸克 | 千问事业部-Agent 算法专家（AI内容创作）-北京 | 北京 | department, salary | requirements=1. 计算机、人工智能、数学、统计等相关专业，本科及以上学历；5 年及以上NLP / 机器学习 / LLM 应用相关工作经验 2. 扎实的编程与工程能力，熟练 Python；具备复杂 LLM/Agent 系统的架构设计经验（多 Agent 协作、长流程任务编排、上下文与记忆管理、工具调用体系等） 3. 有 Agent 类项目的完整落地经验（如复杂内容生成、研究/写作助手、长流程任务自动化、多步工具调用 Agent 等），有过 1-2 个独立主导的 Agent 系统设计经验 4. 有良好的自驱力，能独立把控一个完整方向（协同多名工程师），乐于和业务专家共建标准与流程，有过将专家经验沉淀为可复用 Skill / 评测体系的经验加分 |
| 4351 | quark | 100016700001 | 夸克 | 千问事业部-agent算法（AI内容生产）-北京 | 北京 | department, salary | requirements=1.计算机、人工智能、自动化或相关专业硕士及以上学历，3年以上算法研发经验，智能视频剪辑、广告内容生产或多模态大模型应用落地经验者优先。 2.精通Python，熟练掌握C/C++，深入理解PyTorch/TensorFlow等主流深度学习框架，熟练掌握vibe coding开发范式。 3.熟悉全球主流多模态大模型与推理大模型的技术特性、能力边界与演进趋势，具备跨模型对比评估、场景适配与混合架构设计能力，能针对内容生产链路中的不同环节完成模型选型、路由调度与工程化权衡。 4.熟悉视频内容处理全链路技术，包括多模态视频理解、镜头语义理解、文案自动叙事结构生成、转场/特效合成、多模态融合Pipeline设计，具备从算法原型到工程落地的完整交付能力。 5.具备良好的业务与产品思维，能够将模糊的业务需求转化为可落地的技术方案，理解核心业务指标，并通过算法迭代持续驱动业务价值；具备优秀的问题拆解、跨团队沟通与文档沉淀能力。 6.加分项：具备AI视频剪辑工程落地经验，熟悉主流AI内容生产平台架构；在 NeurIPS/ICML/ACL 等顶会发表过 LLM/Agent 相关论文；拥有高星开源项目贡献。 |
| 4352 | quark | 100006720002 | 夸克 | 产品营销-产品营销专家-市场 | 杭州 | department, salary | requirements=1.洞察与提炼能力：熟练掌握洞察方法并对产品、行业、竞品、消费者进行洞察，给产品线带来市场声音的输入，并能够快速理解复杂产品逻辑，并精准提炼差异化卖点与用户价值主张； 2.规划能力：能输出结构化规划，具备产品周期意识，能根据产品所处阶段（冷启动/成长/成熟）制定匹配的营销策略； 3.项目经验：有成功打造过具备行业影响力或广泛用户参与度的市场营销项目经验（请附案例）； 4.沟通影响力：出色的跨部门沟通与项目管理能力，能在快节奏环境中高效推进多线程任务； 5.加分项，有AI领域相关项目经验，具备高成长性市场方法，对内容和创意敏感。  经验要求： 3年以上互联网产品营销、或品牌相关工作经验，有从0到1产品推广经验者优先。 |
| 4353 | quark | 100011480015 | 夸克 | 千问事业部-用户增长渠道运营-拉活\|千问 | 北京 | department, salary | requirements=1、本科及以上学历，有2年以上信息流广告投放经验，有DPA/RTB等投放模式经验优先，有AI/工具/网服行业经验优先，深入了解主流投放平台竞价机制和优化策略，通过账户策略优化、代理商管理提效，实现目标增长； 2、逻辑清晰，数据敏感，对流量成本敏感，具备较强的判断能力及抗压能力，能通过数据拆解问题并提出解决方案，具备精细化管控能力； 3、具备抽象思维能力，善于思考和总结，具备创新精神，能将繁琐重复工作自动化，日常工作中有AI运用实操优先； 4、热爱学习，善于沟通，有团队合作意识，能够帮助团队完成共同目标，适应快节奏的投放优化与策略调整 |
| 4354 | quark | 100022100001 | 夸克 | 千问事业部-大模型推理框架系统研发专家-杭州/北京/广州 | 北京, 杭州, 广州 | department, salary | requirements=1. 精通C++/Python，熟悉CUDA编程和GPU推理系统开发，具备扎实的系统软件、分布式系统、并行计算和高性能服务端开发基础； 2. 深入理解大模型推理框架核心机制，包括Prefill/Decode、KV Cache管理、Continuous Batching、PagedAttention、Speculative Decoding、Quantization等； 3. 熟悉分布式推理并行与通信优化，包括Tensor Parallel、Pipeline Parallel、Expert Parallel、Context Parallel、MoE All-to-All、通信计算重叠、负载均衡等； 4. 熟悉GPU间和跨节点通信机制，了解NCCL、RCCL、MPI、UCX、RDMA、InfiniBand、NVLink、NVSwitch、PCIe等相关技术，具备端到端性能分析和问题定位能力； 5. 熟悉vLLM、SGLang、TensorRT-LLM等推理或服务框架，有核心模块开发、深度改造或生产级落地经验者优先。 |
| 4355 | quark | 100021600005 | 夸克 | 千问事业部-大模型压缩&推理加速高级专家-杭州/北京/广州 | 北京, 杭州, 广州 | department, salary | requirements=1. 在量化、剪枝、稀疏、蒸馏、投机解码、KV Cache压缩、Token压缩等至少一个方向有深入研究或大规模工程落地经验； 2. 熟悉主流低比特量化方法，包括FP8、FP4、INT8、INT4、PTQ、QAT、SmoothQuant、AWQ、GPTQ、KV Cache量化、混合精度策略等，能够分析并解决低比特部署中的精度退化问题； 3. 具备扎实的Python/PyTorch开发能力和严谨的实验分析能力，能够设计评测集、消融实验和回归机制，平衡模型效果、推理延迟、吞吐和成本收益； 4. 有大规模模型压缩、推理加速或线上LLM服务优化经验者优先；在NeurIPS、ICML、ICLR、ACL、EMNLP、MLSys等会议发表相关论文或有高质量开源贡献者优先。 |
| 4356 | quark | 100011460013 | 夸克 | 千问事业部-用户增长投放运营专家-拉活 | 北京 | department, salary | requirements=1、本科及以上学历，有4年以上信息流广告投放经验，有DPA/RTB等投放模式经验优先，有AI/工具/网服行业经验优先，深入了解主流投放平台竞价机制和优化策略，熟悉投放流量分布和点位信息，对流量买量效率和成本负责； 2、逻辑清晰，数据敏感，对流量成本敏感，具备较强的判断能力及抗压能力，能通过数据拆解问题并提出解决方案，具备精细化管控能力； 3、具备抽象思维能力，善于思考和总结，具备创新精神，能将繁琐重复工作通过AI实现提效率和提效果，可实操落地； 4、热爱学习，善于沟通，有团队合作意识，能够帮助团队完成共同目标，适应快节奏的投放优化与策略调整 |
| 4357 | quark | 100021840004 | 夸克 | 千问事业部-高级数据分析师-北京 | 北京 | department, salary | requirements=1、 清晰的分析逻辑以及良好的业务洞察能力，能快速发现问题、拆解问题并定位到影响业务的关键点； 2、 数据处理能力强，对业务数据、日志等流转链路清晰，掌握各层数据逻辑；可使用多种方式提取数据并进行分析，熟练掌握hive、SQL、excel等相关数据提取及处理工具； 3、 业务理解力好，能够通过对业务脉络的梳理，形成框架完整、逻辑清晰的指标体系； 4、 良好的沟通能力和团队协作能力，能够有效地和业务、数据技术团队沟通交流，具有跨团队的推进项目的能力，并基于数据洞察向业务输出建议，对数据工作有热情、态度积极主动； 5、 具备数据运营与数据产品能力，针对业务问题，可以透过实验设计，并制订科学的衡量方法，辅助业务做出判断； 6、 良好的数据敏感度，能从海量数据提炼核心结果，有丰富的数据分析、挖掘、清洗和建模经验，能独立编写商业数据分析报告。 |
| 4358 | quark | 100013100004 | 夸克 | 千问事业部-前端研发工程师（UC浏览器）-广州 | 广州 | department, salary | requirements=1、统招本科及以上学历，计算机相关专业优先，具备扎实的编程基础。 2、精通 HTML5、CSS3、JavaScript（ES6+），熟练掌握 React / Vue 等主流框架，对前端技术体系有系统性理解。 3、3 年以上前端开发经验，有大型 Web 应用或大型 APP 前端开发经验者优先。 4、熟悉前端性能优化方法论，掌握 Webpack / Vite / Rollup 等构建工具链，对前端工程化有深入实践。 5、能熟练运用 AI Coding 工具（如 Copilot 等）提升研发效率，具备 AI 辅助开发的实际经验者优先。 6、有 Electron 桌面端开发经验或 Weex 等跨端技术经验者优先。 7、沟通表达清晰，具备良好的团队协作意识与责任心。 8、对新技术保持热情，具备持续学习与自我驱动能力。  在这里，你将获得： 行业前列的技术平台：技术纵深扎实，场景宽度充足。 AI 变革先锋机会：AI 改造业务起点，创新空间大。 顶级 AI 资源：大模型 token 福利充足，AI 编程工具自由使用。 完善成长体系：新人专属导师，快速融入团队。 |
| 4359 | quark | 100009920043 | 夸克 | 千问事业部-鸿蒙高级开发工程师（UC浏览器 ）-北京/广州 | 北京, 广州 | department, salary | requirements=1. 统招本科及以上学历，1年及以上鸿蒙开发经验，软件工程、计算机、通信等相关专业； 2. 精通ArkTS/ArkUI，熟悉鸿蒙开发框架以及常用的三方库； 3. 熟悉鸿蒙系统UI控件及自定义控件，熟悉移动设备的开发特点； 4. 了解鸿蒙系统性能瓶颈，会使⽤性能调优⼯具进⾏性能优化； 5. 熟悉常用设计模式，深入理解面向对象的设计思想； 6. 有良好的编程风格和沟通表达能力，学习能力强，对技术有热情，自我驱动； 7. 能承受工作压力，有较强的团队协作意识； 8. 有Android/iOS工作经验，熟悉Java、Kotlin/Object-C编程语⾔者优先；  在这里，你将获得： 行业前列的技术平台：技术纵深扎实，场景宽度充足。 AI 变革先锋机会：AI 改造业务起点，创新空间大。 顶级 AI 资源：大模型 token 福利充足，AI 编程工具自由使用。 完善成长体系：新人专属导师，快速融入团队。 |
| 4360 | quark | 100021960003 | 夸克 | 千问事业部-安全评测运营专家-北京 | 北京 | department, salary | requirements=1、本科及以上学历，计算机、数据科学、信息安全、新闻传播或相关专业，具备内容风险理解能力； 2、2年以上互联网内容安全运营、安全策略运营、数据分析、安全评测或相关工作经验，有 LLM 自动化评测、红队测试经验优先； 3、具备扎实的数据分析能力，熟练使用Excel/SQL/Python 等工具进行数据处理与分析；能够结合 AI 工具提升评测与归因效率； 4、具备优秀的文字表达和逻辑归纳能力，能独立输出清晰、结构化的评测报告； 5、了解大模型的基本原理、训练阶段及内容安全领域的典型风险（如有害内容分类、越狱攻击等）并能够持续关注行业新知识与风险变化； 6、能在信息不完整的场景下主动定义评测边界、发起跨团队对齐，具备较强的问题定义与推动能力。 |
| 4361 | quark | 100010960008 | 夸克 | 千问事业部-千问-AI 内容运营专家-AI生成内容 | 北京 | department, salary | requirements=1. 本科及以上学历，3 年以上内容运营经验，有 AI 产品、内容社区、图片/视频平台运营经验者优先。 2. 热爱 AI，熟悉主流 AI 图片、视频模型及 AI Agent，具备持续学习新模型、新工具的习惯，并能够熟练运用 AI 提升工作效率。 3. 具备优秀的内容 Sense，对互联网内容、热点趋势、用户审美和传播规律有敏锐判断，能够快速发现并策划具有传播潜力的内容。 4. 对国内外主流 AI 模型有较深理解，了解不同模型的能力边界、优势及适用内容，能够判断模型适合创作什么内容，并将模型能力转化为运营策略。 5. 具备较强的策略思维、数据分析能力和跨团队协作能力，能够独立负责项目，推动业务结果落地。  加分项  * 有 AI 图片、AI 视频创作经验，或运营过小红书、抖音、B站、X（Twitter）等内容账号，并有爆款案例。 * 长期关注全球 AI 行业动态，对海外 AI 社区和产品保持持续关注，能够快速捕捉新模型、新玩法并落地应用。 |
| 4362 | quark | 100022020001 | 夸克 | 千问事业部-AI产品经理-审核 / 安全评测方向 | 北京 | department, salary | requirements=1、本科及以上学历，3年以上产品经理经验，有AI产品、安全产品、内容审核平台经验优先； 2、熟悉大模型产品形态与原理，对LLM、Agent、RAG、AI Workflow有理解和实践经验，熟悉MCP、CLI工具链及主流AI Coding工具（如Cursor、Claude Code等）优先； 3、对内容安全、审核、风控、安全评测有理解； 4、具备较强的数据分析与系统抽象能力，有较强跨团队推动能力，能够协调研发、安全运营共同推进项目，拥有很强的自驱和学习能力，能够快速学习复杂业务、AI新变化。 |
| 4363 | quark | 100019560003 | 夸克 | 千问事业部-客户端技术专家-音视频播放器容器方向 | 杭州, 广州 | department, salary | requirements=1、本科及以上学历，计算机、通信、电子工程、信号处理等相关专业优先； 2、五年以上客户端、音视频、多媒体 SDK 或播放器相关研发经验，有完整线上项目交付经验； 3、有良好的编程习惯和工程质量意识，能够设计清晰、可维护、可持续迭代的代码结构； 4、熟练掌握 C / C++，或熟练掌握 Android / iOS 端侧开发语言，并具备良好的工程编码能力、数据结构和算法基础； 5、熟悉 FFmpeg、WebRTC、GStreamer、IJKPlayer 等音视频框架之一或多个，理解编解码、渲染、传输、音频处理、弱网优化等核心技术； 6、对 C 端产品体验有较强敏感度，重视播放稳定性、流畅度、性能、功耗和用户体验，能独立分析并解决音视频链路中的线上体验问题； 7、能熟练使用 AI-coding 工具进行需求拆解、代码生成、重构、测试补齐、问题定位和研发提效，并能将 AI-coding 融入日常开发流程； 8、对 AI-coding 和音视频技术有钻研精神，愿意持续探索新工具、新范式并沉淀实践方法；简历需体现 AI-coding 相关作品、实践项目或可展示链接； 9、具备良好的沟通协作能力，能够快速理解业务需求并推动技术方案落地；有播放器容器化、平台化建设经验者优先。  |
| 4364 | quark | 100019340002 | 夸克 | 千问事业部-客户端架构&性能优化高级专家-千问App | 杭州, 广州 | department, salary | requirements=1. 具备优秀的计算机基础与架构设计能力，精通 Objective-C/Java或者C++，熟练掌握各平台底层原理及调试工具；在大型复杂业务下的客户端架构设计上有成功实践，具备成熟的 AI Coding 工程化落地经验优先； 2. 拥有极强的复杂问题分析与解决能力，具备较好的技术审美与质量意识；在业务领域性能优化、内存治理、启动优化等领域有积累，有大模型对话、Agent 框架设计及端到端性能调优经验者优先； 3. 对移动互联网及 AI 技术趋势有深刻洞察，具备强烈的技术好奇心与创新精神；能在不确定性中探索新方向，致力于通过技术赋能业务增长或提升研发组织效能。 |
| 4365 | quark | 100018620015 | 夸克 | 千问事业部-Java 技术专家-运营业务&平台 | 广州 | department, salary | requirements=1. 计算机、通信、信息相关专业本科以上学历，3年以上的大型服务端项目研发经验； 2. 编程基本功扎实，熟悉常用数据结构和算法，擅长Java编程语言，能编写高质量简洁清晰的代码，能熟练使用AI编程工具来提升编码效率和质量； 3. 熟悉TCP/IP、HTTP协议相关知识，熟悉Unix/Linux环境和系统编程，深入掌握服务器编程模型；熟悉MySQL数据库及主流NoSQL数据库；了解AI相关的前沿技术及工具； 4. 有较好的逻辑思维能力，较强的抽象、概括、总结能力；有较好的沟通交流能力，善于主动思考和行动，乐于解决具有挑战性的问题，对待技术有强烈兴趣； 5. 工作认真、严谨，具备较强的学习能力和责任心，有互联网工作经验者优先考虑，有AI相关技术经验者优先考虑。 |

### experience（14588）

| 行号 | platform | job_id | company | title | location | 缺失字段 | 详情 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 303 | tencent | 2072158294692245504 | 腾讯 | PUBGM资深电竞赛事经理 | 深圳 | experience, education, salary, requirements | requirements= |
| 304 | tencent | 2072158301273108480 | 腾讯 | PUBGM电竞赛事经理 | 深圳 | experience, education, salary, requirements | requirements= |
| 305 | tencent | 2072158307690393600 | 腾讯 | PUBGM电竞生态运营 | 深圳 | experience, education, salary, requirements | requirements= |
| 360 | tencent | 2071916705273262080 | 腾讯 | Senior Legal Counsel (Overseas Advertising Platform & Public Welfare Projects Compliance) | 深圳 | experience, education, salary, requirements | requirements= |
| 361 | tencent | 2071916700101685248 | 腾讯 | Legal Counsel, Cloud | 深圳 | experience, education, salary, requirements | requirements= |
| 487 | tencent | 2071448614940622848 | 腾讯 | Strategic Investment Director | 深圳 | experience, education, salary, requirements | requirements= |
| 1199 | tencent | 2064548152966561792 | 腾讯 | PUBGM中东内容运营 | 深圳 | experience, education, salary, requirements | requirements= |
| 1227 | tencent | 2064351850118950912 | 腾讯 | 中国区运营策划 | 深圳 | experience, education, salary, requirements | requirements= |
| 1328 | tencent | 2057315507438268416 | 腾讯 | Senior Software Engineer II | 深圳 | experience, education, salary, requirements | requirements= |
| 1427 | tencent | 2062117130287104000 | 腾讯 | Senior Software Engineer III | 深圳 | experience, education, salary, requirements | requirements= |
| 1499 | tencent | 2060274994654658560 | 腾讯 | 海外游戏市场与用户研究经理 (日文) | 深圳 | experience, education, salary, requirements | requirements= |
| 1500 | tencent | 2060259938076377088 | 腾讯 | 高品质ARPG端游 Gameplay 开发工程师 | 深圳 | experience, education, salary, requirements | requirements= |
| 1510 | tencent | 2059655909721948160 | 腾讯 | Senior Business Development Manager | 深圳 | experience, education, salary, requirements | requirements= |
| 1534 | tencent | 2059142535267401728 | 腾讯 | 海外休闲IAP（二合）产品负责人 | 深圳 | experience, education, salary, requirements | requirements= |
| 1535 | tencent | 2059142528426491904 | 腾讯 | 海外休闲经典&创意IAA产品负责人 | 深圳 | experience, education, salary, requirements | requirements= |
| 1559 | tencent | 2056998430714281984 | 腾讯 | 游戏研发 Agent 产品策划 | 广州 | experience, education, salary, requirements | requirements= |
| 1572 | tencent | 2057315514178514944 | 腾讯 | PUBG MOBILE游戏运营（产品运营方向） | 深圳 | experience, education, salary, requirements | requirements= |
| 1573 | tencent | 2057315521069756416 | 腾讯 | PUBG MOBILE游戏运营（UGC运营方向） | 深圳 | experience, education, salary, requirements | requirements= |
| 1581 | tencent | 2057043698268684288 | 腾讯 | Talent Management & Organization Development Associate | 深圳 | experience, education, salary, requirements | requirements= |
| 1582 | tencent | 2056998436447895552 | 腾讯 | AI Agent开发工程师（游戏研发） | 广州 | experience, education, salary, requirements | requirements= |

### education（19525）

| 行号 | platform | job_id | company | title | location | 缺失字段 | 详情 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | tencent | 2059455036769091584 | 腾讯 | 混元 AI 产品经理（北京/深圳） | 北京 | education, salary, requirements | requirements= |
| 2 | tencent | 2028730347814027264 | 腾讯 | 高性能计算专家（深圳/北京） | 北京 | education, salary, requirements | requirements= |
| 3 | tencent | 2021054129127981056 | 腾讯 | 元宝-大模型策略产品经理（AIGC方向） | 北京 | education, salary, requirements | requirements= |
| 4 | tencent | 2021054127102132224 | 腾讯 | 元宝-大模型策略产品经理（AIGC方向） | 深圳 | education, salary, requirements | requirements= |
| 5 | tencent | 1942609674138394624 | 腾讯 | 微信-大模型算法专家岗 | 北京 | education, salary, requirements | requirements= |
| 6 | tencent | 2041324863637061632 | 腾讯 | 高级DCI网络架构师 | 深圳 | education, salary, requirements | requirements= |
| 7 | tencent | 2041324866405302272 | 腾讯 | 高级DCI网络架构师 | 北京 | education, salary, requirements | requirements= |
| 8 | tencent | 1993913280330096640 | 腾讯 | PUBG Mobile-高级技术策划-UGC方向 | 深圳 | education, salary, requirements | requirements= |
| 9 | tencent | 2046893561479331840 | 腾讯 | 魔方发行中心-海外资深投放经理 | 深圳 | education, salary, requirements | requirements= |
| 10 | tencent | 2027325894867185664 | 腾讯 | 微信基础-语音大模型算法工程师 | 北京 | education, salary, requirements | requirements= |
| 11 | tencent | 2049458030906621952 | 腾讯 | 游戏交互设计师 | 上海 | education, salary, requirements | requirements= |
| 12 | tencent | 2003030798634209280 | 腾讯 | 暖通工程师 | 深圳 | education, salary, requirements | requirements= |
| 13 | tencent | 1950026512501678080 | 腾讯 | 资深测试开发工程师（AI评测方向） | 北京 | education, salary, requirements | requirements= |
| 14 | tencent | 2016767263998365696 | 腾讯 | AI研效高级工程师 | 深圳 | education, salary, requirements | requirements= |
| 15 | tencent | 2046490171318366208 | 腾讯 | 《洛克王国：世界》-游戏策划-生态AI方向 | 深圳 | education, salary, requirements | requirements= |
| 16 | tencent | 2028671544670191616 | 腾讯 | supercell游戏-游戏策划-英雄设计方向 | 深圳 | education, salary, requirements | requirements= |
| 17 | tencent | 2028422699864457216 | 腾讯 | 魔方工作室-AI技术美术（美术向） | 深圳 | education, salary, requirements | requirements= |
| 18 | tencent | 2029725934701146112 | 腾讯 | 云原生算力平台运维工程师(深圳/北京) | 深圳 | education, salary, requirements | requirements= |
| 19 | tencent | 2029722833814450176 | 腾讯 | 和平精英-资深CG导演（商业化） | 深圳 | education, salary, requirements | requirements= |
| 20 | tencent | 2029046821149634560 | 腾讯 | 3D 动作游戏《狩》研发项目管理（版本PM/技术PM） | 深圳 | education, salary, requirements | requirements= |

### salary（22907）

| 行号 | platform | job_id | company | title | location | 缺失字段 | 详情 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | tencent | 2059455036769091584 | 腾讯 | 混元 AI 产品经理（北京/深圳） | 北京 | education, salary, requirements | requirements= |
| 2 | tencent | 2028730347814027264 | 腾讯 | 高性能计算专家（深圳/北京） | 北京 | education, salary, requirements | requirements= |
| 3 | tencent | 2021054129127981056 | 腾讯 | 元宝-大模型策略产品经理（AIGC方向） | 北京 | education, salary, requirements | requirements= |
| 4 | tencent | 2021054127102132224 | 腾讯 | 元宝-大模型策略产品经理（AIGC方向） | 深圳 | education, salary, requirements | requirements= |
| 5 | tencent | 1942609674138394624 | 腾讯 | 微信-大模型算法专家岗 | 北京 | education, salary, requirements | requirements= |
| 6 | tencent | 2041324863637061632 | 腾讯 | 高级DCI网络架构师 | 深圳 | education, salary, requirements | requirements= |
| 7 | tencent | 2041324866405302272 | 腾讯 | 高级DCI网络架构师 | 北京 | education, salary, requirements | requirements= |
| 8 | tencent | 1993913280330096640 | 腾讯 | PUBG Mobile-高级技术策划-UGC方向 | 深圳 | education, salary, requirements | requirements= |
| 9 | tencent | 2046893561479331840 | 腾讯 | 魔方发行中心-海外资深投放经理 | 深圳 | education, salary, requirements | requirements= |
| 10 | tencent | 2027325894867185664 | 腾讯 | 微信基础-语音大模型算法工程师 | 北京 | education, salary, requirements | requirements= |
| 11 | tencent | 2049458030906621952 | 腾讯 | 游戏交互设计师 | 上海 | education, salary, requirements | requirements= |
| 12 | tencent | 2003030798634209280 | 腾讯 | 暖通工程师 | 深圳 | education, salary, requirements | requirements= |
| 13 | tencent | 1950026512501678080 | 腾讯 | 资深测试开发工程师（AI评测方向） | 北京 | education, salary, requirements | requirements= |
| 14 | tencent | 2016767263998365696 | 腾讯 | AI研效高级工程师 | 深圳 | education, salary, requirements | requirements= |
| 15 | tencent | 2046490171318366208 | 腾讯 | 《洛克王国：世界》-游戏策划-生态AI方向 | 深圳 | education, salary, requirements | requirements= |
| 16 | tencent | 2028671544670191616 | 腾讯 | supercell游戏-游戏策划-英雄设计方向 | 深圳 | education, salary, requirements | requirements= |
| 17 | tencent | 2028422699864457216 | 腾讯 | 魔方工作室-AI技术美术（美术向） | 深圳 | education, salary, requirements | requirements= |
| 18 | tencent | 2029725934701146112 | 腾讯 | 云原生算力平台运维工程师(深圳/北京) | 深圳 | education, salary, requirements | requirements= |
| 19 | tencent | 2029722833814450176 | 腾讯 | 和平精英-资深CG导演（商业化） | 深圳 | education, salary, requirements | requirements= |
| 20 | tencent | 2029046821149634560 | 腾讯 | 3D 动作游戏《狩》研发项目管理（版本PM/技术PM） | 深圳 | education, salary, requirements | requirements= |

### requirements（1958）

| 行号 | platform | job_id | company | title | location | 缺失字段 | 详情 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | tencent | 2059455036769091584 | 腾讯 | 混元 AI 产品经理（北京/深圳） | 北京 | education, salary, requirements | requirements= |
| 2 | tencent | 2028730347814027264 | 腾讯 | 高性能计算专家（深圳/北京） | 北京 | education, salary, requirements | requirements= |
| 3 | tencent | 2021054129127981056 | 腾讯 | 元宝-大模型策略产品经理（AIGC方向） | 北京 | education, salary, requirements | requirements= |
| 4 | tencent | 2021054127102132224 | 腾讯 | 元宝-大模型策略产品经理（AIGC方向） | 深圳 | education, salary, requirements | requirements= |
| 5 | tencent | 1942609674138394624 | 腾讯 | 微信-大模型算法专家岗 | 北京 | education, salary, requirements | requirements= |
| 6 | tencent | 2041324863637061632 | 腾讯 | 高级DCI网络架构师 | 深圳 | education, salary, requirements | requirements= |
| 7 | tencent | 2041324866405302272 | 腾讯 | 高级DCI网络架构师 | 北京 | education, salary, requirements | requirements= |
| 8 | tencent | 1993913280330096640 | 腾讯 | PUBG Mobile-高级技术策划-UGC方向 | 深圳 | education, salary, requirements | requirements= |
| 9 | tencent | 2046893561479331840 | 腾讯 | 魔方发行中心-海外资深投放经理 | 深圳 | education, salary, requirements | requirements= |
| 10 | tencent | 2027325894867185664 | 腾讯 | 微信基础-语音大模型算法工程师 | 北京 | education, salary, requirements | requirements= |
| 11 | tencent | 2049458030906621952 | 腾讯 | 游戏交互设计师 | 上海 | education, salary, requirements | requirements= |
| 12 | tencent | 2003030798634209280 | 腾讯 | 暖通工程师 | 深圳 | education, salary, requirements | requirements= |
| 13 | tencent | 1950026512501678080 | 腾讯 | 资深测试开发工程师（AI评测方向） | 北京 | education, salary, requirements | requirements= |
| 14 | tencent | 2016767263998365696 | 腾讯 | AI研效高级工程师 | 深圳 | education, salary, requirements | requirements= |
| 15 | tencent | 2046490171318366208 | 腾讯 | 《洛克王国：世界》-游戏策划-生态AI方向 | 深圳 | education, salary, requirements | requirements= |
| 16 | tencent | 2028671544670191616 | 腾讯 | supercell游戏-游戏策划-英雄设计方向 | 深圳 | education, salary, requirements | requirements= |
| 17 | tencent | 2028422699864457216 | 腾讯 | 魔方工作室-AI技术美术（美术向） | 深圳 | education, salary, requirements | requirements= |
| 18 | tencent | 2029725934701146112 | 腾讯 | 云原生算力平台运维工程师(深圳/北京) | 深圳 | education, salary, requirements | requirements= |
| 19 | tencent | 2029722833814450176 | 腾讯 | 和平精英-资深CG导演（商业化） | 深圳 | education, salary, requirements | requirements= |
| 20 | tencent | 2029046821149634560 | 腾讯 | 3D 动作游戏《狩》研发项目管理（版本PM/技术PM） | 深圳 | education, salary, requirements | requirements= |

## description_too_short（20）

| 行号 | platform | job_id | company | title | location | 详情 |
| ---: | --- | --- | --- | --- | --- | --- |
| 5554 | feishu | 7593245670041471238 | 智谱AI | AI产品实习生-上海 | 上海 | requirements=-, url=https://zhipu-ai.jobs.feishu.cn/index/position/7593245670041471238/detail, length=2 |
| 5638 | feishu | 7527184302761855282 | 智谱AI | 产品测试 | 北京 | requirements=测试测试, url=https://zhipu-ai.jobs.feishu.cn/index/position/7527184302761855282/detail, length=8 |
| 21734 | jd | 217522 | 京东 | 人才储备岗 | 北京市 | requirements=人才储备  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, url=https://zhaopin.jd.com/web/job-info-detail?requementId=217522, length=38 |
| 21970 | jd | 219062 | 京东 | 关务运营岗 | 北京市 | requirements=关务运营  符合京东价值观：客户为先、创新、拼搏、担当、感恩、诚信。, url=https://zhaopin.jd.com/web/job-info-detail?requementId=219062, length=38 |
| 2685 | netease | 76904 | 网易 | 资深/高级游戏营销策划--燕云十六声 | 杭州市 | requirements=1, url=https://hr.163.com/job-detail.html?id=76904, length=2 |
| 2894 | netease | 68165 | 网易 | 广州程序类岗位专项 | 广州市 | requirements=服务器开发/客户端开发等, url=https://hr.163.com/job-detail.html?id=68165, length=24 |
| 71 | tencent | 2072873374673186816 | 腾讯 | 数值策划 | 深圳 | requirements=, url=http://careers.tencent.com/jobdesc.html?postId=2072873374673186816, length=43 |
| 244 | tencent | 2032007523309092864 | 腾讯 | QClaw-产品策划-AI工具方向 | 深圳 | requirements=, url=http://careers.tencent.com/jobdesc.html?postId=2032007523309092864, length=23 |
| 20983 | xiaohongshu | 18147 | 小红书 | 电商运营高阶 | 上海市 | requirements=/, url=https://job.xiaohongshu.com/social/position/18147, length=2 |
| 20995 | xiaohongshu | 18479 | 小红书 | 社区推荐策略产品经理 | 北京市，上海市 | requirements=推荐策略, url=https://job.xiaohongshu.com/social/position/18479, length=8 |

## description_and_requirements_empty（0）

无样例。

## invalid_or_missing_url（0）

无样例。

## duplicate_platform_job_id（0）

重复组数：0

无样例。

## suspected_duplicate_company_title_location（438）

重复组数：366

| 重复键 | 出现次数 | 行号 | URL |
| --- | ---: | --- | --- |
| title=腾讯乐享-saas产品售前解决方案架构师, location=深圳, company=腾讯, description=1.负责ai知识库产品商业化策略的制定； 2.负责所属行业的项目售前工作及其收入目标结果； 3.挖掘ai知识库产品目标客户的使用场景、需求等，并反哺产研团队。 | 2 | 100, 1137 | http://careers.tencent.com/jobdesc.html?postId=2029338866321883136<br>http://careers.tencent.com/jobdesc.html?postId=1983366206685601792 |
| title=游戏引擎开发工程师（移动端性能优化）, location=杭州市, company=网易, description=1. 根据项目需求定制移动端渲染管线（forward / deferred / tiled / clustered 等）,参与管线架构升级、图形 feature 评估与选型（如 msaa、实时阴影、后处理、bloom、ssr、ao 等）; 2. 深度优化移动平台的图形性能：包括 drawcall、overdraw、shader、带宽、缓存使用等;优化移动端资源加载、纹理压缩格式（astc/etc2）、streaming 使用效率等关键环节; 3. 解决 android/ios 端的兼容性问题（gpu差异、驱动bug、机型适配等); 4. 跟进芯片厂商（高通、mtk、apple、arm 等）文档与驱动变更，及时优化关键路径; 5. 开发与维护移动端渲染调试与分析工具链（frame profiler、gpu/cpu trace 工具集成）; 6. 推动团队对移动平台性能约束与规范的理解，指导资源/美术/策划的性能预算使用; | 2 | 2120, 3556 | https://hr.163.com/job-detail.html?id=76079<br>https://hr.163.com/job-detail.html?id=76078 |
| title=财务bp, location=上海, company=minimax, description=1. 作为业务的财务搭档，深入业务、参与经营会议，输出财务视角的判断与建议 2. 负责所辖业务线月度 p&l 编制、滚动预测与差异分析，驱动业务完成预算目标 3. 搭建业务经济模型，持续监控关键指标健康度 4. 主导业务预算编制与全过程管控，识别资源浪费与降本机会 5. 对业务新项目、新策略、新产品进行事前财务评估（投入产出 / roi / npv / 盈亏平衡），出具立项财务意见 6. 与业务共建关键业务规则（定价、返点、考核口径、激励机制等），确保业务动作与财务结果对齐 7. 向管理层定期输出经营分析报告，揭示风险、捕捉机会、推动改善 | 2 | 5332, 5349 | https://vrfi1sk8a0.jobs.feishu.cn/index/position/7651896987210664246/detail<br>https://vrfi1sk8a0.jobs.feishu.cn/index/position/7646753918701144347/detail |
| title=高级软件研发工程师, location=北京市, company=滴滴, description=1. 负责滴滴租车业务系统的架构设计及系统开发 2. 充分理解并深入挖掘业务需求，基于此制定前瞻性的系统规划，推动系统的持续进化 3. 具备较强的技术攻关能力，持续优化系统架构、性能和稳定性 | 2 | 5863, 5878 | https://talent.didiglobal.com/social/p/62233<br>https://talent.didiglobal.com/social/p/64063 |
| title=社区产品经理（抖省省）-抖音生活服务, location=北京, company=字节跳动, description=1、社区从0到1建设：主导「抖省省」本地吃喝玩乐内容社区的产品规划与架构设计，从发现美好生活、分享探店避坑的年轻化视角出发，打造高活跃、强种草、有温度的本地生活内容阵地； 2、产品创新与体验打磨：打破传统本地生活产品的工具感，探索图文、短视频、互动组件等多元化内容体裁与创新玩法（如个性化榜单、打卡地图、兴趣圈子等），为年轻用户提供有趣、有用且极致流畅的浏览与互动体验； 3、内容生态与分发策略：具备生态视角，协同运营制定创作者入驻与内容沉淀的产品机制，协同算法团队优化搜推联动策略（“推后搜”、“搜后推”），提升优质内容的分发效率及从“种草”到“到店/交易”的转化渗透率； 4、用户心理与趋势洞察：深入研究新时代及年轻客群在餐饮、休闲娱乐等领域的消费趋势与社交行为模式，将时下热点敏捷转化为产品落地； 5、数据驱动与跨组协同：建立社区健康度与业务漏斗转化指标体系，与运营、内容生态、推荐算法及商业化团队紧密配合，实现社区内容规模与商业变现的双向共赢。 | 2 | 6816, 10851 | https://jobs.bytedance.com/experienced/position/7631808185550096645/detail<br>https://jobs.bytedance.com/experienced/position/7631807594580363525/detail |
| title=databuilder 产品经理（j95916）, location=北京市, company=百度, description=-负责大模型应用数据准备平台整体规划、产品设计与落地运营，围绕数据采集、清洗、标注、治理、特征工程、向量数据构建等核心环节，制定ai 原生数据产品路线图与产品策略 -深度参与数据中台与数据治理体系建设，负责数据标准、元数据管理、数据质量、数据安全、数据权限等产品能力设计，构建面向大模型场景的高质量、高可信、高可用数据底座 -开展市场与用户调研，挖掘业务侧、算法侧、研发侧对大模型数据加工、数据治理、数据服务的真实需求，输出高质量 prd 与产品方案，持续提升数据产品易用性与效率 -协同数据研发、ai 工程、架构、测试、市场、销售等团队，推动数据中台能力、数据治理工具、大模型数据平台的研发落地、联调测试与上线交付 -负责产品上线后数据埋点、效果跟踪与深度数据分析，围绕数据产出效率、数据质量、模型效果等指标持续迭代优化 -配合市场与销售团队，输出产品方案、最佳实践与客户化支撑，推动数据产品与 ai 能力的商业化落地与推广 | 2 | 16183, 16185 | https://talent.baidu.com/jobs/detail/SOCIAL/4cf88973-571c-4dd8-8e17-229eb1bbf7e7<br>https://talent.baidu.com/jobs/detail/SOCIAL/80e86000-3c46-422d-b864-28e8d2fa17cb |
| title=小象超市-北京空间设计师, location=北京市, company=美团, description=1. 全流程开站设计：负责服务站/前置仓的开站设计全过程，包括现场勘测、平面方案设计、全套施工图（含装饰、机电、暖通、给排水、消防等专业）的出图与项目设计跟踪落地； 2. 设计标准化建设：主导建立和迭代服务站设计标准库（含不同仓型、面积段的标准模块），实现设计资产复用，缩短单站出图周期； 3. ai辅助设计提效：运用ai效果图生成工具（midjourney/sd/interior ai等）快速产出概念方案，辅助使用bim工具（revit）进行多专业碰撞检测，减少施工阶段变更； 4. 数据驱动设计迭代：结合运营数据（坪效/拣货动线效率/顾客行为热力图），定期复盘现有仓型设计方案，输出量化改善建议，推动设计标准版本升级； 5. 项目管理与交付保障：统筹管理多站点并行设计项目，制定项目计划，协调设计与工程施工节奏，保障开仓时间节点； 6. 跨部门协作推进：深入理解业务变化，与运营、商品、工程等团队协作，将业务痛点转化为设计解决方案，驱动服务站生产力持续提升； 7. 整改与专项支持：承接存量站点整改任务及公司专项设计工作，确保改造方案合规且高效落地。 岗位亮点 1.新零售行业巨大的发展潜力。 2.项目的全过程与全专业设计参与，拓宽个人能力范围。 3. 从ai效果图快速出方案，到数字孪生预演仓型，我们鼓励每一位设计师探索ai提效的可能性。 | 2 | 17729, 18756 | https://zhaopin.meituan.com/web/position/detail?jobUnionId=4603984193&highlightType=social<br>https://zhaopin.meituan.com/web/position/detail?jobUnionId=4478060546&highlightType=social |
| title=结算产品经理-【生活服务】, location=北京, company=快手, description=1、负责生活服务业务交易的账户、计费、分账、结算、发票、保证金、返佣相关能力设计和完善，对结算时效、准确性、安全性负责，对商家、达人、服务商的对账体验负责； 2、通过对业务和产品痛点分析，制定产品具体目标和相应的路径拆解，设计完整闭环的解决方案； 3、对上下游有清晰认知，对接业务及财务，保障数据的一致性和准确性，实现新业务的线上化计费和结算； 4、通过数据分析提炼、客户需求挖掘等手段不断优化产品性能，达成提效降本目标。 | 2 | 19385, 19396 | https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/30196<br>https://zhaopin.kuaishou.cn/recruit/e/#/official/social/job-info/20837 |
| title=湖仓专家, location=北京市，上海市，杭州市, company=小红书, description=1. 主导云原生数据湖架构设计与落地，参与公司湖仓链路建设，支撑bi+ai业务场景。 2. 基于湖仓架构，完善相关的生态和产品，提供更低成本、更高效率的数据开发范式。 3. 和开源社区保持沟通合作，提升团队和个人在业界的影响力。 | 2 | 21109, 21119 | https://job.xiaohongshu.com/social/position/20493<br>https://job.xiaohongshu.com/social/position/18237 |
| title=测试开发工程师, location=上海市, company=京东, description=1、负责测试开发工作，基于深入的业务理解，进行测试流程优化与自动化测试工具的开发，以提高产品质量及发布效率； 2、根据产品特性，设计并实施测试策略和计划，保证软件质量满足业务需求，降低潜在风险； 3、研究并引入先进的测试方法和工具（如：ai），提升测试效率，推动团队技术能力的提升； 4、与项目团队紧密配合，通过有效的沟通确保测试活动与项目进度同步，达成项目质量目标； 5、对测试过程中发现的问题进行深入分析，提出改进建议，协助开发团队优化产品架构和代码质量； 6、持续总结测试经验，构建知识库，促进团队间的知识共享和技能提升； 7、熟悉ai，有ai经验 | 2 | 21624, 22542 | https://zhaopin.jd.com/web/job-info-detail?requementId=220139<br>https://zhaopin.jd.com/web/job-info-detail?requementId=216342 |
