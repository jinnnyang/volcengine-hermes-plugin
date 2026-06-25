# 06. 测试与验收方案

## 1. 目标

为公开仓库增加可重复验证的测试，避免重构破坏：

- Endpoint mode 解析。
- 动态模型拉取。
- fallback 模型。
- 图像/视频 payload。
- 豆包搜索 provider。
- 豆包 TTS provider。
- 豆包 STT provider。
- TTS → STT roundtrip 验收。
- 安装脚本。

测试默认不依赖真实 API key。

## 2. 测试目录

建议新增：

```text
tests/
├── test_base_url_modes.py
├── test_model_provider.py
├── test_image_provider.py
├── test_video_provider.py
├── test_web_search_provider.py
├── test_tts_provider.py
├── test_transcription_provider.py
├── test_voice_roundtrip.py      # smoke/integration，默认跳过真实 API
└── test_install_script.py
```

如项目加入 `pyproject.toml`，测试依赖可用：

```toml
[project.optional-dependencies]
test = [
  "pytest",
  "pytest-mock",
  "httpx",
  "responses",
  "pyyaml",
]
```

## 3. Base URL 测试

覆盖：

| 输入 | 预期 |
|---|---|
| 无 env | `/api/plan/v3` |
| `VOLCENGINE_PLAN_MODE=agent` | `/api/plan/v3` |
| `VOLCENGINE_PLAN_MODE=coding` | `/api/coding/v3` |
| `VOLCENGINE_PLAN_MODE=api` | `/api/v3` |
| `VOLCENGINE_BASE_URL=custom` | custom |
| 非法 mode | fallback agent + warning |

## 4. Model provider 测试

### fallback list

断言：

- 包含 `ark-code-latest`。
- 包含新模型列表。
- 不删除历史 alias。

### `/models` 动态拉取

Mock 成功响应：

```json
{
  "object": "list",
  "data": [
    {"id": "model-a"},
    {"id": "model-b"}
  ]
}
```

预期：

```python
["model-a", "model-b"]
```

Mock 失败：

- 500
- timeout
- invalid JSON
- 空 data

预期：

```python
fallback_models
```

### 用户手动 model id

测试 provider 不阻止未知模型：

```text
my-custom-model-id
```

## 5. Image provider 测试

覆盖：

- 默认模型为 `doubao-seedream-5.0-lite`。
- 模型列表只含 `doubao-seedream-5.0-lite`。
- endpoint 根据 mode 正确。
- payload 包含 prompt/model/size/response_format。
- b64_json 响应保存到文件。
- URL 响应下载保存。
- API 错误返回友好 message。

## 6. Video provider 测试

覆盖：

- 默认模型为 `doubao-seedance-1.5-pro`。
- payload 包含：
  - model
  - content
  - ratio
  - duration
  - resolution
  - generate_audio
- 创建任务成功。
- 创建任务失败。
- 轮询成功。
- 轮询失败。
- 轮询超时。
- 下载视频成功/失败。
- Seedance 2.0 下不支持字段的条件处理。

## 7. Web search provider 测试

Mock request：

```http
POST https://open.feedcoopapi.com/search_api/web_search
```

断言 headers：

```text
Authorization: Bearer ***
Content-Type: application/json
X-Traffic-Tag: skill_web_search_common
```

断言 body：

```json
{
  "Query": "test",
  "SearchType": "web",
  "Count": 5,
  "NeedSummary": true
}
```

成功响应：

```json
{
  "Result": {
    "ResultCount": 1,
    "TimeCost": 12,
    "WebResults": [
      {
        "SortId": 1,
        "Title": "A",
        "SiteName": "Site",
        "AuthInfoDes": "Official",
        "Url": "https://example.com",
        "Summary": "Summary"
      }
    ]
  },
  "ResponseMetadata": {}
}
```

预期 Hermes shape：

```json
{
  "success": true,
  "data": {
    "web": [
      {
        "title": "A",
        "url": "https://example.com",
        "description": "Site | Official\nSummary",
        "position": 1
      }
    ]
  }
}
```

错误响应：

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

预期：

```json
{"success": false, "error": "...10403..."}
```

## 8. Voice provider 测试

### TTS provider mock 测试

覆盖：

- provider name 为 `volcengine`。
- display name 为 `Volcengine Doubao TTS`。
- 默认 model 为 `doubao-seed-tts-2.0`。
- 默认 Resource-Id 为 `seed-tts-2.0`。
- 默认 voice 为 `zh_female_vv_uranus_bigtts`。
- 默认输出格式为 `wav`。
- API key 优先级：`VOLCENGINE_SPEECH_API_KEY > VOLCENGINE_API_KEY > ARK_API_KEY`。
- HTTP TTS 请求头包含 `X-Api-Key`、`X-Api-Resource-Id`、`X-Control-Require-Usage-Tokens-Return`。
- mock chunked JSON line 中的 base64 音频能写入 `output_path`。

### STT provider mock 测试

覆盖：

- provider name 为 `volcengine`。
- display name 为 `Volcengine Doubao ASR`。
- 默认 model 为 `doubao-seed-asr-2.0`。
- 默认 Resource-Id 为 `volc.seedasr.sauc.duration`。
- 默认 language 为自动识别，`language=None` 或 `language="auto"` 不强行发送中文 hint。
- WebSocket 客户端依赖使用 `websockets`。
- 必要时通过 ffmpeg 转为 mono / `pcm_s16le` / 16000Hz / WAV。
- 官方二进制协议 header 构造/解析独立测试。
- 成功响应映射为 Hermes transcription envelope。

### TTS → STT roundtrip smoke 测试

第一版发布前需要真实 roundtrip 验收，但默认测试不自动调用真实 API：

1. 固定输入文本：`今天天气很好，适合测试语音模型。`
2. 调用 TTS provider，默认 voice `zh_female_vv_uranus_bigtts`，默认输出 `wav`。
3. 将生成 wav 交给 STT provider。
4. STT 默认 language 为自动识别。
5. 转写文本与原始文本完全相等则通过。
6. 如果真实 API 引入标点、空格、数字格式等差异，需要先讨论并显式记录规范化规则，不能静默放宽。

该测试应标记为 smoke/integration，并要求用户明确授权真实 API key 与可能产生的计费。

## 9. Install script 测试

建议通过临时目录模拟 Hermes profile：

```text
tmp_profile/
  config.yaml
  plugins/
```

覆盖：

- `--dry-run` 不写文件。
- 插件复制到正确目录。
- config 修改前备份。
- `plugins.enabled` 去重。
- `--mode agent/coding/api` 生成正确配置。
- `--enable-web-search` 设置 `web.search_backend=volcengine`。
- 重复运行 idempotent。

## 10. 手动 smoke test

在有真实 key 且用户明确允许时，可执行：

```bash
hermes plugins list
hermes model
hermes doctor
```

搜索 smoke test：

```text
让 Hermes 执行 web_search 查询一个简单问题，确认 backend 为 volcengine 且返回结果。
```

不要在 CI 中使用真实 key。

## 11. CI 建议

如果仓库面向公开用户，建议后续加 GitHub Actions：

```yaml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --extra test
      - run: uv run pytest
```

## 12. 验收标准总表

| 模块 | 最低验收 |
|---|---|
| model provider | endpoint mode、fallback models、动态 `/models` mock 通过 |
| image provider | 默认 5.0-lite、payload、响应保存通过 |
| video provider | 默认 1.5-pro、payload、任务状态测试通过 |
| web provider | mock 豆包搜索成功/失败映射通过 |
| TTS provider | 默认 voice `zh_female_vv_uranus_bigtts`、默认 `wav`、mock chunk 写文件通过 |
| STT provider | 默认自动语言、`websockets`、协议解析和 envelope 映射通过 |
| voice roundtrip | 真实授权后 TTS wav → STT 文本与原文相等 |
| install | dry-run、备份、配置去重通过 |
| docs | 中英文 README 更新，含搜索 backend 和 endpoint 模式 |
