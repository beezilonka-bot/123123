# 开源方案地图

STAGE-001：开源方案侦察与选型。

重点候选：FreshRSS、feeds.fun、ClawFeed、AI News Radar、DailyBrief、TrendRadar、TrendSonar、FeedCraft、XActions、x-tweet-scraper。

方向：RSS采集 → 标准化 → 去重 → 事件聚类 → 趋势评分 → LLM分析 → 今日内容机会；X数据作为可替换适配器。

本阶段先研究，不复制第三方代码。真正集成前核对许可证、API条款和数据来源条款。


## STAGE-001B 核验结果（第一批）

### FreshRSS/FreshRSS
- LICENSE：GNU AGPL v3。
- 定位：成熟的自托管 RSS 聚合器。
- 结论：适合研究 feed 管理、抓取、存储与订阅模型；不直接作为本项目核心依赖，原因是 AGPL 的网络服务义务需要单独评估。

### sansan0/TrendRadar
- LICENSE：GNU GPL v3。
- 定位：多平台热点、RSS 与趋势监测。
- 结论：适合研究热点采集、排序、推送与配置方式；不直接复制进核心服务，先借鉴设计。

### Thysrael/Horizon
- LICENSE：MIT。
- 定位：AI-powered news radar；公开资料显示支持 RSS/Atom、GitHub，并提供抓取、去重、评分、过滤和 enrichment 思路。
- 结论：目前是最值得深入阅读的候选之一。MIT 允许更灵活的代码复用，但仍需检查依赖许可证和具体实现。

### nirholas/XActions
- LICENSE：Apache License 2.0。
- 定位：X/Twitter 自动化、scraper、CLI 与 MCP 工具；公开文档展示 profile、tweets、search 等能力。
- 结论：可作为 X 数据适配器和数据结构研究对象；不把 scraper 当作产品长期数据供应保证，需单独评估 X 平台条款与稳定性。

## 第一轮选择

当前保留三个重点研究方向：
1. Horizon：重点研究信息雷达 pipeline。
2. TrendRadar：重点研究趋势/热点层。
3. XActions：重点研究 X 数据适配器。

FreshRSS 保留为 RSS 基础设施参考，不作为第一版核心依赖。

下一小阶段：继续核验 Horizon 与 TrendRadar 的目录结构、评分/去重实现和数据流，然后再确定 Phase 2 技术组合。


## STAGE-001B 第二轮：内部机制核验

### Horizon
公开源码文档确认其核心链路为：
- Profile resolution
- 内容准备（限制分析字符数、sampling，并加入 comments/engagement metadata）
- LLM profile analysis
- JSON 校验与失败重试
- profile threshold filtering
- topic deduplication
- category quotas / final item cap
- enrichment

其评分不是固定的全局新闻分数，而是**按 profile 定义 rubric**，输出 0–10 分、原因、摘要和 tags。配置还支持时间窗口、并发度和 topic_dedup。

对 123123 的启发：保留“采集后先筛选/聚类，再让 LLM 做深分析”的分层思想；不要照搬 Horizon 的 profile/enrichment 全套系统。

### TrendRadar
当前公开资料确认：
- 项目目标是轻量热点监测；
- 支持多平台热点与 RSS；
- 支持 AI 分析、AI 智能筛选；
- 支持关键词配置，并提供关键词共现分析；
- README 当前版本标为 v6.10.0；
- 数据获取还依赖 newsnow API，因此其数据供应链不能直接等同于我们的长期数据层。

对 123123 的启发：可以借鉴“热点源 + RSS + 关键词/相关性 + AI 分析”的组合，但 Phase 2 仍应从我们可控的 RSS/Atom 源开始。

### 当前技术结论
Phase 2 最小闭环暂定：

RSS/Atom → Normalize → Exact Dedup → Event Cluster → 基础趋势信号 → LLM Event Analysis → Today's Opportunities

其中：
- Exact Dedup 先处理 URL/规范化标题等确定性重复；
- Event Cluster 再处理“不同文章讲同一事件”；
- 基础趋势信号先使用 freshness、source_count、velocity 等可解释信号；
- LLM 负责事件理解、重要性解释、受众相关性和内容机会提取；
- 暂不引入复杂 Agent、复杂推荐模型或假设性的 X 官方权重。

下一阶段：建立 123123 自己的最小 radar 数据模型和 RSS collector，先跑通真实数据，再迭代评分。
