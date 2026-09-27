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
