# 08. 详细阶段任务拆解

本文件把 `07-implementation-phases.md` 中的阶段进一步拆成可执行任务。当前仍是方案文档，不进入代码实现。

## Phase 1：基础兼容与 endpoint 模式

### 目标

先统一三个 provider 的 endpoint 解析，让项目稳定支持：

- Agent Plan：`/api/plan/v3`
- Coding Plan：`/api/coding/v3`
- 普通 Ark API：`/api/v3`
- 用户自定义完整 base URL

### 任务清单

#### 1.1 梳理现有硬编码 endpoint

涉及文件：

```text
plugins/model-providers/volcengine/__init__.py
plugins/image_gen/volcengine/__init__.py
plugins/video_gen/volcengine/__init__.py
```

需要记录当前硬编码值：

```text
https://ark.cn-beijing.volces.com/api/plan/v3
https://ark.cn-beijing.volces.com/api/plan/v3/images/generations
https://ark.cn-beijing.volces.com/api/plan/v3/contents/generations/tasks
```

验收：形成测试用例覆盖 endpoint 拼接，不再只靠人工检查。

#### 1.2 新增 base URL resolver

候选文件：

```text
plugins/_volcengine_common/config.py
```

如果跨插件 import 在外部安装场景不稳定，则第一版可以先放在每个 provider 内部，后续再抽取。

伪代码：

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


def _strip_trailing_slash(value: str) -> str:
    return value.rstrip("/")


def resolve_volcengine_base_url() -> str:
    explicit = os.getenv("VOLCENGINE_BASE_URL", "").strip()
    if explicit:
        return _strip_trailing_slash(explicit)

    mode = os.getenv("VOLCENGINE_PLAN_MODE", "agent").strip().lower()
    path = MODE_TO_PATH.get(mode, MODE_TO_PATH["agent"])
    return DEFAULT_REGION_BASE + path


def volcengine_endpoint(suffix: str) -> str:
    base = resolve_volcengine_base_url()
    suffix = "/" + suffix.lstrip("/")
    return base + suffix
```

#### 1.3 API key resolver

伪代码：

```python
import os


def resolve_volcengine_api_key() -> str | None:
    for name in ("VOLCENGINE_API_KEY", "ARK_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None
```

后续搜索 provider 使用独立 resolver，详见 Phase 4。

#### 1.4 更新 model provider profile

保留：

```text
name = volcengine
aliases = doubao, volcengine-agent-plan, volcengine-coding-plan, volces-engine
```

确认：

```text
api_mode = chat_completions
base_url = resolved default, 默认 /api/plan/v3
```

#### 1.5 增加测试

测试文件：

```text
tests/test_base_url_modes.py
```

测试点：

```python
def test_default_base_url_is_agent_plan(monkeypatch): ...
def test_coding_mode_base_url(monkeypatch): ...
def test_api_mode_base_url(monkeypatch): ...
def test_custom_base_url_has_highest_priority(monkeypatch): ...
def test_invalid_mode_falls_back_to_agent(monkeypatch): ...
```

### 配置示例

Agent Plan：

```bash
export VOLCENGINE_PLAN_MODE=agent
export VOLCENGINE_API_KEY="..."
```

Coding Plan：

```bash
export VOLCENGINE_PLAN_MODE=coding
export VOLCENGINE_API_KEY="..."
```

普通 Ark API：

```bash
export VOLCENGINE_PLAN_MODE=api
export ARK_API_KEY="..."
```

自定义 endpoint：

```bash
export VOLCENGINE_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
export ARK_API_KEY="..."
```

---

## Phase 2：动态模型列表与用户选择

### 目标

让 Hermes 可以从当前 endpoint 自动获取模型列表，同时保持 fallback 和手动输入 model id。

### 任务清单

#### 2.1 定义 fallback models

候选文件：

```text
plugins/model-providers/volcengine/__init__.py
```

建议：

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

#### 2.2 实现 `/models` 请求函数

伪代码：

```python
from __future__ import annotations

import httpx


def fetch_models_from_openai_compatible_endpoint(base_url: str, api_key: str, timeout: float = 10.0) -> list[str]:
    url = base_url.rstrip("/") + "/models"
    resp = httpx.get(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    models = []
    for item in payload.get("data", []) or []:
        model_id = str(item.get("id", "")).strip()
        if model_id and model_id not in models:
            models.append(model_id)
    return models
```

#### 2.3 增加缓存

缓存路径建议：

```text
~/.hermes/cache/volcengine/models.json
```

注意 profile 场景下应使用 Hermes home/profile home，而不是硬编码 `~/.hermes`。实现时优先查 Hermes 是否提供 `get_hermes_home()`。

缓存 JSON：

```json
{
  "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3",
  "fetched_at": "2026-06-24T00:00:00Z",
  "models": ["ark-code-latest", "doubao-seed-2.0-lite"]
}
```

伪代码：

```python
CACHE_TTL_SECONDS = int(os.getenv("VOLCENGINE_MODELS_CACHE_TTL_SECONDS", "86400"))


def load_cached_models(base_url: str) -> list[str] | None:
    if os.getenv("VOLCENGINE_DISABLE_MODEL_CACHE") == "1":
        return None
    # read JSON, check base_url and fetched_at age
    ...


def save_cached_models(base_url: str, models: list[str]) -> None:
    # atomic write where possible
    ...
```

#### 2.4 fallback 逻辑

伪代码：

```python
def list_volcengine_models() -> tuple[list[str], str]:
    base_url = resolve_volcengine_base_url()
    cached = load_cached_models(base_url)
    if cached:
        return cached, "cache"

    api_key = resolve_volcengine_api_key()
    if api_key:
        try:
            models = fetch_models_from_openai_compatible_endpoint(base_url, api_key)
            if models:
                save_cached_models(base_url, models)
                return models, "remote"
        except Exception:
            pass

    return list(FALLBACK_MODELS), "fallback"
```

#### 2.5 用户手动输入 model id

文档和安装脚本应明确：

> 模型列表仅用于选择和提示，不限制用户输入。普通 Ark API 或企业环境下，用户可以直接输入控制台显示的 model id。

### 测试

```text
tests/test_model_provider.py
```

测试点：

- `/models` 成功，返回远端列表。
- `/models` 返回空，使用 fallback。
- `/models` timeout，使用 fallback。
- cache 命中时不发请求。
- cache 过期时重新请求。
- fallback 包含 `ark-code-latest`。

---

## Phase 3：图像与视频 provider 更新

### 目标

保持独立 provider，更新默认模型、模型列表和视频 payload。

### 任务清单

#### 3.1 图像模型收窄

修改：

```text
plugins/image_gen/volcengine/__init__.py
```

目标：

```python
DEFAULT_IMAGE_MODEL = "doubao-seedream-5.0-lite"
SUPPORTED_IMAGE_MODELS = ("doubao-seedream-5.0-lite",)
```

#### 3.2 图像 endpoint 使用 resolver

伪代码：

```python
def image_generation_url() -> str:
    return volcengine_endpoint("/images/generations")
```

#### 3.3 视频默认模型更新

目标：

```python
DEFAULT_VIDEO_MODEL = "doubao-seedance-1.5-pro"
SUPPORTED_VIDEO_MODELS = (
    "doubao-seedance-1.5-pro",
    "doubao-seedance-2.0",
    "doubao-seedance-2.0-fast",
)
```

#### 3.4 视频 payload 补齐

伪代码：

```python
def build_video_payload(
    prompt: str,
    model: str,
    ratio: str,
    duration: int,
    resolution: str | None = None,
    generate_audio: bool | None = None,
    draft: bool | None = None,
    watermark: bool | None = None,
    camera_fixed: bool | None = None,
    return_last_frame: bool | None = None,
    seed: int | None = None,
) -> dict:
    payload = {
        "model": model,
        "content": [{"type": "text", "text": prompt}],
        "ratio": ratio,
        "duration": duration,
    }
    if resolution:
        payload["resolution"] = resolution
    if generate_audio is not None:
        payload["generate_audio"] = generate_audio
    if draft is not None:
        payload["draft"] = draft
    if watermark is not None:
        payload["watermark"] = watermark
    if camera_fixed is not None:
        payload["camera_fixed"] = camera_fixed
    if return_last_frame is not None:
        payload["return_last_frame"] = return_last_frame
    if seed is not None and "seedance-2.0" not in model:
        payload["seed"] = seed
    return payload
```

#### 3.5 Coding Plan 多模态错误提示

当 base URL 包含 `/api/coding/v3` 且图像/视频请求失败时，错误信息补充：

```text
当前使用 Coding Plan endpoint。Coding Plan 推荐用于文本/编码工具，多模态能力请优先使用 Agent Plan 或普通 Ark API。
```

### 测试

```text
tests/test_image_provider.py
tests/test_video_provider.py
```

重点断言：

- image 默认模型。
- video 默认模型。
- endpoint 拼接。
- video payload 包含 `resolution`。
- Seedance 2.0 下 `seed` 不被误传。

---

## Phase 4：Volcengine Web Search Provider

### 目标

实现 `plugins/web/volcengine`，把豆包搜索 direct API 注册为 Hermes `web_search` backend。

### 任务清单

#### 4.1 新增文件结构

```text
plugins/web/volcengine/
├── __init__.py
├── provider.py
└── plugin.yaml
```

#### 4.2 plugin.yaml

```yaml
name: web-volcengine
version: 0.1.0
description: Volcengine Doubao Search backend for Hermes web_search
author: jinnnyang
kind: backend
provides_web_providers:
  - volcengine
```

#### 4.3 provider 注册

`__init__.py`：

```python
from __future__ import annotations

from plugins.web.volcengine.provider import VolcengineWebSearchProvider


def register(ctx) -> None:
    ctx.register_web_search_provider(VolcengineWebSearchProvider())
```

#### 4.4 provider 核心伪代码

```python
from __future__ import annotations

import os
from typing import Any, Dict

import httpx
from agent.web_search_provider import WebSearchProvider

ENDPOINT = "https://open.feedcoopapi.com/search_api/web_search"
TRAFFIC_TAG = "skill_web_search_common"

SEARCH_KEY_ENV_VARS = (
    "VOLCENGINE_SEARCH_API_KEY",
    "WEB_SEARCH_API_KEY",
    "ASK_ECHO_SEARCH_INFINITY_API_KEY",
    "VOLCENGINE_API_KEY",
    "ARK_API_KEY",
)


def resolve_search_api_key() -> str | None:
    for key in SEARCH_KEY_ENV_VARS:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return None


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


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

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        api_key = resolve_search_api_key()
        if not api_key:
            return {"success": False, "error": "VOLCENGINE_SEARCH_API_KEY or WEB_SEARCH_API_KEY is not set"}

        count = max(1, min(int(limit or 5), 50))
        body: Dict[str, Any] = {
            "Query": query,
            "SearchType": "web",
            "Count": count,
            "NeedSummary": True,
        }

        auth_level = os.getenv("VOLCENGINE_SEARCH_AUTH_LEVEL", "").strip()
        if auth_level == "1":
            body["Filter"] = {"AuthInfoLevel": 1}

        time_range = os.getenv("VOLCENGINE_SEARCH_TIME_RANGE", "").strip()
        if time_range:
            body["TimeRange"] = time_range

        if env_bool("VOLCENGINE_SEARCH_QUERY_REWRITE"):
            body["QueryControl"] = {"QueryRewrite": True}

        try:
            resp = httpx.post(
                ENDPOINT,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "X-Traffic-Tag": TRAFFIC_TAG,
                },
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPStatusError as exc:
            return {"success": False, "error": f"Volcengine Doubao Search returned HTTP {exc.response.status_code}"}
        except Exception as exc:
            return {"success": False, "error": f"Could not reach Volcengine Doubao Search: {exc}"}

        error = (payload.get("ResponseMetadata") or {}).get("Error")
        if error:
            code = error.get("Code", "")
            message = error.get("Message", "")
            return {"success": False, "error": f"Volcengine Doubao Search API Error [{code}]: {message}"}

        web = []
        for index, item in enumerate((payload.get("Result") or {}).get("WebResults") or []):
            summary = item.get("Summary") or item.get("Snippet") or ""
            meta = " | ".join(x for x in [item.get("SiteName"), item.get("AuthInfoDes")] if x)
            description = f"{meta}\n{summary}" if meta else summary
            web.append({
                "title": str(item.get("Title") or ""),
                "url": str(item.get("Url") or ""),
                "description": description,
                "position": int(item.get("SortId") or index + 1),
            })

        return {"success": True, "data": {"web": web}}

    def get_setup_schema(self) -> Dict[str, Any]:
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

#### 4.5 配置示例

```bash
export VOLCENGINE_SEARCH_API_KEY="..."
hermes plugins enable web-volcengine
hermes config set web.search_backend volcengine
hermes tools enable web
```

Hermes config：

```yaml
web:
  search_backend: volcengine
```

### 测试

```text
tests/test_web_search_provider.py
```

覆盖：

- env var 优先级。
- body schema。
- header schema。
- 成功响应映射。
- API error 映射。
- HTTP error 映射。
- 缺失 key 时 provider unavailable。

---

## Phase 5：安装脚本与配置体验

### 目标

让外部用户能通过本仓库安装和配置 provider，并尽量接近 Hermes setup/tools 体验。

### 任务清单

#### 5.1 install.sh 参数解析

建议支持：

```bash
./install.sh --mode agent
./install.sh --mode coding
./install.sh --mode api
./install.sh --base-url https://ark.cn-beijing.volces.com/api/v3
./install.sh --enable-web-search --set-default-web-search
./install.sh --dry-run
```

#### 5.2 profile 检测

检测顺序：

1. 用户传入 `--profile`。
2. 当前 `HERMES_HOME`。
3. `~/.hermes/profiles/<active>`，如果能从 Hermes 获取。
4. `~/.hermes`。

Windows/Git Bash 注意路径兼容：

```bash
/c/Users/jinnn/AppData/Local/hermes/profiles/devops
C:/Users/jinnn/AppData/Local/hermes/profiles/devops
```

#### 5.3 非破坏式写配置

配置写入原则：

- 修改前备份。
- `plugins.enabled` 去重。
- secrets 不写进 `config.yaml`。
- `--dry-run` 只打印计划。

#### 5.4 配置示例

```yaml
plugins:
  enabled:
    - web-volcengine

web:
  search_backend: volcengine

model:
  provider: volcengine
  name: ark-code-latest
```

`.env`：

```bash
VOLCENGINE_API_KEY=...
VOLCENGINE_PLAN_MODE=agent
VOLCENGINE_SEARCH_API_KEY=...
```

---

## Phase 6：测试体系

### 目标

所有核心行为都能 mock 验证，不依赖真实 API key。

### 任务清单

1. 增加 `pyproject.toml` 或测试说明。
2. 引入 pytest。
3. 为 resolver 写纯函数测试。
4. 为 model provider 写 `/models` mock 测试。
5. 为 image/video 写 payload 测试。
6. 为 web search 写 direct API mock 测试。
7. 为 install.sh 写临时 profile 测试。

### 推荐命令

Windows 当前环境没有 `pip`，但有 `uv`，建议：

```bash
uv run pytest
```

如果项目尚无 `pyproject.toml`，可先：

```bash
uv add --dev pytest pytest-mock httpx pyyaml
uv run pytest
```

### CI 示例

```yaml
name: tests
on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-extras --dev
      - run: uv run pytest
```

---

## Phase 7：文档发布

### 目标

让公开用户仅阅读 README 就能完成安装和配置。

### README 必须覆盖

1. 项目定位。
2. 支持 Hermes Agent 版本。
3. Agent Plan / Coding Plan / Ark API 区别。
4. 安装命令。
5. 环境变量。
6. 模型选择和自定义 model id。
7. 图像/视频模型说明。
8. Web search backend 配置。
9. 常见错误。
10. 卸载。

### README 片段示例

#### Endpoint mode

````md
## Select endpoint mode

```bash
# Agent Plan, default
export VOLCENGINE_PLAN_MODE=agent

# Coding Plan
export VOLCENGINE_PLAN_MODE=coding

# Pay-as-you-go Ark API
export VOLCENGINE_PLAN_MODE=api

# Custom endpoint
export VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```
````

#### Web search backend

````md
## Enable Volcengine as Hermes web_search backend

```bash
export VOLCENGINE_SEARCH_API_KEY=...
hermes plugins enable web-volcengine
hermes config set web.search_backend volcengine
hermes tools enable web
```

After this, Hermes still calls the standard `web_search` tool, but the backend is Volcengine Doubao Search.
````

### 发布前检查

```bash
git status --short
uv run pytest
hermes plugins list
hermes doctor
```

真实 API smoke test 只有在用户明确提供 key 并授权时才执行。
