# Radar 最小数据模型

STAGE-002A：设计最小数据模型。

目标：用最少的数据结构支撑“RSS/Atom → 标准化 → 去重 → 事件聚类 → 趋势信号 → LLM 分析 → 今日内容机会”。

## 1. Source

表示一个信息源。

- id：内部稳定 ID
- name：来源名称
- url：feed URL
- type：rss | atom
- enabled：是否启用
- fetch_interval：建议抓取间隔
- credibility：来源质量基础值（可选，默认值即可）

第一版不做复杂 source profile。

## 2. Item

表示一次采集到的原始内容。

- id
- source_id
- url
- canonical_url
- title
- summary
- content：可选
- author：可选
- published_at
- fetched_at
- language：可选
- raw_hash

### 去重键

第一层 Exact Dedup：

1. canonical_url
2. URL 规范化后的 hash
3. title + source + published_at 的辅助 hash

不要仅用标题去重，因为同一事件可能来自同一来源的不同报道。

## 3. Event

表示多个 Item 共同描述的一个事件。

- id
- representative_item_id
- title
- summary
- first_seen_at
- latest_seen_at
- item_count
- source_count
- cluster_key
- status：active | stale

Event 是趋势分析的核心对象，而不是 URL。

## 4. TrendSignal

表示事件的可解释趋势信号。

- event_id
- freshness
- velocity
- source_count
- item_count
- novelty
- relevance
- total_score
- calculated_at

第一版不要使用黑盒权重。

建议先使用可解释的归一化规则：

- freshness：越新越高
- velocity：单位时间新增报道越多越高
- source_count：独立来源越多越高
- novelty：近期首次出现越高
- relevance：由用户主题配置计算

## 5. EventAnalysis

LLM 对 Event 的分析结果。

- event_id
- importance
- why_it_matters
- who_cares
- key_facts
- uncertainty
- tags
- suggested_angles
- analyzed_at
- model

LLM 只处理已经聚类和预筛选后的 Event。

## 6. ContentOpportunity

最终给推文生成器消费的内容机会。

- id
- event_id
- title
- why_now
- audience
- angle
- suggested_format
- priority
- created_at
- expires_at

它回答的问题是：

> 今天有什么值得写？为什么现在值得写？可以从什么角度写？

## 7. 最小关系

Source 1 → N Item

Item N → 1 Event

Event 1 → 1 TrendSignal（当前快照）

Event 1 → N EventAnalysis（允许重新分析）

Event 1 → N ContentOpportunity

## 8. 第一版明确不做

- 不保存完整网页正文作为核心数据依赖
- 不做复杂知识图谱
- 不做向量数据库
- 不做复杂 Agent memory
- 不做 X 官方推荐权重模拟
- 不做复杂实时流处理
- 不做多租户权限系统

先把真实 RSS 数据稳定进入 Event 层。

## 9. Phase 2 最小数据库对象

第一版只需要：

`sources`
`items`
`events`
`trend_signals`
`event_analyses`
`content_opportunities`

Collector 可以先输出标准 JSON，再接数据库，避免在 RSS 解析尚未稳定时过早绑定数据库实现。
