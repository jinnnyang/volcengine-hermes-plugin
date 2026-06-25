# 13. 交接文档：第一版发布前语音 Provider 实施

本文档用于把当前 `volcengine-hermes-plugin` 重构方案交接给下一位实施者。重点是：当前 P0/P1 核心能力已经完成，下一阶段进入 **TTS + STT 语音 provider**，并且 **第一版发布前必须同时完成 TTS 与 STT**。

## 1. 当前仓库状态

- 当前分支：`refactor/volcengine-hermes-next`
- 当前最新已提交版本：`094b326 fix: use unique volcengine plugin ids`
- 当前工作区状态：方案文档有未提交修改，且新增了语音规划文档。
- 当前测试命令：

```bash
uv run pytest -q
```

最近验证结果：

```text
................................ [100%]
```

最近也已执行：

```bash
git diff --check
```

结果通过，无 whitespace / diff 格式问题。

## 2. 当前已完成能力

### P0：开发基线

已完成：

- `pyproject.toml`
- pytest 测试入口
- `tests/` 测试目录
- 当前 `uv run pytest -q` 通过

### P1-A：Endpoint 与套餐适配

已完成：

- Agent Plan 默认 `/api/plan/v3`
- Coding Plan 支持 `/api/coding/v3`
- 普通 Ark API 支持 `/api/v3`
- 自定义 `VOLCENGINE_BASE_URL`
- 共享 resolver：`plugins/_volcengine_common/config.py`

### P1-B：动态模型列表与用户选择

已完成核心能力：

- model provider 支持 `/models` 动态拉取
- 拉取失败时 fallback models
- 保留 `ark-code-latest`
- 用户可手动指定 model id

### P1-C：图像 / 视频 Provider

已完成：

- 图像默认和列表收窄到 `doubao-seedream-5.0-lite`
- 视频默认模型为 `doubao-seedance-1.5-pro`
- 视频 payload 支持关键参数
- 相关 mock/contract 测试通过

### P1-D：Volcengine Web Search Provider

已完成：

- `plugins/web/volcengine`
- Hermes `web_search` backend provider
- 豆包搜索 direct API mock 测试
- Hermes 本体已补显式 `web.search_backend=volcengine` 不被 legacy Tavily fallback 静默替换的问题

## 3. 当前关键决策

### 3.1 发布策略

第一版发布前必须完成：

- Volcengine TTS Provider
- Volcengine STT / transcription Provider
- 安装脚本启用 TTS + STT
- README 公开使用说明
- mock 测试通过
- 用户授权后的 TTS→STT roundtrip smoke test

不采用“只完成 TTS 后先发布第一版”的策略。

### 3.2 插件形态

语音能力必须实现为 Hermes backend provider，而不是新增模型可见的普通 tool：

```text
plugins/tts/volcengine
plugins/transcription/volcengine
```

注册入口：

```python
ctx.register_tts_provider(...)
ctx.register_transcription_provider(...)
```

用户配置入口：

```yaml
tts:
  provider: volcengine

stt:
  provider: volcengine
```

### 3.3 TTS 已确认契约

- provider name：`volcengine`
- display name：`Volcengine Doubao TTS`
- model：`doubao-seed-tts-2.0`
- Resource-Id：`seed-tts-2.0`
- 默认 voice：`zh_female_vv_uranus_bigtts`
- 默认输出格式：`wav`
- 首版接口：HTTP POST

```text
https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional
```

请求头必须包含：

```text
X-Api-Key: ***
X-Api-Resource-Id: seed-tts-2.0
X-Control-Require-Usage-Tokens-Return: *
```

首版响应处理：

- HTTP chunk line 是 JSON
- `data` 字段为 base64 音频片段
- 累积 decode 后写入 `output_path`
- `code == 20000000` 表示结束
- 非结束错误码需要抛出/返回清晰错误
- 尽量保留 `X-Tt-Logid` 便于排查

### 3.4 STT 已确认契约

- provider name：`volcengine`
- display name：`Volcengine Doubao ASR`
- model：`doubao-seed-asr-2.0`
- Resource-Id：`volc.seedasr.sauc.duration`
- 默认 language：自动识别
- WebSocket 客户端依赖：`websockets`
- 首版接口：WebSocket 单流 `bigmodel_nostream`

```text
wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_nostream
```

请求头必须包含：

```text
X-Api-Key: ***
X-Api-Resource-Id: volc.seedasr.sauc.duration
X-Api-Request-Id: <uuid>
X-Api-Connect-Id: <uuid>
X-Api-Sequence: -1
```

音频处理：

- 默认接受 wav
- 必要时通过 ffmpeg 转为：
  - mono
  - `pcm_s16le`
  - 16000 Hz
  - WAV
- WebSocket 协议二进制 header / gzip 逻辑应单独封装，不要塞进 provider 主类

## 4. 测试与验收策略

### 4.1 必须 TDD

实现顺序必须是：

1. 写 TTS provider 失败测试。
2. 确认测试按预期失败。
3. 实现最小 TTS provider。
4. 确认 TTS 测试通过。
5. 写 STT provider 失败测试。
6. 确认测试按预期失败。
7. 实现最小 STT provider。
8. 确认 STT 测试通过。
9. 完成 TTS→STT roundtrip smoke test。

不要先写 provider 再补测试。

### 4.2 TTS mock 测试目标

建议新增：

```text
tests/test_tts_provider.py
```

覆盖：

- manifest id/name 唯一且语义正确
- `register(ctx)` 调用 `ctx.register_tts_provider()`
- provider name 为 `volcengine`
- API key 优先级：`VOLCENGINE_SPEECH_API_KEY > VOLCENGINE_API_KEY > ARK_API_KEY`
- 默认 model/resource id 正确
- 默认 voice 为 `zh_female_vv_uranus_bigtts`
- 默认 format 为 `wav`
- HTTP 请求头包含 `X-Api-Key`、`X-Api-Resource-Id`、`X-Control-Require-Usage-Tokens-Return`
- HTTP body 包含 text、speaker、format、sample_rate
- mock chunk 中 base64 音频被写入 `output_path`
- 错误响应包含清晰错误信息和 log id / request id

### 4.3 STT mock 测试目标

建议新增：

```text
tests/test_transcription_provider.py
```

覆盖：

- `register(ctx)` 调用 `ctx.register_transcription_provider()`
- provider name 为 `volcengine`
- 默认 model/resource id 正确
- 默认 language 为自动识别：`language=None` 或 `language="auto"` 时不强行传中文 hint
- auth header 包含 request/connect UUID
- WebSocket 客户端使用 `websockets`
- WAV 判断、必要时调用 ffmpeg 转码的边界
- 官方二进制协议 header 构造/解析独立单测
- 成功响应映射到 Hermes transcription envelope
- 错误响应包含 code/logid/request id

### 4.4 TTS→STT roundtrip smoke test

建议新增：

```text
tests/test_voice_roundtrip.py
```

默认不跑真实 API。必须用户明确授权并提供语音 API key 后才执行。

验收步骤：

1. 固定输入文本：`今天天气很好，适合测试语音模型。`
2. 调用 TTS provider，默认 voice `zh_female_vv_uranus_bigtts`，默认输出 `wav`。
3. 将生成 wav 交给 STT provider。
4. STT 默认 language 为自动识别。
5. 转写文本与原始文本完全相等则通过。

注意：如果真实 API 引入标点、空格、数字格式等差异，不能静默放宽；必须先讨论并显式记录规范化规则。

## 5. 预计新增 / 修改文件

### 新增 TTS plugin

```text
plugins/tts/volcengine/plugin.yaml
plugins/tts/volcengine/__init__.py
plugins/tts/volcengine/provider.py
```

TTS manifest 建议：

```yaml
id: tts-volcengine
name: Volcengine TTS Provider
version: 0.1.0
description: Volcengine Doubao Seed TTS backend for Hermes text_to_speech.
author: jinnnyang
kind: backend
requires_env:
  - VOLCENGINE_SPEECH_API_KEY
provides_tts_providers:
  - volcengine
```

### 新增 STT plugin

```text
plugins/transcription/volcengine/plugin.yaml
plugins/transcription/volcengine/__init__.py
plugins/transcription/volcengine/provider.py
plugins/transcription/volcengine/protocol.py
```

STT manifest 建议：

```yaml
id: transcription-volcengine
name: Volcengine Speech-to-Text Provider
version: 0.1.0
description: Volcengine Doubao Seed ASR backend for Hermes transcription.
author: jinnnyang
kind: backend
requires_env:
  - VOLCENGINE_SPEECH_API_KEY
provides_transcription_providers:
  - volcengine
```

### 修改共享配置

```text
plugins/_volcengine_common/config.py
```

需要增加或确认：

```python
resolve_volcengine_speech_api_key()
```

优先级：

```text
VOLCENGINE_SPEECH_API_KEY > VOLCENGINE_API_KEY > ARK_API_KEY
```

### 修改依赖

```text
pyproject.toml
```

预计新增：

```toml
websockets>=12
```

`httpx` 已存在，可用于 TTS HTTP。

### 修改安装脚本

```text
install.sh
```

当前 `install.sh` 仍偏向旧的 image/video 安装体验。下一阶段需要改造为支持：

```text
--mode agent|coding|api
--base-url URL
--profile PATH
--enable-model
--enable-image
--enable-video
--enable-web-search
--enable-tts
--enable-stt
--set-default-web-search
--set-default-tts
--set-default-stt
--dry-run
--no-config
```

并且：

- 修改 config 前自动备份
- `plugins.enabled` 去重
- secrets 不写入 `config.yaml`
- 语音 API key 写入 `.env` 或提示用户自行设置
- 可同时配置 `tts.provider=volcengine` 与 `stt.provider=volcengine`

## 6. 现有关键文件索引

### Provider 代码

```text
plugins/model-providers/volcengine/__init__.py
plugins/image_gen/volcengine/__init__.py
plugins/video_gen/volcengine/__init__.py
plugins/web/volcengine/__init__.py
plugins/web/volcengine/provider.py
plugins/_volcengine_common/config.py
```

### Provider manifests

```text
plugins/model-providers/volcengine/plugin.yaml
plugins/image_gen/volcengine/plugin.yaml
plugins/video_gen/volcengine/plugin.yaml
plugins/web/volcengine/plugin.yaml
```

### Tests

```text
tests/test_repository_baseline.py
tests/test_volcengine_config.py
tests/test_model_provider_endpoint.py
tests/test_media_provider_contracts.py
tests/test_web_search_provider.py
tests/test_plugin_manifest_ids.py
```

## 7. 文档索引

从这里开始读：

```text
docs/refactor/README.md
docs/refactor/00-context-and-decisions.md
docs/refactor/11-development-priority-task-map.md
docs/refactor/12-voice-provider-plan.md
docs/refactor/10-implementation-checklists.md
docs/refactor/06-testing-and-acceptance.md
```

重点文档：

- `12-voice-provider-plan.md`：语音 provider 详细方案。
- `10-implementation-checklists.md`：实施 checklist。
- `06-testing-and-acceptance.md`：测试与验收。
- `11-development-priority-task-map.md`：下一阶段优先级。

## 8. 下一步建议执行顺序

### Step 1：提交当前方案文档基线

在进入代码实现前，建议先提交当前 docs/refactor 方案文档，避免设计状态和代码状态混在一起。

建议命令：

```bash
git status --short
git diff --check
uv run pytest -q
git add docs/refactor
git commit -m "docs: update voice provider release plan"
```

不要把 `.hermes/` scratch 文件加入提交，除非用户明确要求。

### Step 2：TTS RED

新增 TTS 测试，先让测试失败。

建议命令：

```bash
uv run pytest tests/test_tts_provider.py -q
```

预期：失败，原因是 `plugins/tts/volcengine` 不存在或 provider 未实现。

### Step 3：TTS GREEN

实现最小 TTS provider，让 TTS mock 测试通过。

建议命令：

```bash
uv run pytest tests/test_tts_provider.py -q
uv run pytest -q
```

### Step 4：STT RED

新增 STT 测试和协议测试，先让测试失败。

建议命令：

```bash
uv run pytest tests/test_transcription_provider.py -q
```

预期：失败，原因是 `plugins/transcription/volcengine` 不存在或 provider/protocol 未实现。

### Step 5：STT GREEN

实现最小 STT provider 和 WebSocket protocol 封装，让 STT mock 测试通过。

建议命令：

```bash
uv run pytest tests/test_transcription_provider.py -q
uv run pytest -q
```

### Step 6：安装脚本与 README

改造：

```text
install.sh
README.md
README_zh-CN.md
```

确保第一版公开说明里 TTS 与 STT 都是已支持能力，不是 roadmap。

### Step 7：授权后 roundtrip smoke test

仅在用户明确授权并提供语音 API key 后执行。

建议命令形式后续由实现决定，例如：

```bash
VOLCENGINE_SPEECH_API_KEY=... uv run pytest tests/test_voice_roundtrip.py -q -m smoke
```

## 9. 风险与注意事项

1. **TTS HTTP chunk 边界**：文档示例使用 `iter_lines()` 读取 JSON line，需要 mock 和真实 smoke test 验证。
2. **ASR WebSocket 协议复杂**：二进制 header、gzip、分片发送、最终响应解析必须独立封装和单测。
3. **roundtrip 文本一致性**：当前验收要求严格相等；如果真实 API 返回标点/空格差异，要先讨论规范化规则。
4. **依赖控制**：STT 已选 `websockets`，不要再引入 `aiohttp` 作为并行方案，除非有明确原因。
5. **secrets 安全**：真实 API key 不进 `config.yaml`，不进 git，不进测试 fixture。
6. **Hermes runtime 验证**：mock 通过后，还需要在真实 dev profile 中验证 plugin 注册与 `tts.provider` / `stt.provider` 路由。
7. **manifest ID 与名称**：继续保持 machine id 与 human-readable name 分离。

## 10. 交接结论

当前已经完成第一版发布前的功能边界和语音契约确认。下一位实施者不需要重新讨论是否拆分发布：**必须 TTS + STT 都完成再发布第一版**。

下一步从 TTS provider 的失败测试开始，严格按 TDD 推进。
