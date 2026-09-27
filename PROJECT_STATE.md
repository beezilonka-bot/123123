# Project State

## 当前版本
v0.3.0

## 当前阶段
STAGE-003 — 信息雷达闭环：RSS → Event → Trend → LLM Analysis

## 已完成
- 创建新公开仓库 123123
- 确立产品方向：移动端 X 一键推文生成器
- 确立先做“信息分析器 / 信息雷达”的开发顺序
- 确立采用成熟开源项目组合，而不是从零实现全部能力
- 建立项目目标、拓扑、开发顺序和工作规则
- 完成第一版开源方案地图
- 完成最小 RSS/Atom Collector
- 完成 Event Cluster 与可解释 Trend Signal
- 建立 PostgreSQL 持久化：sources、items、events、trend_signals
- 已迁移到用户自有服务器部署，不再依赖 Render Cron
- 接入 OpenAI-compatible LLM 分析层
- Tierflow 已配置为默认 LLM endpoint：/v1
- 默认 Radar 分析模型：Qwen3.8-Flash
- API Key 从服务器受保护的 key file 读取，不写入仓库
- 建立 event_analyses 持久化
- 真实服务器运行验证成功：一次采集 37 items、36 events，并完成 5 个 LLM analyses
- 修复 Event ID：改为基于最早事件 item 的稳定身份，而不是代表标题指纹

## 已验证
- 服务器 Python 代码可编译
- PostgreSQL 连接正常
- RSS 实际采集正常
- Tierflow /v1/models 可用
- Qwen3.8-Flash 实际完成事件分析
- LLM 输出包含 importance、why_it_matters、who_cares、key_facts、uncertainty、tags、suggested_angles
- 分析结果成功写入 PostgreSQL

## 当前已知问题
- 历史数据库中仍存在旧 Event ID，因此短期内可能看到同一事件的旧记录与新记录并存。
- velocity 当前仍是基于当前事件体量的近似信号，还不是历史时间窗口速度。
- RSS 来源目前只有 BBC News 与 NPR News。
- /collect 尚未做鉴权；后续需要通过服务器内部调度或 token/Nginx 限制访问。

## 下一步
STAGE-003B — 让 Radar 真正回答“今天最值得写什么”

1. 清理/合并历史重复 Event。
2. 用数据库历史 snapshot 计算真实 velocity。
3. 将 LLM analysis 转换成 content_opportunities 并持久化。
4. 扩展 RSS 来源与来源质量字段。
5. 用服务器 cron/systemd timer 替代旧 GitHub Actions 调度。
6. 然后进入个人账号历史表现分析与一键推文生成。
