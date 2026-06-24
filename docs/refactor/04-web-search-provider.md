# 04. Volcengine Web Search Provider 方案

## 1. 目标

新增 Hermes Web Search Provider Plugin：

```text
plugins/web/volcengine/
```

让豆包搜索成为 Hermes 标准 `web_search` backend，达到 Tavily-like 使用体验。

用户配置后仍然调用：

```text
web_search(query="...", limit=5)
```

但底层 provider 是：

```text
Volcengine Doubao Search
```

## 2. 为什么不是 MCP 主线

MCP/官方 server 可以作为备选接入方式，但不是本仓库主线。

原因：

- MCP 会暴露额外工具，而不是 Hermes 标准 `web_search` backend。
- 用户和模型看到的是 MCP tool 名称，不是统一 `web_search`。
- Tavily-like 体验应通过 Hermes `WebSearchProvider` 实现。

因此主线是 direct API provider。

## 3. Hermes WebSearchProvider 接口

根据 Hermes 最新文档和源码，provider 应继承：

```python
from agent.web_search_provider import WebSearchProvider
```

实现：

```python
class VolcengineWebSearchProvider(WebSearchProvider):
    @property
    def name(self) -> str:
        return "volcengine"

    @property
    def display_name(self) -> str:
        return "Volcengine Doubao Search"

    def is_available(self) -> bool:
        return bool(resolve_search_api_key())

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False

    def search(self, query: str, limit: int = 5) -> dict:
        ...
```

注册：

```python
def register(ctx):
    ctx.register_web_search_provider(VolcengineWebSearchProvider())
```

## 4. plugin.yaml

建议：

```yaml
name: web-volcengine
version: 0.1.0
description: Volcengine Doubao Search backend for Hermes web_search
author: jinnnyang
kind: backend
provides_web_providers:
  - volcengine
```

是否写 `requires_env` 要谨慎。因为 provider 支持多个 env var fallback，如果 manifest 强制某一个变量，可能误伤已有用户。

建议第一版不使用强制 `requires_env`，改由 `get_setup_schema()` 提供 setup 提示。

## 5. API Key 解析

官方 skill 使用：

```text
WEB_SEARCH_API_KEY
```

本插件建议优先级：

```text
VOLCENGINE_SEARCH_API_KEY
WEB_SEARCH_API_KEY
ASK_ECHO_SEARCH_INFINITY_API_KEY
VOLCENGINE_API_KEY
ARK_API_KEY
```

含义：

| 环境变量 | 用途 |
|---|---|
| `VOLCENGINE_SEARCH_API_KEY` | 本插件推荐名称 |
| `WEB_SEARCH_API_KEY` | 兼容官方 byted-web-search skill |
| `ASK_ECHO_SEARCH_INFINITY_API_KEY` | 兼容官方 MCP server 命名 |
| `VOLCENGINE_API_KEY` | 兼容当前仓库 |
| `ARK_API_KEY` | 兼容火山 Ark 用户习惯 |

## 6. 豆包搜索 direct API schema

已从官方 skill `C:\Users\jinnn\.agents\skills\byted-web-search` 分析确认。

### Endpoint

推荐 API Key / Bearer 方式：

```http
POST https://open.feedcoopapi.com/search_api/web_search
```

Headers：

```http
Content-Type: application/json
Authorization: Bearer <api_key>
X-Traffic-Tag: skill_web_search_common
```

### Web 搜索请求

最小请求：

```json
{
  "Query": "Hermes Agent 火山方舟",
  "SearchType": "web",
  "Count": 5,
  "NeedSummary": true
}
```

带过滤与改写：

```json
{
  "Query": "最近一周 火山方舟 Agent Plan",
  "SearchType": "web",
  "Count": 10,
  "NeedSummary": true,
  "Filter": {
    "AuthInfoLevel": 1
  },
  "TimeRange": "OneWeek",
  "QueryControl": {
    "QueryRewrite": true
  }
}
```

字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `Query` | string | 搜索词，建议 1–100 字符 |
| `SearchType` | string | `web` 或 `image`，provider 第一版固定 `web` |
| `Count` | int | web 最多 50，来自 Hermes `limit` |
| `NeedSummary` | bool | web 搜索默认 true |
| `Filter.AuthInfoLevel` | int | `1` 表示权威来源过滤 |
| `TimeRange` | string | `OneDay` / `OneWeek` / `OneMonth` / `OneYear` / 日期区间 |
| `QueryControl.QueryRewrite` | bool | 开启 query rewrite |

### 响应结构

官方 skill 读取：

```python
result = data.get("Result", {})
error = (data.get("ResponseMetadata") or {}).get("Error")
```

预期形态：

```json
{
  "Result": {
    "ResultCount": 5,
    "TimeCost": 123,
    "WebResults": [
      {
        "SortId": 1,
        "Title": "标题",
        "SiteName": "来源站点",
        "AuthInfoDes": "权威来源说明",
        "Url": "https://example.com",
        "Summary": "摘要",
        "Snippet": "片段"
      }
    ]
  },
  "ResponseMetadata": {
    "Error": null
  }
}
```

## 7. Hermes 结果映射

Hermes `web_search` 返回格式：

```python
{
    "success": True,
    "data": {
        "web": [
            {
                "title": str,
                "url": str,
                "description": str,
                "position": int,
            }
        ]
    }
}
```

映射规则：

```python
title = item.get("Title", "")
url = item.get("Url", "")
summary = item.get("Summary") or item.get("Snippet") or ""
meta = " | ".join(x for x in [item.get("SiteName"), item.get("AuthInfoDes")] if x)
description = f"{meta}\n{summary}" if meta else summary
position = item.get("SortId") or index + 1
```

## 8. 错误处理

API 错误：

```json
{
  "ResponseMetadata": {
    "Error": {
      "Code": "10403",
      "Message": "invalid_api_key"
    }
  }
}
```

映射：

```python
{
    "success": False,
    "error": "Volcengine Doubao Search API Error [10403]: invalid_api_key"
}
```

常见错误码：

| 错误码/信息 | 含义 |
|---|---|
| `10400` | 参数错误 |
| `10402` | 搜索类型非法 |
| `10403` / `invalid_api_key` | Key 无效或类型不对 |
| `10406` | 免费额度耗尽 |
| `10407` | 无可用免费策略 |
| `10408` / `FunctionUnavailable` | 欠费 |
| `10409` | 套餐不支持该类型 |
| `10412` | 套餐额度不足 |
| `10500` | 服务内部错误 |
| `429` / `FlowLimitExceeded` / `100018` | 请求过快 |
| `700429` | 免费链路限流 |
| `100013` | 子账号未授权 |

## 9. get_setup_schema

为了接近 Tavily-like setup 体验，provider 应实现：

```python
def get_setup_schema(self) -> dict:
    return {
        "name": "Volcengine Doubao Search",
        "badge": "search",
        "tag": "Official Volcengine Doubao Search backend for Hermes web_search.",
        "env_vars": [
            {
                "key": "VOLCENGINE_SEARCH_API_KEY",
                "prompt": "Volcengine Doubao Search API key",
                "url": "https://console.volcengine.com/search-infinity/api-key",
            }
        ],
    }
```

安装脚本也可以设置：

```bash
hermes plugins enable web-volcengine
hermes config set web.search_backend volcengine
hermes tools enable web
```

## 10. 第一版边界

第一版做：

- `web` 搜索。
- API Key Bearer direct API。
- `Count` 映射 `limit`，上限 50。
- `NeedSummary=true`。
- 可选环境变量控制：
  - `VOLCENGINE_SEARCH_AUTH_LEVEL=1`
  - `VOLCENGINE_SEARCH_TIME_RANGE=OneWeek`
  - `VOLCENGINE_SEARCH_QUERY_REWRITE=true`
- 错误码友好提示。
- mock 测试。

第一版不做：

- image search 暴露到标准 `web_search`。
- AK/SK 签名路径。
- 专业数据集搜索。
- MCP server 包装。

## 11. 后续专业数据集搜索

专业数据集搜索不一定适合塞进标准 `web_search`。

后续建议单独设计普通 Hermes tool：

```text
volcengine_dataset_search
```

可能参数：

```json
{
  "query": "...",
  "dataset_id": "...",
  "limit": 5,
  "filters": {}
}
```

实现前需要确认专业数据集搜索 direct API schema。
