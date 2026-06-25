# 07. 分阶段实施计划

## 0. 分支与工作方式

已确认：重构不能在 `main` 分支直接进行。

当前重构分支：

```bash
git checkout refactor/volcengine-hermes-next
```

当前阶段：P0/P1 核心能力已完成，本轮回到方案编辑状态，把当前完成状态和语音 provider 插件方向同步进规划；下一步进入 Voice-P1 + Voice-P2，完成 TTS 与 STT 后再进入第一版发布收尾。

每个阶段建议独立提交，便于回滚和 review。

## Phase 1：基础兼容与 endpoint 模式

状态：**已完成**。

目标：先让现有 provider 正确支持 Agent/Coding/API 三种模式。

任务：

1. 增加统一 base URL 解析逻辑。
2. 支持：
   - `VOLCENGINE_PLAN_MODE=agent|coding|api`
   - `VOLCENGINE_BASE_URL=...`
3. 保留现有 `VOLCENGINE_API_KEY` / `ARK_API_KEY`。
4. 更新 model provider metadata。
5. 保留历史 alias 和 `ark-code-latest`。

验收：

- 默认 `/api/plan/v3`。
- coding 模式 `/api/coding/v3`。
- api 模式 `/api/v3`。
- 自定义 base URL 优先。

## Phase 2：动态模型列表与用户选择

状态：**核心已完成**。

目标：让 Hermes 能获取动态模型列表，同时允许用户手动输入。

任务：

1. 实现 `{base_url}/models` 拉取。
2. 增加 fallback models。
3. 增加缓存。
4. 失败时 fallback 到内置列表。
5. README 说明用户可手动输入 model id。

验收：

- Mock `/models` 成功返回动态列表。
- Mock `/models` 失败返回 fallback。
- fallback 包含 `ark-code-latest`。

## Phase 3：图像和视频 provider 更新

状态：**已完成**。

目标：更新多模态默认模型和 payload。

任务：

1. 图像模型列表收窄到 `doubao-seedream-5.0-lite`。
2. 视频默认模型改为 `doubao-seedance-1.5-pro`。
3. 视频 payload 补传 `resolution` 等字段。
4. 改进 Coding Plan 下多模态错误提示。

验收：

- 图像默认和列表正确。
- 视频默认模型正确。
- 视频 payload 测试通过。

## Phase 4：Volcengine Web Search Provider

状态：**已完成**。

目标：实现豆包搜索作为 Hermes `web_search` backend。

任务：

1. 新增 `plugins/web/volcengine`。
2. 实现 `VolcengineWebSearchProvider`。
3. 支持 API Key 优先级：
   - `VOLCENGINE_SEARCH_API_KEY`
   - `WEB_SEARCH_API_KEY`
   - `ASK_ECHO_SEARCH_INFINITY_API_KEY`
   - `VOLCENGINE_API_KEY`
   - `ARK_API_KEY`
4. 调用 direct API：
   - `POST https://open.feedcoopapi.com/search_api/web_search`
5. 返回 Hermes 标准 web result shape。
6. 实现 `get_setup_schema()`。
7. 增加 mock 测试。

验收：

- `hermes config set web.search_backend volcengine` 可用。
- `web_search` 返回 `data.web`。
- API 错误映射清晰。

## Phase 5：Volcengine 语音 Provider

状态：**已确认纳入第一版发布门槛，TTS + STT 都完成后再发布第一版**。

目标：把豆包语音合成与语音识别注册为 Hermes 标准 TTS / STT backend。

任务：

1. 新增 `plugins/tts/volcengine`。
2. 实现 `VolcengineTTSProvider` 并通过 `ctx.register_tts_provider()` 注册。
3. TTS 首版使用 HTTP POST 接口：`https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional`。
4. TTS Resource-Id 默认 `seed-tts-2.0`，model 默认 `doubao-seed-tts-2.0`，voice 默认 `zh_female_vv_uranus_bigtts`，输出格式默认 `wav`。
5. 新增 `plugins/transcription/volcengine`。
6. 实现 `VolcengineTranscriptionProvider` 并通过 `ctx.register_transcription_provider()` 注册。
7. STT 首版使用 WebSocket 单流接口：`wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_nostream`。
8. STT Resource-Id 默认 `volc.seedasr.sauc.duration`，model 默认 `doubao-seed-asr-2.0`，language 默认自动识别，WebSocket 客户端使用 `websockets`。
9. 支持 API Key 优先级：
   - `VOLCENGINE_SPEECH_API_KEY`
   - `VOLCENGINE_API_KEY`
   - `ARK_API_KEY`
10. 增加 mock 测试，不默认跑真实 API；按 TDD 顺序先写 TTS 测试再实现 TTS，再写 STT 测试再实现 STT。

验收：

- `tts.provider=volcengine` 时 `text_to_speech` 写出音频文件。
- `stt.provider=volcengine` 时语音转写返回 Hermes 标准 envelope。
- 请求头包含 `X-Api-Key` 与正确的 `X-Api-Resource-Id`。
- 真实授权后 TTS→STT roundtrip 通过：TTS 生成 wav，STT 转写文本与原文相等。
- 真实 API smoke test 仅在用户明确授权并提供测试 key 后执行。
- 第一版发布前必须同时满足 TTS 与 STT 的 mock 测试、安装配置和 README 使用说明。

详细方案见 [`12-voice-provider-plan.md`](12-voice-provider-plan.md)。

## Phase 6：安装脚本与公开用户体验

目标：让其他用户能顺利安装和配置。

任务：

1. 改造 `install.sh`。
2. 支持 `--mode agent|coding|api`。
3. 支持 `--base-url`。
4. 支持 `--enable-web-search`。
5. 支持 `--enable-tts` / `--enable-stt`。
6. 支持 `--dry-run`。
7. 修改配置前备份。
8. 重复运行 idempotent。

验收：

- 临时 profile 测试通过。
- 真实 profile dry-run 输出正确。
- 不覆盖用户已有配置。
- 可同时配置 `tts.provider=volcengine` 与 `stt.provider=volcengine`。

## Phase 7：测试体系

目标：所有核心行为可自动验证。

任务：

1. 引入 pytest。
2. 增加 mock HTTP 测试。
3. 增加语音 provider mock 测试。
4. 增加 install script 测试。
5. 可选增加 GitHub Actions。

验收：

```bash
uv run pytest
```

全部通过。

## Phase 8：文档发布

目标：让公开用户看 README 即可使用。

任务：

1. 更新英文 README。
2. 更新中文 README。
3. 新增配置示例。
4. 新增搜索 backend 使用说明。
5. 新增语音 TTS / STT provider 使用说明。
6. 新增常见错误码。
7. 新增卸载说明。

验收：

- 新用户能从 README 完成安装。
- Agent Plan / Coding Plan / Ark API 三种路径说明清楚。
- 搜索能力说明为 Hermes `web_search` backend，不误导成 MCP 主线。
- 语音能力说明为 Hermes TTS / STT provider，不误导成普通 tool。
- 第一版发布说明中 TTS 与 STT 均为已支持能力，而不是 roadmap。

## Phase 9：后续增强

候选增强：

1. AK/SK 签名方式支持豆包搜索。
2. 专业数据集搜索普通 tool。
3. Agent/Coding Plan 管控 API 模型列表。
4. 图像/视频模型动态列表。
5. 更完整的 `hermes setup` 集成体验。
6. 打包为 pip plugin / 插件 registry。
7. TTS WebSocket 双向/单向流式支持。
8. ASR WebSocket 双流实时识别支持。

## 建议提交边界

| 提交 | 内容 |
|---|---|
| commit 1 | docs/refactor 方案文档 |
| commit 2 | base URL resolver + tests |
| commit 3 | model provider dynamic models + tests |
| commit 4 | image/video provider updates + tests |
| commit 5 | web search provider + tests |
| commit 6 | tts provider + tests |
| commit 7 | stt provider + tests |
| commit 8 | install script improvements + tests |
| commit 9 | README updates |

## 风险控制

- 每阶段先写测试再改代码。
- 不删除历史 alias。
- 不强制迁移 env var。
- 真实 API smoke test 需用户明确提供 key 并确认。
- 如果火山 API 返回与文档不一致，以真实 API 响应修正 provider。
