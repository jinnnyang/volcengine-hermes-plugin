# 14. Voice Dictation 调试日志：安装、激活、使用闭环

本文持续记录本次会话中 Hermes Desktop Voice Dictation 接入 Volcengine STT provider 时出现的报错、原因判断、验证证据与修复方案。最终会整理进 README 的“安装 -> 激活 -> 使用 / 排障”章节。

## 2026-06-25：Desktop voice dictation 第一次报错

### 用户看到的错误

```text
Error occurred in handler for 'hermes:api': Error: Timed out connecting to Hermes backend after 15000ms
```

### 配置状态

当时 `stt.provider` 仍是：

```yaml
stt:
  enabled: true
  provider: local
```

虽然 `transcription/volcengine` 插件已经启用并注册成功，但 Hermes voice dictation 仍走内置 local STT。

### 后端日志证据

日志显示 local STT 首次使用时触发：

```text
Lazy-installing faster-whisper==1.2.1 sounddevice==0.5.5 numpy==2.4.3 for feature 'stt.faster_whisper'
Loading faster-whisper model 'base' (first load downloads the model)...
Local transcription failed: Got: ConnectTimeout: [WinError 10060]
huggingface_hub.errors.LocalEntryNotFoundError
```

### 原因判断

这不是 Volcengine STT provider 被调用失败，而是：

```text
stt.provider=local
→ Hermes 内置 faster-whisper
→ 首次加载 base 模型，需要从 HuggingFace 下载
→ 网络连接 HuggingFace 超时
→ Desktop 等 backend API 超过 15 秒
→ Electron 侧统一显示 Hermes backend timeout
```

### 已执行方案

切换 devops profile：

```yaml
stt:
  enabled: true
  provider: volcengine
  volcengine:
    model: doubao-seed-asr-2.0
    language: auto
```

后端路由验证显示：

```text
Transcribing with plugin STT provider 'volcengine'...
RESULT_PROVIDER=volcengine
```

结论：local faster-whisper / HuggingFace 路径已被绕开。

## 2026-06-25：Desktop voice dictation 第二次报错

### 用户看到的错误

```text
Error occurred in handler for 'hermes:api': Error: 400: {"detail":"no close frame received or sent"}
```

### 后端日志证据

日志已出现：

```text
INFO tools.transcription_tools: Transcribing with plugin STT provider 'volcengine'...
```

说明 Desktop voice dictation 已经真实进入 `transcription/volcengine` provider，不再走 local whisper。

### 初步原因判断

当前 `plugins/transcription/volcengine` 的 ASR WebSocket 实现不符合 Volcengine ASR V3 二进制协议：

1. 初始 full client request frame 缺少 sequence 字段。
2. 音频分片被直接 `websocket.send(chunk)` 发送为裸音频 bytes，而不是 ASR V3 `AUDIO_ONLY_REQUEST` 二进制 frame。
3. 没有发送带负 sequence 的最终 audio-only frame 来标记音频结束。
4. response parser 只按 `header + payload_size + gzip JSON` 解析，未处理 ASR V3 的 sequence、ACK、error response、last package flags。
5. 可能还存在 endpoint 路径差异：当前代码使用 `wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_nostream`，公开文档显示为 `wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream`。需要用真实 smoke test 验证。

### 方案

按 TDD 修复：

1. 先补协议单测，覆盖：
   - full client request 带正 sequence；
   - audio-only request 带正 sequence；
   - final audio-only request 带负 sequence；
   - parse server full response / ACK / error / last package。
2. 修复 `protocol.py`，实现 Volcengine ASR V3 frame builder/parser。
3. 修复 `provider.py`，发送顺序改为：

```text
connect websocket
send full client request sequence=1
send audio-only request sequence=2..N for each chunk
send final empty audio-only request sequence=-N
receive and parse frames until last package or transcript available
close websocket normally
```

4. 目标测试通过后复制插件到 devops profile，再让 Desktop voice dictation 复测。

### 已执行修复与新现象

已按 TDD 补充协议测试，初始 RED 失败点包括：

```text
build_full_client_request() got an unexpected keyword argument 'sequence'
module has no attribute 'build_audio_only_request'
gzip.BadGzipFile
```

随后已修复：

- `protocol.py`：新增 ASR V3 sequence-aware full client request、audio-only request、final audio marker、server ACK/error/last response parser。
- `provider.py`：音频发送从裸 bytes 改为 `AUDIO_ONLY_REQUEST` frame；发送最后一个空音频负 sequence frame；循环读取响应直到 last package。
- endpoint 恢复为用户提供的 Agent Plan Base URL：`wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_nostream`；之前改成非 `/plan/` 路径是错误方向。

测试结果：

```text
uv run pytest tests/test_transcription_provider.py -q
......... [100%]
uv run pytest -q
...................................................... [100%]
git diff --check
通过
```

把插件复制/同步到 devops profile 后，用同一个 Hermes transcription 公共入口做路由/协议 probe，结果已经继续走插件：

```text
INFO tools.transcription_tools: Transcribing with plugin STT provider 'volcengine'...
RESULT_PROVIDER=volcengine
RESULT_SUCCESS=False
RESULT_ERROR_HEAD=server rejected WebSocket connection: HTTP 401
```

该新错误说明：WebSocket 协议构造层已经前进到 handshake 鉴权阶段；当前阻塞点从“连接非正常关闭 / no close frame”转为“服务端拒绝鉴权 HTTP 401”。已根据用户补充的 Agent Plan 配置确认：TTS Resource-Id 必须为 `seed-tts-2.0`，ASR Resource-Id 必须为 `volc.seedasr.sauc.duration`，语音模型不支持通过 Auto 或控制台切换；ASR endpoint 包括双流实时 `wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_async` 与单流高精度 `wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_nostream`。当前 Hermes provider 默认选择单流 `bigmodel_nostream`，因为 Hermes voice dictation 当前传入的是完整录音文件，优先匹配“发送完成后统一返回高精度结果”的场景。下一步优先在该 endpoint 上核对 handshake header 与 API Key 类型。
