# 00. 背景、目标与已确认决策

## 1. 重构目标

把 `volcengine-hermes-plugin` 重构为支持新版 Hermes Agent 的火山方舟插件集合，重点支持：

- Agent Plan / Coding Plan / 普通 Ark API 三种 endpoint 模式。
- 文本模型 provider 自动拉取可用模型列表。
- Hermes 用户可选择模型，也可手动输入 model id。
- 图像和视频能力保持独立 provider。
- 视频默认模型更新为 `doubao-seedance-1.5-pro`。
- 图像模型收窄到 Agent Plan 页面明确支持的 `doubao-seedream-5.0-lite`。
- 新增 Volcengine Web Search Provider，把豆包搜索接入 Hermes 标准 `web_search` backend。
- 新增 Volcengine TTS / STT Provider，把豆包语音模型接入 Hermes 标准 `text_to_speech` 和语音转写 pipeline。
- 提供测试、验证、安装和公开用户文档。

## 2. 项目新定位

建议项目定位改为：

> Volcengine Ark / Doubao plugin bundle for Hermes Agent，支持 Agent Plan、Coding Plan、普通火山 Ark API，并提供文本模型、图像生成、视频生成、搜索和语音 backend。

中文 README 可写为：

> 面向 Hermes Agent 的火山方舟 / 豆包插件集合，兼容 Agent Plan、Coding Plan 与普通 Ark 按量付费 API，提供模型 provider、图像生成、视频生成、豆包搜索和语音 provider。

## 3. 兼容性原则

重构可以重新定义项目定位，但必须保留已有用户配置的可用性。

### 需要保留的兼容项

- Provider canonical name：`volcengine`
- 历史 alias：
  - `volcengine-agent-plan`
  - `volcengine-coding-plan`
  - `doubao`
  - `volces-engine`
- 历史模型：
  - `ark-code-latest`
- 历史环境变量：
  - `VOLCENGINE_API_KEY`
  - `ARK_API_KEY`
- 历史默认 endpoint 行为：默认仍指向 Agent Plan。

### 允许新增的配置

- `VOLCENGINE_PLAN_MODE=agent|coding|api`
- `VOLCENGINE_BASE_URL=...`
- `VOLCENGINE_MODEL=...`
- `VOLCENGINE_SEARCH_API_KEY=...`
- `WEB_SEARCH_API_KEY=...`
- `VOLCENGINE_SPEECH_API_KEY=...`
- `VOLCENGINE_TTS_RESOURCE_ID=...`
- `VOLCENGINE_ASR_RESOURCE_ID=...`

## 4. Endpoint 模式

| 模式 | Base URL | 用途 | 默认 |
|---|---|---|---|
| `agent` | `https://ark.cn-beijing.volces.com/api/plan/v3` | Agent Plan | 是 |
| `coding` | `https://ark.cn-beijing.volces.com/api/coding/v3` | Coding Plan / 编码工具 | 否 |
| `api` | `https://ark.cn-beijing.volces.com/api/v3` | 普通 Ark 按量付费 API | 否 |
| `custom` | 用户自定义完整 base URL | 私有网关、未来 endpoint、灰度环境 | 否 |

解析优先级：

```text
显式 VOLCENGINE_BASE_URL
  > VOLCENGINE_PLAN_MODE
  > 插件默认 agent mode
```

## 5. 多模态与 Coding Plan 的文档口径

代码层面允许所有 provider 根据统一逻辑切换到 `/api/coding/v3`。

但文档应明确：

> Coding Plan 推荐用于文本和编码工具场景。图像/视频等多模态能力请优先使用 Agent Plan 或普通 Ark API；如果在 Coding Plan endpoint 下调用失败，通常表示当前套餐或 endpoint 不支持对应能力。

## 6. 图像与视频决策

### 图像

- 保持独立 image provider。
- 默认模型：`doubao-seedream-5.0-lite`
- 模型列表只保留：`doubao-seedream-5.0-lite`

### 视频

- 保持独立 video provider。
- 默认模型改为：`doubao-seedance-1.5-pro`
- fallback/可选列表可包含：
  - `doubao-seedance-1.5-pro`
  - `doubao-seedance-2.0`
  - `doubao-seedance-2.0-fast`

## 7. 搜索能力决策

主线实现：

> 新增 `plugins/web/volcengine`，实现 Hermes `WebSearchProvider`，把豆包搜索注册为 Hermes `web_search` backend。

这比单独 MCP 工具更符合用户目标：

- 用户仍然使用标准 `web_search`。
- Hermes backend 切换为 `volcengine`。
- 使用体验接近 Tavily / Exa / Brave 等 provider。

专业数据集搜索暂列为后续普通 tool 或独立 provider 设计，需进一步确认 direct API schema。

## 8. 语音能力决策

主线实现：

> 新增 `plugins/tts/volcengine` 与 `plugins/transcription/volcengine`，分别实现 Hermes `TTSProvider` 与 `TranscriptionProvider`，把豆包语音合成和豆包流式语音识别接入 Hermes 标准语音入口。

这比新增 `volcengine_tts` / `volcengine_asr` 普通 tool 更符合 Hermes 现有 UX：

- 用户仍然使用 `text_to_speech`、`/voice tts`、语音消息自动转写等标准入口。
- `tts.provider=volcengine` 与 `stt.provider=volcengine` 负责 backend 切换。
- TTS 首版优先 HTTP POST 接口，匹配 Hermes 当前 `synthesize(text, output_path)` 文件输出契约。
- STT 首版优先 WebSocket 单流 `bigmodel_nostream`，匹配 Hermes 当前拿完整音频文件做转写的 pipeline。
- TTS 默认 voice：`zh_female_vv_uranus_bigtts`。
- TTS 默认输出格式：`wav`。
- STT 默认语言：自动识别。
- ASR WebSocket 客户端依赖：`websockets`。
- 语音实现必须按 TDD 推进：先写 TTS 测试，再实现 TTS；再写 STT 测试，再实现 STT。
- 第一版真实验收需要 TTS→STT roundtrip：TTS 生成 wav，STT 转写，转写文本与原始文本相等则通过。
- 第一版发布前必须同时完成 TTS 与 STT 两个 provider；不能只完成 TTS 后先发布第一版。

火山语音模型当前不支持通过 Auto 或控制台切换使用，必须显式设置 Resource-Id：

```text
TTS: seed-tts-2.0
ASR: volc.seedasr.sauc.duration
```

## 9. 非目标

第一阶段不做：

- 大规模重写 Hermes core。
- 在 `main` 分支上直接改代码。
- 未确认 API schema 的专业数据集搜索实现。
- 未经用户明确授权并提供语音 API key 前，不直接做真实语音 API smoke test。
- 强制用户只能使用 fallback 模型列表中的模型。
- 强制用户迁移已有环境变量或 provider alias。

## 10. 分支策略

- 不在 `main` 上重构。
- 当前重构分支：`refactor/volcengine-hermes-next`
- 每个阶段独立提交。
- Phase 1 和 Phase 2 先不改公开行为太多，优先保证兼容。
