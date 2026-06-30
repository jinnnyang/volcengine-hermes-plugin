# Volcengine Doubao Plugin Integration for Hermes Agent (`volcengine`)

This repository provides Volcengine / Doubao backend providers for Hermes Agent:

- LLM model provider: Agent Plan, Coding Plan, and standard Ark API endpoint modes.
- Image generation: Doubao Seedream.
- Video generation: Doubao Seedance.
- Web search: Volcengine / Doubao Search backend for Hermes `web_search`.
- Text to speech: Doubao Seed TTS backend for Hermes `text_to_speech`.
- Speech to text: Doubao Seed ASR backend for Hermes transcription / voice input.

The provider name used by Hermes runtime configuration is `volcengine`.

## Directory structure

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

## Naming model

Hermes uses several names at different layers:

| Layer | Example | Purpose |
|---|---|---|
| Manifest `id` | `speech-to-text-volcengine` | Stable plugin bundle identifier in `plugin.yaml`. |
| Manifest `name` | `Volcengine Speech to Text Provider` | Human-readable display name in `hermes plugins list`. |
| Plugin registry key | `transcription/volcengine` | Path-derived enable key stored in `plugins.enabled`. |
| Runtime provider name | `volcengine` | Value selected by `tts.provider`, `stt.provider`, `web.search_backend`, etc. |

For voice, Hermes' plugin directory category is `transcription`, while the runtime config section is `stt`. Volcengine's product terminology is ASR.

## Installation

### Automatic installation

Run from the repository root:

```bash
bash install.sh
```

The installer scans for Hermes Agent profile directories, prompts you to choose one, copies the selected plugin folders, backs up `config.yaml`, enables plugin registry keys with de-duplication, and writes non-secret provider defaults.

Common non-interactive example:

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

Useful options:

```text
--mode agent|coding|api      Write VOLCENGINE_PLAN_MODE to .env.
--base-url URL               Write VOLCENGINE_BASE_URL to .env.
--profile PATH               Install to a specific Hermes profile.
--dry-run                    Print actions without changing files.
--no-config                  Copy plugins only; do not edit config.yaml or .env.
--no-tts / --no-stt          Skip TTS or STT installation if not needed.
```

Secrets are never written to `config.yaml`. Put keys in the target profile `.env`:

```bash
VOLCENGINE_API_KEY=[REDACTED]
```

`VOLCENGINE_API_KEY` is the shared key used by all Volcengine services. The current providers also fall back to `ARK_API_KEY` for compatibility.

After installation, restart Hermes Agent or reset the session so newly enabled plugins are loaded.

### Manual installation

Copy plugin folders to your Hermes profile's `plugins` directory:

```bash
# Where `[HERMES_PROFILE]` is the path to your Hermes profile (~/.hermes/profiles/<name>):
cp -r plugins/_volcengine_common [HERMES_PROFILE]/plugins/
cp -r plugins/model-providers/volcengine [HERMES_PROFILE]/plugins/model-providers/
cp -r plugins/image_gen/volcengine [HERMES_PROFILE]/plugins/image_gen/
cp -r plugins/video_gen/volcengine [HERMES_PROFILE]/plugins/video_gen/
cp -r plugins/web/volcengine [HERMES_PROFILE]/plugins/web/
cp -r plugins/tts/volcengine [HERMES_PROFILE]/plugins/tts/
cp -r plugins/transcription/volcengine [HERMES_PROFILE]/plugins/transcription/
```

#### Linux / macOS
For development (link from repo to profile so changes are live after git pull):
```bash
# Replace `~/projects/volcengine-hermes-plugin` with your repo clone path:
for d in _volcengine_common model-providers/volcengine image_gen/volcengine video_gen/volcengine web/volcengine tts/volcengine transcription/volcengine; do
  ln -sf ~/projects/volcengine-hermes-plugin/plugins/$d ~/.hermes/profiles/devops/plugins/$d
done
```

#### Windows (git-bash / MSYS)
For development (junction from repo to profile):
```bash
# Replace `C:\Users\yourname\projects\volcengine-hermes-plugin` with your repo clone path:
for d in _volcengine_common model-providers/volcengine image_gen/volcengine video_gen/volcengine web/volcengine tts/volcengine transcription/volcengine; do
  cmd //c mklink /J ^
C:\\Users\\yourname\\AppData\\Local\\hermes\\profiles\\devops\\plugins\\$d ^
C:\\Users\\yourname\\projects\\volcengine-hermes-plugin\\plugins\\$d
done
```
(Use elevated terminal for `mklink` if you get "permission denied".)

Enable plugin registry keys in `[HERMES_PROFILE]/config.yaml`:

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

Configure active providers in `[HERMES_PROFILE]/config.yaml`:

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

Put secrets in `[HERMES_PROFILE]/.env`, **never in `config.yaml`**:

```bash
# At least one of these is required:
VOLCENGINE_API_KEY=[your-ark-api-key]
# ARK API key also works as a fallback:
ARK_API_KEY=[your-ark-api-key]
```

```

## Endpoint modes

The shared config helper resolves the Volcengine Ark base URL as follows:

1. `VOLCENGINE_BASE_URL`, if explicitly set.
2. `VOLCENGINE_PLAN_MODE`, mapped to:
   - `agent` → `https://ark.cn-beijing.volces.com/api/plan/v3`
   - `coding` → `https://ark.cn-beijing.volces.com/api/coding/v3`
   - `api` → `https://ark.cn-beijing.volces.com/api/v3`
3. Agent Plan by default.

## Capabilities

### LLM model provider

The model provider registers the runtime provider name `volcengine` and supports dynamic `/models` discovery with fallback models, including `ark-code-latest`.

### Image generation

Default model:

```text
doubao-seedream-5.0-lite
```

The image provider is text-to-image only and maps aspect ratios to high-resolution sizes suitable for Volcengine image endpoints.

### Video generation

Default model:

```text
doubao-seedance-1.5-pro
```

The video provider wraps Volcengine's async task lifecycle with synchronous polling and returns a local cached video path when generation succeeds.

### Web search

The web provider registers a Hermes `web_search` backend named `volcengine` and is selected with:

```yaml
web:
  search_backend: volcengine
```

### Text to speech

The TTS provider registers with Hermes via `ctx.register_tts_provider(...)` and is selected with:

```yaml
tts:
  provider: volcengine
```

Three TTS endpoints are provided (aligned with Agent Plan):

| Endpoint | Protocol | URL | Recommended for |
|----------|----------|-----|------------------|
| Unidirectional HTTP | HTTP POST | `https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional` | Non-streaming synthesis, default. |
| Bidirectional streaming | WebSocket | `wss://openspeech.bytedance.com/api/v3/plan/tts/bidirection` | Real-time streaming synthesis. |
| Streaming output | WebSocket | `wss://openspeech.bytedance.com/api/v3/plan/tts/unidirectional/stream` | Unidirectional request with streaming output. |

Defaults:

```text
model: doubao-seed-tts-2.0
resource id: seed-tts-2.0
voice: zh_female_vv_uranus_bigtts
format: wav
sample_rate: 24000
endpoint: unidirectional HTTP
```

### Speech to text / transcription

The STT provider registers with Hermes via `ctx.register_transcription_provider(...)` and is selected with:

```yaml
stt:
  enabled: true
  provider: volcengine
```

Two ASR endpoints are provided (both WebSocket, aligned with Agent Plan):

| Endpoint | URL | Recommended for |
|----------|-----|------------------|
| Single-stream (nostream) | `wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_nostream` | Accuracy-first scenarios: send full audio after recording, unified result returned when upload completes. This is the default for Hermes voice dictation (record-first then transcribe). |
| Async / dual-stream | `wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_async` | Low-latency real-time scenarios: stream audio and get incremental recognition results. Available for future Hermes real-time voice interfaces. |

Defaults:

```text
model: doubao-seed-asr-2.0
resource id: volc.seedasr.sauc.duration
endpoint: single-stream (bigmodel_nostream)
language: auto
```

The implementation uses the `websockets` Python package and keeps the Volcengine ASR binary protocol helpers in `plugins/transcription/volcengine/protocol.py`.

## Verification

Run the test suite:

```bash
uv run pytest -q
```

Check plugin enablement in a Hermes profile:

```bash
hermes plugins list --plain --enabled
```

Expected registry keys include:

```text
model-providers/volcengine
image_gen/volcengine
video_gen/volcengine
web/volcengine
tts/volcengine
transcription/volcengine
```

A real TTS → STT roundtrip smoke test should only be run after explicitly providing a valid speech API key in `.env`.
