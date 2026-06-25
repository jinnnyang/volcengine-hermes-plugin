# 火山引擎豆包插件与 Hermes Agent 集成 (`volcengine`)

本仓库为 Hermes Agent 提供火山引擎 / 豆包 backend provider：

- LLM model provider：支持 Agent Plan、Coding Plan 和普通 Ark API 端点模式。
- 图像生成：豆包 Seedream。
- 视频生成：豆包 Seedance。
- Web Search：Hermes `web_search` 的火山 / 豆包搜索 backend。
- 文本转语音：Hermes `text_to_speech` 的豆包 Seed TTS backend。
- 语音转文字：Hermes transcription / voice input 的豆包 Seed ASR backend。

Hermes 运行时配置里使用的 provider name 是 `volcengine`。

## 目录结构

```text
plugins/
├── _volcengine_common/
│   └── config.py
├── model-providers/
│   └── volcengine/
│       ├── __init__.py
│       └── plugin.yaml
├── image_gen/
│   └── volcengine/
│       ├── __init__.py
│       └── plugin.yaml
├── video_gen/
│   └── volcengine/
│       ├── __init__.py
│       └── plugin.yaml
├── web/
│   └── volcengine/
│       ├── __init__.py
│       ├── plugin.yaml
│       └── provider.py
├── tts/
│   └── volcengine/
│       ├── __init__.py
│       ├── plugin.yaml
│       └── provider.py
└── transcription/
    └── volcengine/
        ├── __init__.py
        ├── plugin.yaml
        ├── provider.py
        └── protocol.py
```

## 命名模型

Hermes 在不同层级会使用不同的名字：

| 层级 | 示例 | 用途 |
|---|---|---|
| manifest `id` | `speech-to-text-volcengine` | `plugin.yaml` 里的稳定插件包机器标识。 |
| manifest `name` | `Volcengine Speech to Text Provider` | `hermes plugins list` 里展示的人类可读名称。 |
| plugin registry key | `transcription/volcengine` | 根据路径派生，写入 `plugins.enabled` 的启用 key。 |
| runtime provider name | `volcengine` | `tts.provider`、`stt.provider`、`web.search_backend` 等配置选择的 provider name。 |

语音部分需要注意：Hermes 插件目录 category 叫 `transcription`，运行时配置 section 叫 `stt`，火山产品名通常叫 ASR。

## 安装方法

### 自动安装

在仓库根目录运行：

```bash
bash install.sh
```

安装脚本会扫描 Hermes Agent profile 目录，提示选择目标 profile，复制插件文件夹，备份 `config.yaml`，去重写入 plugin registry key，并写入非 secret 的 provider 默认配置。

非交互示例：

```bash
bash install.sh \
  --profile /path/to/hermes/profile \
  --mode agent \
  --enable-model \
  --enable-image \
  --enable-video \
  --enable-web-search \
  --enable-tts \
  --enable-stt \
  --set-default-web-search \
  --set-default-tts \
  --set-default-stt
```

常用选项：

```text
--mode agent|coding|api      将 VOLCENGINE_PLAN_MODE 写入 .env。
--base-url URL               将 VOLCENGINE_BASE_URL 写入 .env。
--profile PATH               安装到指定 Hermes profile。
--dry-run                    只打印动作，不修改文件。
--no-config                  只复制插件，不修改 config.yaml 或 .env。
--no-tts / --no-stt          不安装 TTS 或 STT 插件。
```

Secrets 永远不要写入 `config.yaml`。请把 key 放在目标 profile 的 `.env`：

```bash
VOLCENGINE_API_KEY=[REDACTED]
VOLCENGINE_SPEECH_API_KEY=[REDACTED]
```

`VOLCENGINE_SPEECH_API_KEY` 是 TTS 和 STT 推荐使用的专用语音 key。当前语音 provider 也会兼容 fallback 到 `VOLCENGINE_API_KEY` 和 `ARK_API_KEY`。

安装后需要重启 Hermes Agent 或 reset session，让新启用的插件被加载。

### 手动安装

复制插件文件夹到你的 Hermes profile 的 `plugins` 目录：

```bash
# `[HERMES_PROFILE]` 是你的 Hermes profile 路径 (~/.hermes/profiles/<name>):
cp -r plugins/_volcengine_common [HERMES_PROFILE]/plugins/
cp -r plugins/model-providers/volcengine [HERMES_PROFILE]/plugins/model-providers/
cp -r plugins/image_gen/volcengine [HERMES_PROFILE]/plugins/image_gen/
cp -r plugins/video_gen/volcengine [HERMES_PROFILE]/plugins/video_gen/
cp -r plugins/web/volcengine [HERMES_PROFILE]/plugins/web/
cp -r plugins/tts/volcengine [HERMES_PROFILE]/plugins/tts/
cp -r plugins/transcription/volcengine [HERMES_PROFILE]/plugins/transcription/
```

#### Linux / macOS
开发模式（从仓库链接到 profile，git pull 后直接生效无需重新复制）：
```bash
# 将 `~/projects/volcengine-hermes-plugin` 替换为你克隆仓库的路径：
for d in _volcengine_common model-providers/volcengine image_gen/volcengine video_gen/volcengine web/volcengine tts/volcengine transcription/volcengine; do
  ln -sf ~/projects/volcengine-hermes-plugin/plugins/$d ~/.hermes/profiles/devops/plugins/$d
done
```

#### Windows (git-bash / MSYS)
开发模式（从仓库创建目录 junction 到 profile）：
```bash
# 将 `C:\Users\yourname\projects\volcengine-hermes-plugin` 替换为你克隆仓库的路径：
for d in _volcengine_common model-providers/volcengine image_gen/volcengine video_gen/volcengine web/volcengine tts/volcengine transcription/volcengine; do
  cmd //c mklink /J ^
C:\\Users\\yourname\\AppData\\Local\\hermes\\profiles\\devops\\plugins\\$d ^
C:\\Users\\yourname\\projects\\volcengine-hermes-plugin\\plugins\\$d
done
```
如果遇到 "permission denied"，请使用管理员权限打开终端再执行 `mklink`。

在 `[HERMES_PROFILE]/config.yaml` 中启用 plugin registry key：

```yaml
plugins:
  enabled:
    - model-providers/volcengine
    - image_gen/volcengine
    - video_gen/volcengine
    - web/volcengine
    - tts/volcengine
    - transcription/volcengine
```

在 `[HERMES_PROFILE]/config.yaml` 中配置 active providers：

```yaml
model:
  provider: volcengine

web:
  search_backend: volcengine

image_gen:
  provider: volcengine
  volcengine:
    model: doubao-seedream-5.0-lite

video_gen:
  provider: volcengine
  volcengine:
    model: doubao-seedance-1.5-pro

tts:
  provider: volcengine
  volcengine:
    model: doubao-seed-tts-2.0
    resource_id: seed-tts-2.0
    voice: zh_female_vv_uranus_bigtts
    format: wav
    sample_rate: 24000

stt:
  enabled: true
  provider: volcengine
  volcengine:
    model: doubao-seed-asr-2.0
    resource_id: volc.seedasr.sauc.duration
    language: auto
```

把 secrets 写入 `[HERMES_PROFILE]/.env`，**绝对不要写入 `config.yaml`**：

```bash
# 至少需要以下其中一个：
VOLCENGINE_API_KEY=[你的-...]
# 语音 TTS/STT 推荐使用专用 key：
VOLCENGINE_SPEECH_API_KEY=[你的-speech-key]
# 如果没有 speech key，ARK API key 也可以兼容：
ARK_API_KEY=[你的-ark-key]
```
```

## 端点模式

共享配置 helper 按以下顺序解析 Volcengine Ark base URL：

1. 显式设置的 `VOLCENGINE_BASE_URL`。
2. `VOLCENGINE_PLAN_MODE`：
   - `agent` → `https://ark.cn-beijing.volces.com/api/plan/v3`
   - `coding` → `https://ark.cn-beijing.volces.com/api/coding/v3`
   - `api` → `https://ark.cn-beijing.volces.com/api/v3`
3. 默认使用 Agent Plan。

## 能力说明

### LLM model provider

Model provider 注册 runtime provider name `volcengine`，支持动态 `/models` 拉取，并保留 fallback models，包括 `ark-code-latest`。

### 图像生成

默认模型：

```text
doubao-seedream-5.0-lite
```

图像 provider 首版是 text-to-image only，并把 aspect ratio 映射为适配火山图像端点的高分辨率尺寸。

### 视频生成

默认模型：

```text
doubao-seedance-1.5-pro
```

视频 provider 对火山异步任务生命周期做同步轮询封装，生成成功后返回本地缓存的视频路径。

### Web Search

Web provider 注册 Hermes `web_search` backend，provider name 为 `volcengine`，通过以下配置选择：

```yaml
web:
  search_backend: volcengine
```

### 文本转语音 TTS

TTS provider 通过 `ctx.register_tts_provider(...)` 注册到 Hermes，并通过以下配置选择：

```yaml
tts:
  provider: volcengine
```

本插件提供三个 TTS 端点（与 Agent Plan 对齐）：

| 端点类型 | 协议 | URL | 推荐场景 |
|----------|------|-----|----------|
| 单向 HTTP | HTTP POST | `https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional` | 非流式合成，默认选项。 |
| 双向流式 | WebSocket | `wss://openspeech.bytedance.com/api/v3/plan/tts/bidirection` | 实时流式合成。 |
| 流式输出 | WebSocket | `wss://openspeech.bytedance.com/api/v3/plan/tts/unidirectional/stream` | 单向请求，流式输出合成结果。 |

默认配置：

```text
model: doubao-seed-tts-2.0
resource id: seed-tts-2.0
voice: zh_female_vv_uranus_bigtts
format: wav
sample_rate: 24000
endpoint: 单向 HTTP
```

### 语音转文字 STT / transcription

STT provider 通过 `ctx.register_transcription_provider(...)` 注册到 Hermes，并通过以下配置选择：

```yaml
stt:
  enabled: true
  provider: volcengine
```

本插件提供两个 ASR 端点（均为 WebSocket 协议，与 Agent Plan 对齐）：

| 端点类型 | URL | 推荐场景 |
|----------|-----|----------|
| 单流接口 (nostream) | `wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_nostream` | 准确率优先场景：录制完整音频后发送，上传完成统一返回结果。Hermes 当前 voice dictation（先录音后转写）默认选择此端点。 |
| 双流接口 (async) | `wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_async` | 低延迟实时场景：边发送音频边获取增量识别结果，为未来 Hermes 实时语音接口预留。 |

默认配置：

```text
model: doubao-seed-asr-2.0
resource id: volc.seedasr.sauc.duration
endpoint: 单流 (bigmodel_nostream)
language: auto
```

实现使用 `websockets` Python 包，并把火山 ASR 二进制协议 helper 放在 `plugins/transcription/volcengine/protocol.py`。

## 验证

运行测试：

```bash
uv run pytest -q
```

检查 Hermes profile 中插件是否已启用：

```bash
hermes plugins list --plain --enabled
```

预期 registry key 包含：

```text
model-providers/volcengine
image_gen/volcengine
video_gen/volcengine
web/volcengine
tts/volcengine
transcription/volcengine
```

真实 TTS → STT roundtrip smoke test 只能在明确提供有效 speech API key 到 `.env` 之后执行。
