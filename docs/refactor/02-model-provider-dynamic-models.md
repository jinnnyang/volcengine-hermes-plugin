# 02. 模型 Provider 与动态模型列表方案

## 1. 目标

重构 `plugins/model-providers/volcengine`，让它：

- 兼容 Agent Plan、Coding Plan、普通 Ark API。
- 默认使用 `/api/plan/v3`。
- 允许通过环境变量或安装脚本切换 endpoint。
- 动态拉取模型列表。
- Hermes 用户可以选择模型。
- 用户也可以手动输入任意 model id。
- 保留 `ark-code-latest` 和历史 alias。

## 2. ProviderProfile 设计

Provider canonical name：

```text
volcengine
```

建议 aliases：

```python
aliases=(
    "doubao",
    "volcengine-agent-plan",
    "volcengine-coding-plan",
    "volces-engine",
)
```

建议字段：

```python
ProviderProfile(
    name="volcengine",
    aliases=(...),
    display_name="Volcengine Ark / Doubao",
    description="Volcengine Ark-compatible API for Agent Plan, Coding Plan, and pay-as-you-go Ark API.",
    signup_url="https://console.volcengine.com/ark/",
    env_vars=("VOLCENGINE_API_KEY", "ARK_API_KEY", "VOLCENGINE_BASE_URL", "VOLCENGINE_PLAN_MODE"),
    base_url="https://ark.cn-beijing.volces.com/api/plan/v3",
    auth_type="api_key",
    api_mode="chat_completions",
    default_aux_model="doubao-seed-2.0-lite",
    fallback_models=(...),
)
```

## 3. Endpoint 解析

### 环境变量

```bash
VOLCENGINE_PLAN_MODE=agent|coding|api
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/plan/v3
```

解析优先级：

```text
1. VOLCENGINE_BASE_URL，如果存在则直接使用
2. VOLCENGINE_PLAN_MODE
3. 默认 agent mode
```

映射：

```python
MODE_BASE_URLS = {
    "agent": "https://ark.cn-beijing.volces.com/api/plan/v3",
    "coding": "https://ark.cn-beijing.volces.com/api/coding/v3",
    "api": "https://ark.cn-beijing.volces.com/api/v3",
}
```

接受 alias：

```text
agent, agent_plan, plan
coding, coding_plan
api, ark, payg, pay_as_you_go
```

非法值处理：

- 不直接崩溃。
- fallback 到 agent mode。
- 在日志或错误提示里说明合法值。

## 4. API Key 解析

优先级：

```text
VOLCENGINE_API_KEY > ARK_API_KEY
```

原因：

- 当前仓库已有 `VOLCENGINE_API_KEY`。
- 火山官方示例常用 `ARK_API_KEY`。
- 两者都保留可减少迁移成本。

## 5. 动态模型列表

### 第一阶段：OpenAI-compatible `/models`

对 resolved base URL 请求：

```http
GET {base_url}/models
Authorization: Bearer <api_key>
```

预期兼容 OpenAI 格式：

```json
{
  "object": "list",
  "data": [
    {"id": "doubao-seed-2.0-lite", "object": "model"}
  ]
}
```

解析规则：

- 优先读取 `data[].id`。
- 忽略没有 id 的条目。
- 去重并保留原顺序。
- 如果请求失败、超时、返回非 JSON 或 data 为空，则使用 fallback list。

### 第二阶段：Agent/Coding Plan 管控 API

火山可能存在面向套餐的模型列表 OpenAPI，例如：

- `ListArkAgentPlanModel`
- `ListArkCodingPlanModel`

它们可能不走 OpenAI-compatible `/models`，鉴权和 endpoint 也可能不同。

建议第二阶段再接入，避免第一阶段把 provider 复杂化。

## 6. 缓存策略

为避免每次启动都请求 `/models`，建议增加简单缓存。

候选位置：

```text
~/.hermes/cache/volcengine/models.json
```

缓存内容：

```json
{
  "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3",
  "fetched_at": "2026-06-24T00:00:00Z",
  "models": ["ark-code-latest", "doubao-seed-2.0-lite"]
}
```

TTL：

```text
默认 24 小时
```

环境变量：

```bash
VOLCENGINE_MODELS_CACHE_TTL_SECONDS=86400
VOLCENGINE_DISABLE_MODEL_CACHE=1
```

缓存行为：

1. 有新鲜缓存：直接返回。
2. 无缓存或过期：请求 `/models`。
3. 请求成功：写缓存。
4. 请求失败：如果有旧缓存，返回旧缓存并提示；否则 fallback。

## 7. Fallback 模型列表

建议 fallback list：

```python
FALLBACK_MODELS = (
    "ark-code-latest",
    "doubao-seed-2.0-code",
    "doubao-seed-2.0-pro",
    "doubao-seed-2.0-lite",
    "doubao-seed-2.0-mini",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "glm-5.2",
    "kimi-k2.6",
    "kimi-k2.7-code",
    "minimax-m2.7",
    "minimax-m3",
)
```

注意：不同套餐、不同账号、不同 endpoint 下可用模型可能不同。fallback list 只用于展示与兜底，不代表用户一定有权限调用。

## 8. 用户手动输入模型

必须允许用户输入任意 model id。

理由：

- 普通 Ark API 的 endpoint/model id 高度依赖用户实际开通情况。
- 新模型发布速度快，插件 fallback list 不可能永远最新。
- 企业用户可能有自定义 endpoint 或私有模型。

文档建议说明：

> 如果模型不在列表中，可以直接输入火山控制台显示的模型 ID。插件不会阻止未知模型 ID，请求失败时以 API 返回为准。

## 9. Hermes model picker 集成预期

根据 Hermes model provider 文档，provider 注册后应被：

- `hermes model`
- `hermes setup`
- `hermes doctor`
- runtime provider resolver

识别。

需要验证：

```bash
hermes model
hermes doctor
hermes config get model
```

## 10. 验收标准

- 默认 base URL 是 `/api/plan/v3`。
- `VOLCENGINE_PLAN_MODE=coding` 后 base URL 是 `/api/coding/v3`。
- `VOLCENGINE_PLAN_MODE=api` 后 base URL 是 `/api/v3`。
- `VOLCENGINE_BASE_URL` 优先级最高。
- fallback models 包含 `ark-code-latest`。
- 动态 `/models` 成功时使用 API 返回。
- 动态 `/models` 失败时 fallback。
- 用户可手动配置未知 model id。
