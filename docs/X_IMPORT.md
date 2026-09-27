# X 历史数据导入

## 目的

本项目不接入付费 X API。账号历史表现通过用户自己提供的数据文件导入。

## 支持格式

- CSV
- JSON

接口：

`POST /account/import?format=csv`

或：

`POST /account/import?format=json`

请求体直接放文件内容。

## 常见字段

正文：

- text
- full_text
- content

帖子 ID：

- id
- post_id
- tweet_id
- tweetId

发布时间：

- published_at
- created_at
- createdAt
- date
- timestamp

指标：

- impressions / views
- likes
- replies
- reposts / retweets
- bookmarks
- quotes
- profile_visits

字段只是兼容映射，不代表某个字段一定存在于官方导出文件。

## 数据原则

- 有什么保存什么。
- 缺失指标保存为 NULL。
- 不把缺失指标当作真实的 0。
- 不模拟 X 官方推荐算法。
- 表现分析只使用实际导入的数据。
- 用户不需要把 X 密码、API Key 或 OAuth Token 提供给本项目。

## 当前接口

`GET /account/performance` 返回已导入账号数据的基础表现汇总。

导入接口在增加鉴权前，不应直接对公网开放。
