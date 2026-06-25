# 12. Volcengine 语音模型 Provider 规划

本文件记录把火山方舟 Agent Plan 语音模型接入 Hermes Agent 的初步方案。当前处于方案讨论阶段，不进入实现。

## 1. 背景与目标

火山方舟 Agent Plan 已提供语音模型能力：

- 语音合成 TTS：豆包语音合成模型 2.0
- 语音识别 ASR/STT：豆包流式语音识别模型 2.0

目标是把这些能力注册为 Hermes 的标准语音 provider，而不是新增模型可见的专用工具。这样用户仍然使用 Hermes 现有语音入口：

- TTS：`text_to_speech` tool / `/voice tts` / gateway 语音回复
- STT：语音消息自动转写 / Hermes transcription pipeline

## 2. Hermes 扩展点确认

当前 Hermes Agent 本体已经有语音 provider 插件扩展点：

```text
agent/tts_provider.py
agent/tts_registry.py
agent/transcription_provider.py
agent/transcription_registry.py
hermes_cli/plugins.py::PluginContext.register_tts_provider()
hermes_cli/plugins.py::PluginContext.register_transcription_provider()
```

因此 Volcengine 语音接入应优先走 backend provider 插件：

```text
plugins/tts/volcengine/
plugins/transcription/volcengine/
```

而不是新增 `volcengine_tts` / `volcengine_asr` 普通 tool。

## 3. 火山语音模型信息

来源：火山方舟文档《接入语音模型》。截至当前方案：

### TTS

```text
模型名：doubao-seed-tts-2.0
Resource-Id：seed-tts-2.0
```

可用接口：

| 类型 | 协议 | Base URL | 适用场景 |
|---|---|---|---|
| 双向流式 | WebSocket | `wss://openspeech.bytedance.com/api/v3/plan/tts/bidirection` | 实时对话，流式发送文本、流式接收音频 |
| 单向流式 | WebSocket | `wss://openspeech.bytedance.com/api/v3/plan/tts/unidirectional/stream` | 一次发送文本，流式接收音频片段 |
| HTTP | HTTP POST | `https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional` | 一次发送文本，一次返回或 chunk 返回音频，最适合先接入 Hermes `text_to_speech` |

### ASR / STT

```text
模型名：doubao-seed-asr-2.0
Resource-Id：volc.seedasr.sauc.duration
```

可用接口：

| 类型 | 协议 | Base URL | 适用场景 |
|---|---|---|---|
| 双流接口 | WebSocket | `wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_async` | 边发送音频边实时返回识别结果 |
| 单流接口 | WebSocket | `wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_nostream` | 流式发送音频，完成后或超过 15s 返回高精度结果 |

## 4. 配置与鉴权原则

官方要求：

- 使用专属 API Key。
- 请求头中设置 `X-Api-Key`。
- 请求头中设置 `X-Api-Resource-Id`。
- 当前语音模型不支持通过 Auto 或控制台切换使用。
- 开启超额后付费后无需修改 Base URL、API Key 或模型名称，系统自动进入后付费。

建议本插件配置：

### 环境变量

```text
VOLCENGINE_SPEECH_API_KEY      # 首选，语音专属 API Key
VOLCENGINE_API_KEY             # fallback，沿用已有火山 key
ARK_API_KEY                    # fallback，沿用官方 Ark key 命名

VOLCENGINE_TTS_RESOURCE_ID     # 默认 seed-tts-2.0
VOLCENGINE_ASR_RESOURCE_ID     # 默认 volc.seedasr.sauc.duration
```

### Hermes config.yaml

非 secret 行为写入 `config.yaml`：

```yaml
tts:
  provider: volcengine
  volcengine:
    model: doubao-seed-tts-2.0
    voice: zh_female_vv_uranus_bigtts
    sample_rate: 24000
    format: wav
    base_url: https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional

stt:
  enabled: true
  provider: volcengine
  volcengine:
    model: doubao-seed-asr-2.0
    mode: nostream
    sample_rate: 16000
    language: auto
```

注意：API Key 不写入 `config.yaml`，应写入 Hermes profile `.env` 或由用户自行设置环境变量。

## 5. 建议插件结构

```text
plugins/tts/volcengine/
├── plugin.yaml
├── __init__.py
└── provider.py

plugins/transcription/volcengine/
├── plugin.yaml
├── __init__.py
├── provider.py
└── protocol.py        # 若实现 WebSocket ASR，可封装二进制协议
```

TTS manifest 建议：

```yaml
id: text-to-speech-volcengine
name: Volcengine Text to Speech Provider
version: 0.1.0
description: Volcengine Doubao Seed TTS backend for Hermes text_to_speech.
author: jinnnyang
kind: backend
requires_env:
  - VOLCENGINE_SPEECH_API_KEY
provides_tts_providers:
  - volcengine
```

STT manifest 建议：

```yaml
id: speech-to-text-volcengine
name: Volcengine Speech to Text Provider
version: 0.1.0
description: Volcengine Doubao Seed ASR backend for Hermes transcription.
author: jinnnyang
kind: backend
requires_env:
  - VOLCENGINE_SPEECH_API_KEY
provides_transcription_providers:
  - volcengine
```

如果当前 Hermes plugin manifest loader 尚未消费 `provides_tts_providers` / `provides_transcription_providers` 字段，也应保留这些字段作为机器可读意图；真实注册由 `__init__.py` 中的 `register(ctx)` 完成。

## 6. TTS Provider 设计

实现类：

```text
VolcengineTTSProvider(TTSProvider)
```

核心方法：

- `name -> "volcengine"`
- `display_name -> "Volcengine Doubao TTS"`
- `is_available()`：检查 API key 是否存在，不做网络调用
- `list_models()`：返回 `doubao-seed-tts-2.0`
- `default_model()`：`doubao-seed-tts-2.0`
- `list_voices()`：至少提供默认中文音色
- `default_voice()`：默认 `zh_female_vv_uranus_bigtts`
- `get_setup_schema()`：暴露 API key 提示和文档链接
- `synthesize(text, output_path, voice=None, model=None, speed=None, format="wav", **extra)`：调用 HTTP TTS 接口，写入音频文件并返回路径

首版优先接 HTTP POST 接口，因为它最贴近 Hermes 当前 `TTSProvider.synthesize()` 的同步文件输出契约。WebSocket 双向/单向流式可作为后续增强。

### TTS 请求要点

请求头：

```text
X-Api-Key: <api-key>
X-Api-Resource-Id: seed-tts-2.0
Content-Type: application/json
Connection: keep-alive
X-Control-Require-Usage-Tokens-Return: *
```

body：

```json
{
  "req_params": {
    "text": "...",
    "speaker": "zh_female_vv_uranus_bigtts",
    "audio_params": {
      "format": "wav",
      "sample_rate": 24000
    }
  }
}
```

响应处理：

- HTTP chunk line 是 JSON。
- `data` 字段为 base64 音频片段。
- 累积 decode 后写入 `output_path`。
- `code == 20000000` 表示结束。
- `code > 0` 且非结束码时视为错误。
- 始终记录或返回 `X-Tt-Logid` 便于排查。

## 7. STT Provider 设计

实现类：

```text
VolcengineTranscriptionProvider(TranscriptionProvider)
```

核心方法：

- `name -> "volcengine"`
- `display_name -> "Volcengine Doubao ASR"`
- `is_available()`：检查 API key，必要时检查 `ffmpeg` 是否存在
- `list_models()`：返回 `doubao-seed-asr-2.0`
- `default_model()`：`doubao-seed-asr-2.0`
- `get_setup_schema()`：暴露 API key 提示和文档链接
- `transcribe(file_path, model=None, language=None, **extra)`：返回 Hermes 标准 envelope；默认语言为自动识别，配置中可记为 `language: auto` 或不传 language hint

首版建议接 WebSocket 单流 `bigmodel_nostream`，因为 Hermes STT 通常拿到的是完整音频文件路径，单流完成后返回结果更符合当前契约。实时双流 `bigmodel_async` 可以后续支持。

### ASR 请求要点

请求头：

```text
X-Api-Key: <api-key>
X-Api-Resource-Id: volc.seedasr.sauc.duration
X-Api-Request-Id: <uuid>
X-Api-Connect-Id: <uuid>
X-Api-Sequence: -1
```

音频处理：

- 若输入不是 WAV，使用 ffmpeg 转为：
  - mono
  - `pcm_s16le`
  - 16000 Hz
  - WAV
- 分片发送，默认 200ms。
- 使用官方示例中的 gzip + 二进制 header 协议。
- WebSocket 客户端依赖选用 `websockets`。

返回处理：

- 成功：`{"success": true, "transcript": "...", "provider": "volcengine"}`
- 失败：`{"success": false, "transcript": "", "error": "...", "provider": "volcengine"}`
- 尽量透出 `X-Tt-Logid` / request id。

## 8. 测试策略

先写测试再实现。mock 测试不做真实 API 调用，除非用户明确授权。

### TTS mock 测试

候选文件：

```text
tests/test_tts_provider.py
```

覆盖：

1. manifest id/name 唯一且语义正确。
2. `register(ctx)` 调用 `ctx.register_tts_provider()`。
3. provider name 为 `volcengine`。
4. API key 优先级：`VOLCENGINE_SPEECH_API_KEY > VOLCENGINE_API_KEY > ARK_API_KEY`。
5. 默认 model/resource id 正确。
6. HTTP TTS 请求头包含：
   - `X-Api-Key`
   - `X-Api-Resource-Id: seed-tts-2.0`
   - `X-Control-Require-Usage-Tokens-Return: *`
7. HTTP body 包含 text、speaker、format、sample_rate，默认 `speaker=zh_female_vv_uranus_bigtts`，默认 `format=wav`。
8. mock chunk 中 base64 音频被写入 output_path。
9. 错误响应返回清晰异常，由 Hermes dispatcher 转为失败 envelope。

### STT mock 测试

候选文件：

```text
tests/test_transcription_provider.py
```

覆盖：

1. `register(ctx)` 调用 `ctx.register_transcription_provider()`。
2. provider name 为 `volcengine`。
3. 默认 model/resource id 正确。
4. auth header 包含 request/connect UUID。
5. 默认 language 为自动识别：`language=None` 或配置值 `auto` 时不强行传中文语言 hint。
6. WAV 判断、必要时调用 ffmpeg 转码的边界。
7. 官方二进制协议 header 构造/解析独立单测。
8. 成功响应映射到 Hermes transcription envelope。
9. 错误响应包含 code/logid/request id。

### TTS → STT roundtrip 验收测试

在 TTS 与 STT provider 都完成后，增加一个端到端 roundtrip 验收：

1. 使用固定文本，例如：`今天天气很好，适合测试语音模型。`
2. 调用 Volcengine TTS provider，默认 voice `zh_female_vv_uranus_bigtts`，默认输出 `wav`。
3. 将 TTS 生成的 wav 文件交给 Volcengine STT provider。
4. STT 默认语言为自动识别。
5. 对比原始文本与转写文本。
6. 文本完全相等则通过；若真实 API 存在标点、空格或简繁差异，再显式记录规范化规则，不能静默放宽。

该 roundtrip 测试需要真实语音 API key 和计费授权，因此默认标记为 smoke/integration，不在普通 `uv run pytest -q` 中自动执行。mock 测试仍必须覆盖 provider 逻辑。

## 9. 分阶段建议

发布策略已确认：**第一版发布前必须同时完成 TTS Provider 与 STT Provider**。TTS 可以先实现以降低风险，但不能作为单独第一版发布；STT 不能推迟到第一版之后。

### Voice-P0：方案与契约确认

- 更新 `docs/refactor/` 当前状态。
- 明确优先实现 TTS HTTP，ASR 单流 WebSocket。
- 已确认默认 voice：`zh_female_vv_uranus_bigtts`。
- 已确认默认音频格式：`wav`。
- 已确认 STT 默认语言：自动识别。
- 已确认 ASR WebSocket 依赖：`websockets`。
- 确认是否同名 provider `volcengine` 分别用于 `tts.provider` 与 `stt.provider`。

### Voice-P1：TTS Provider

- 写 TTS provider 失败测试。
- 实现 `plugins/tts/volcengine`。
- 使用 HTTP POST 接口。
- 默认 voice 为 `zh_female_vv_uranus_bigtts`。
- 默认输出格式为 `wav`。
- mock chunked base64 音频写文件。
- 配置接入 `tts.provider=volcengine`。

### Voice-P2：STT Provider

- 写 STT provider 失败测试。
- 实现 `plugins/transcription/volcengine`。
- 先支持 `bigmodel_nostream`。
- 使用 `websockets` 实现 WebSocket 客户端。
- 默认 language 为自动识别。
- 独立测试协议编码/解析。
- 配置接入 `stt.provider=volcengine`。
- TTS 与 STT 都完成后执行 TTS→STT roundtrip smoke test：TTS 生成 wav，STT 转写，转写文本与原始文本相等则通过。

### Voice-P3：安装与文档

- `install.sh --enable-tts`
- `install.sh --enable-stt`
- `install.sh --set-default-tts`
- `install.sh --set-default-stt`
- README 增加语音模型章节。
- 文档注明超额后付费无需变更配置。
- 第一版发布文档中 TTS 与 STT 都应列为已支持能力，而不是后续 roadmap。

## 10. 风险与开放问题

1. **TTS HTTP 是否严格 chunked**：示例使用 `iter_lines()` 读取 JSON line，需要 mock 和真实 smoke test 验证边界。
2. **ASR 协议复杂度高**：WebSocket 二进制协议应单独封装和测试，避免塞进 provider 主类。
3. **Hermes manifest 字段消费情况**：核心注册已支持，但 manifest `provides_tts_providers` / `provides_transcription_providers` 是否被 UI 完整使用需要运行态验证。
4. **真实 API smoke test**：语音模型涉及专属 API Key 和计费，必须用户明确授权后再跑。
5. **roundtrip 文本一致性**：用户要求 TTS 结果再经 STT 后文本相等才算成功；如果真实 API 引入标点/空格/数字格式差异，需要先讨论是否允许规范化。
