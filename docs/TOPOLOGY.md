# 系统拓扑

## 总体拓扑

Mobile App
  │
  │ HTTPS
  ▼
Backend / API
  ├────────────── Information Radar
  │                 ├─ RSS / Web / Social / Sources
  │                 ├─ Normalize
  │                 ├─ Dedup / Event Cluster
  │                 └─ Trend / Rank / Opportunity
  │
  └────────────── Post Engine
                    ├─ Personal Style
                    ├─ Audience
                    ├─ User History
                    ├─ LLM Reasoning + Generation
                    ├─ De-AI / Edit / Format
                    └─ Optional Image Generation

## 数据流

外部信息
→ 采集
→ 标准化
→ 去重 / 事件聚类
→ 新鲜度 + 传播速度 + 讨论度 + 来源质量 + 用户相关度
→ 今日信息排名
→ 内容机会池
→ 一键生成

## 重要边界

- 信息雷达负责“发现和分析”。
- Post Engine 负责“研究、推理、写作”。
- 图片是最后的可选步骤。
- X 平台分析负责学习用户自己的历史表现，不假定知道官方内部权重。
- 手机端负责体验；复杂计算放后端。
