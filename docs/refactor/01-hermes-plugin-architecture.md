# 01. Hermes 插件体系与目标架构

## 1. 参考的 Hermes 官方插件机制

新版 Hermes Agent 插件体系包括多类扩展：

| 能力 | 插件机制 |
|---|---|
| 普通工具、hook、命令 | `register(ctx)` + `ctx.register_tool()` |
| 模型 provider | `plugins/model-providers/<name>/` + `register_provider(ProviderProfile(...))` |
| Web search backend | `plugins/web/<name>/` + `ctx.register_web_search_provider(...)` |
| 图像生成 backend | `ctx.register_image_gen_provider(provider)` |
| 视频生成 backend | `ctx.register_video_gen_provider(provider)` |
| 平台适配器 | `ctx.register_platform(...)` |

本仓库需要同时覆盖四类 provider：

1. Model provider
2. Image generation provider
3. Video generation provider
4. Web search provider

## 2. 目标目录结构

建议重构后的目录为：

```text
volcengine-hermes-plugin/
├── README.md
├── README_zh-CN.md
├── install.sh
├── docs/
│   └── refactor/
├── plugins/
│   ├── model-providers/
│   │   └── volcengine/
│   │       ├── __init__.py
│   │       ├── plugin.yaml
│   │       └── README.md              # 可选
│   ├── image_gen/
│   │   └── volcengine/
│   │       ├── __init__.py
│   │       └── plugin.yaml
│   ├── video_gen/
│   │   └── volcengine/
│   │       ├── __init__.py
│   │       └── plugin.yaml
│   └── web/
│       └── volcengine/
│           ├── __init__.py
│           ├── provider.py
│           └── plugin.yaml
├── tests/
│   ├── test_base_url_modes.py
│   ├── test_model_provider.py
│   ├── test_image_provider.py
│   ├── test_video_provider.py
│   ├── test_web_search_provider.py
│   └── test_install_script.py
└── pyproject.toml                       # 可选，便于测试依赖管理
```

## 3. Provider 边界

### Model provider

位置：

```text
plugins/model-providers/volcengine/
```

职责：

- 注册 Hermes inference provider。
- 提供 OpenAI-compatible endpoint 信息。
- 声明 env var 优先级。
- 提供 fallback models。
- 支持动态模型列表。

### Image provider

位置：

```text
plugins/image_gen/volcengine/
```

职责：

- 文生图。
- 调用火山图像生成接口。
- 使用统一 base URL 解析逻辑。
- 默认 `doubao-seedream-5.0-lite`。

### Video provider

位置：

```text
plugins/video_gen/volcengine/
```

职责：

- 文生视频/图生视频。
- 创建异步任务。
- 轮询任务状态。
- 下载并缓存结果视频。
- 默认 `doubao-seedance-1.5-pro`。

### Web search provider

位置：

```text
plugins/web/volcengine/
```

职责：

- 注册 Hermes `WebSearchProvider`。
- 让 `web_search` backend 可选择 `volcengine`。
- 调用豆包搜索 direct API。
- 返回 Hermes 标准 web result shape。

## 4. 共享配置逻辑

当前三个 provider 可能各自硬编码 base URL。重构时建议抽取最小共享逻辑，但不要过度工程化。

建议新增一个内部 helper，例如：

```text
plugins/_volcengine_common/
  __init__.py
  config.py
  models.py
  errors.py
```

如果 Hermes 插件 loader 对跨插件 import 不稳定，也可以先复制少量简单函数，后续再抽取。

建议共享函数：

```python
def resolve_base_url(default_path: str = "/api/plan/v3") -> str:
    ...

def resolve_api_key(*env_names: str) -> str | None:
    ...

def join_endpoint(base_url: str, suffix: str) -> str:
    ...
```

## 5. 插件启用方式

用户安装后，provider 类插件应支持：

```bash
hermes plugins enable web-volcengine
hermes config set web.search_backend volcengine
hermes tools enable web
```

模型 provider 通过 Hermes provider registry 被发现，用户可通过：

```bash
hermes model
```

或配置文件选择：

```yaml
model:
  provider: volcengine
  name: ark-code-latest
```

## 6. 最新 Hermes 兼容点

需要对齐新版 Hermes：

- Model provider 使用 `ProviderProfile` 和 `register_provider()`。
- Web search 使用 `agent.web_search_provider.WebSearchProvider`。
- Web backend 选择使用：
  - `web.search_backend`
  - fallback：`web.backend`
- Provider setup metadata 通过 `get_setup_schema()` 暴露给 `hermes tools` / setup 体验。
- 用户插件默认 opt-in，不应无提示启用危险能力。

## 7. 设计原则

1. 先兼容，后增强。
2. provider 边界清晰，不把搜索塞进模型 provider。
3. 支持用户显式配置，不猜测用户套餐。
4. endpoint 和 model id 都允许手动覆盖。
5. 出错信息要指出可能的套餐/endpoint/API key 原因。
6. 所有网络调用都应可 mock 测试。
