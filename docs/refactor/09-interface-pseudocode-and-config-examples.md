# 09. 接口伪代码与配置示例汇总

本文件集中放置实现阶段会用到的接口伪代码和配置样例，便于后续按 TDD 实现。

## 1. Endpoint resolver

```python
from __future__ import annotations

import os

DEFAULT_REGION_BASE = "https://ark.cn-beijing.volces.com"

MODE_TO_PATH = {
    "agent": "/api/plan/v3",
    "agent_plan": "/api/plan/v3",
    "plan": "/api/plan/v3",
    "coding": "/api/coding/v3",
    "coding_plan": "/api/coding/v3",
    "api": "/api/v3",
    "ark": "/api/v3",
    "payg": "/api/v3",
    "pay_as_you_go": "/api/v3",
}


def resolve_volcengine_base_url() -> str:
    explicit = os.getenv("VOLCENGINE_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")

    mode = os.getenv("VOLCENGINE_PLAN_MODE", "agent").strip().lower()
    path = MODE_TO_PATH.get(mode, MODE_TO_PATH["agent"])
    return DEFAULT_REGION_BASE + path


def volcengine_endpoint(suffix: str) -> str:
    return resolve_volcengine_base_url().rstrip("/") + "/" + suffix.lstrip("/")
```

## 2. API key resolver

```python
import os


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def resolve_volcengine_api_key() -> str | None:
    return first_env("VOLCENGINE_API_KEY", "ARK_API_KEY")


def resolve_volcengine_search_api_key() -> str | None:
    return first_env(
        "VOLCENGINE_SEARCH_API_KEY",
        "WEB_SEARCH_API_KEY",
        "ASK_ECHO_SEARCH_INFINITY_API_KEY",
        "VOLCENGINE_API_KEY",
        "ARK_API_KEY",
    )


def resolve_volcengine_speech_api_key() -> str | None:
    return first_env("VOLCENGINE_SPEECH_API_KEY", "VOLCENGINE_API_KEY", "ARK_API_KEY")
```

## 3. Dynamic models

```python
from __future__ import annotations

from typing import Iterable

import httpx

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


def dedupe_keep_order(values: Iterable[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def fetch_remote_models(base_url: str, api_key: str) -> list[str]:
    response = httpx.get(
        base_url.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    return dedupe_keep_order(item.get("id") for item in payload.get("data", []) or [])


def get_models_for_picker() -> list[str]:
    base_url = resolve_volcengine_base_url()
    api_key = resolve_volcengine_api_key()
    if api_key:
        try:
            models = fetch_remote_models(base_url, api_key)
            if models:
                return models
        except Exception:
            pass
    return list(FALLBACK_MODELS)
```

## 4. Model provider profile sketch

```python
from providers import register_provider
from providers.base import ProviderProfile

volcengine = ProviderProfile(
    name="volcengine",
    aliases=(
        "doubao",
        "volcengine-agent-plan",
        "volcengine-coding-plan",
        "volces-engine",
    ),
    display_name="Volcengine Ark / Doubao",
    description="OpenAI-compatible Volcengine Ark provider for Agent Plan, Coding Plan, and pay-as-you-go API.",
    signup_url="https://console.volcengine.com/ark/",
    env_vars=("VOLCENGINE_API_KEY", "ARK_API_KEY", "VOLCENGINE_BASE_URL", "VOLCENGINE_PLAN_MODE"),
    base_url=resolve_volcengine_base_url(),
    auth_type="api_key",
    api_mode="chat_completions",
    default_aux_model="doubao-seed-2.0-lite",
    fallback_models=FALLBACK_MODELS,
)

register_provider(volcengine)
```

## 5. Image provider payload sketch

```python
def build_image_payload(prompt: str, model: str, aspect_ratio: str) -> dict:
    size_by_ratio = {
        "landscape": "2560x1440",
        "square": "2048x2048",
        "portrait": "1440x2560",
    }
    return {
        "model": model or "doubao-seedream-5.0-lite",
        "prompt": prompt,
        "size": size_by_ratio.get(aspect_ratio, size_by_ratio["landscape"]),
        "response_format": "b64_json",
    }
```

## 6. Video provider payload sketch

```python
def build_video_payload(args: dict) -> dict:
    model = args.get("model") or "doubao-seedance-1.5-pro"
    payload = {
        "model": model,
        "content": [{"type": "text", "text": args["prompt"]}],
        "ratio": args.get("aspect_ratio", "16:9"),
        "duration": args.get("duration", 5),
    }

    optional_fields = {
        "resolution": args.get("resolution"),
        "generate_audio": args.get("audio"),
        "draft": args.get("draft"),
        "watermark": args.get("watermark"),
        "camera_fixed": args.get("camera_fixed"),
        "return_last_frame": args.get("return_last_frame"),
    }
    for key, value in optional_fields.items():
        if value is not None:
            payload[key] = value

    seed = args.get("seed")
    if seed is not None and "seedance-2.0" not in model:
        payload["seed"] = seed

    return payload
```

## 7. Web search request sketch

```python
VOLCENGINE_SEARCH_ENDPOINT = "https://open.feedcoopapi.com/search_api/web_search"


def build_search_body(query: str, limit: int) -> dict:
    count = max(1, min(int(limit or 5), 50))
    body = {
        "Query": query,
        "SearchType": "web",
        "Count": count,
        "NeedSummary": True,
    }

    if os.getenv("VOLCENGINE_SEARCH_AUTH_LEVEL") == "1":
        body["Filter"] = {"AuthInfoLevel": 1}

    time_range = os.getenv("VOLCENGINE_SEARCH_TIME_RANGE", "").strip()
    if time_range:
        body["TimeRange"] = time_range

    rewrite = os.getenv("VOLCENGINE_SEARCH_QUERY_REWRITE", "").lower() in {"1", "true", "yes", "on"}
    if rewrite:
        body["QueryControl"] = {"QueryRewrite": True}

    return body
```

## 8. Web search response mapping

```python
def map_doubao_result_to_hermes(payload: dict) -> dict:
    error = (payload.get("ResponseMetadata") or {}).get("Error")
    if error:
        return {
            "success": False,
            "error": f"Volcengine Doubao Search API Error [{error.get('Code', '')}]: {error.get('Message', '')}",
        }

    web = []
    for index, item in enumerate((payload.get("Result") or {}).get("WebResults") or []):
        meta = " | ".join(x for x in [item.get("SiteName"), item.get("AuthInfoDes")] if x)
        summary = item.get("Summary") or item.get("Snippet") or ""
        web.append({
            "title": str(item.get("Title") or ""),
            "url": str(item.get("Url") or ""),
            "description": f"{meta}\n{summary}" if meta else summary,
            "position": int(item.get("SortId") or index + 1),
        })

    return {"success": True, "data": {"web": web}}
```

## 9. Hermes config examples

### Agent Plan 默认

```yaml
model:
  provider: volcengine
  name: ark-code-latest

plugins:
  enabled:
    - web-volcengine

web:
  search_backend: volcengine

tts:
  provider: volcengine
  volcengine:
    model: doubao-seed-tts-2.0
    voice: zh_female_vv_uranus_bigtts
    format: wav

stt:
  enabled: true
  provider: volcengine
  volcengine:
    model: doubao-seed-asr-2.0
    language: auto
```

`.env`：

```bash
VOLCENGINE_PLAN_MODE=agent
VOLCENGINE_API_KEY=...
```

### Coding Plan

```yaml
model:
  provider: volcengine
  name: ark-code-latest
```

`.env`：

```bash
VOLCENGINE_PLAN_MODE=coding
VOLCENGINE_API_KEY=...
```

文档提示：Coding Plan 推荐用于文本和编码工具；图像/视频优先使用 Agent Plan 或普通 Ark API。

### 普通 Ark API

```yaml
model:
  provider: volcengine
  name: your-endpoint-model-id
```

`.env`：

```bash
VOLCENGINE_PLAN_MODE=api
ARK_API_KEY=...
```

### 自定义 endpoint 与模型

```yaml
model:
  provider: volcengine
  name: custom-model-id
```

`.env`：

```bash
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_API_KEY=...
```

## 10. install.sh example commands

```bash
# Install everything needed for the first public release with Agent Plan defaults
./install.sh --mode agent --enable-model --enable-image --enable-video --enable-web-search --enable-tts --enable-stt

# Coding Plan only, no multimodal defaults
./install.sh --mode coding --enable-model

# Ordinary Ark API with custom model and search backend
./install.sh \
  --mode api \
  --enable-model \
  --enable-web-search \
  --set-default-web-search

# Preview first-release defaults
./install.sh --mode agent --enable-web-search --enable-tts --enable-stt --dry-run
```

## 11. 标准端点汇总 (Agent Plan 默认配置)

所有服务的默认端点按功能分类如下：

### 大语言模型 & 向量模型

| 类型 | 默认端点 |
|------|----------|
| 语言模型 / 补全接口 | `https://ark.cn-beijing.volces.com/api/plan/v3` |
| 向量模型 / 嵌入接口 | `https://ark.cn-beijing.volces.com/api/plan/v3` |

### 视频生成 (Seedance)

| 操作 | 端点 |
|------|------|
| 创建视频生成任务 | `https://ark.cn-beijing.volces.com/api/plan/v3/contents/generations/tasks` |
| 查询单个视频任务 | `https://ark.cn-beijing.volces.com/api/plan/v3/contents/generations/tasks/{id}` |
| 查询任务列表 | `https://ark.cn-beijing.volces.com/api/plan/v3/contents/generations/tasks?page_num={page_num}&page_size={page_size}&filter.status={filter.status}&filter.task_ids={filter.task_ids}&filter.model={filter.model}` |
| 取消/删除任务 | `https://ark.cn-beijing.volces.com/api/plan/v3/contents/generations/tasks/{id}` |

### 图片生成 (Seedream)

| 操作 | 端点 |
|------|------|
| 图片生成 | `https://ark.cn-beijing.volces.com/api/plan/v3/images/generations` |

### 语音合成 (TTS Doubao Seed 2.0)

| 接口类型 | 端点 |
|----------|------|
| HTTP 接口 (HTTP POST) | `https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional` |
| 双向流式 (WebSocket) | `wss://openspeech.bytedance.com/api/v3/plan/tts/bidirection` |
| 单向流式输出 (WebSocket) | `wss://openspeech.bytedance.com/api/v3/plan/tts/unidirectional/stream` |

当前 Hermes 插件实现使用 HTTP 接口。

### 语音识别 (ASR Doubao Seed 2.0)

| 接口类型 | 端点 |
|----------|------|
| 双流异步接口 | `wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_async` |
| 单流同步接口 | `wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_nostream` |

当前 Hermes 插件实现使用单流接口，适合处理完整音频文件离线识别。

### 网页搜索 (Doubao Search)

搜索服务使用独立入口：`https://open.feedcoopapi.com/search_api/web_search`
