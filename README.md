# Volcengine Doubao Plugin Integration for Hermes Agent (`volcengine`)

This plugin integration adds native support for Volcano Engine (火山引擎) models—specifically Doubao LLMs, Doubao Seedream (image generation), and Doubao Seedance (video generation)—into Hermes Agent.

## Table of Contents
- [Motivation](#motivation)
- [Design & Architecture](#design--architecture)
- [Directory Structure](#directory-structure)
- [Installation](#installation)
  - [Automatic Installation](#automatic-installation)
  - [Manual Installation](#manual-installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [1. LLM Models](#1-llm-models)
  - [2. Image Generation](#2-image-generation)
  - [3. Video Generation](#3-video-generation)

---

## Motivation

Hermes Agent natively supports standard model backends but lacks flexible, full-featured integrations for Volcano Engine (火山引擎). Volcano Engine provides high-quality foundation models, notably:
- **Doubao LLMs** (Agent and Coding plans)
- **Doubao Seedream** (Image Generation)
- **Doubao Seedance** (Video Generation)

By leveraging Hermes Agent's extensibility, this project implements a set of customized plugins (`volcengine`) to seamlessly register and use these models directly inside your agent profiles.

---

## Design & Architecture

Hermes Agent discovers different types of extensions through two distinct mechanisms:
1. **Model Providers**: Discovered and loaded at the system level via `providers/` scanner.
2. **Backends (Image/Video Gen)**: Loaded dynamically by Hermes' `PluginManager`.

This integration is split into three independent plug-and-play plugins under the standard namespace `volcengine`:

### 1. Model Provider Plugin
Registers a custom LLM provider profile (`volcengine`) pointing to Volcano Engine's enterprise endpoint (`https://ark.cn-beijing.volces.com/api/plan/v3`). It registers the `doubao` and `volces-engine` aliases to maintain complete backward compatibility with older configuration structures.

### 2. Image Generation Plugin (`Seedream`)
A custom backend that handles:
- **State Transparency (No Black-Box)**: Visual initialization and execution logs are printed directly to standard error (`sys.stderr`) when loading and calling the plugin so developers always know the plugin's status.
- **Enterprise Endpoints**: Uses the `/api/plan/v3/images/generations` path required by enterprise plans.
- **Dynamic Resolution Mappings**:
  - **Seedream 5.0** (e.g. `doubao-seedream-5.0-lite`, `doubao-seedream-5.0-pro`): Requires high resolutions ($\ge 3.68$ megapixels) to prevent API validation failures:
    - `landscape` $\rightarrow$ `2560x1440`
    - `square` $\rightarrow$ `2048x2048`
    - `portrait` $\rightarrow$ `1440x2560`
  - **Seedream 4.0** (e.g. `doubao-seedream-4.0`): Falls back to standard resolution options:
    - `landscape` $\rightarrow$ `1792x1024`
    - `square` $\rightarrow$ `1024x1024`
    - `portrait` $\rightarrow$ `1024x1792`
- **Timeouts & Reliability**: Separated connect (10s) and read (120s) timeouts using `httpx.Timeout` to prevent premature failures on slow generations.

### 3. Video Generation Plugin (`Seedance 2.0`)
- **Durable Task Processing & Guidance**: Volcengine Video Generation is asynchronous by nature, typically taking **2 to 3 minutes**. The plugin implements a resilient synchronous wrapper around the asynchronous task creation (`POST /api/plan/v3/contents/generations/tasks`) and background status polling (`GET /api/plan/v3/contents/generations/tasks/{id}`) lifecycle. The tool call blocks during this period, and the agent is guided to wait patiently without interrupting.
- **Real-Time Logs & Polling**: Automatically polls the task status every 10 seconds. It prints the task creation status, Task ID, and current states (`queued`, `running`, `succeeded`) directly to standard error (`sys.stderr`) to provide maximum visibility and resolve any "black-box" loader state issues.
- **Automatic Downloading & Local Caching**: Once video generation succeeds, the plugin **automatically downloads the video file** from the temporary remote URL and caches it locally under the profile's video cache folder (matching the local-saving behavior of image generation). The returned `video` reference contains the absolute local filesystem path (e.g., `/opt/data/profiles/athena/cache/videos/volc_...mp4`), making it fully offline-accessible.

---

## Directory Structure

```
.
├── install.sh                  # Interactive installation script
├── README.md                   # English documentation
├── README_zh-CN.md             # Chinese documentation
└── plugins/
    ├── model-providers/
    │   └── volcengine/
    │       ├── plugin.yaml     # Model provider metadata
    │       └── __init__.py     # Module-level registry call & alias exports
    ├── image_gen/
    │   └── volcengine/
    │       ├── plugin.yaml     # Image gen backend metadata
    │       └── __init__.py     # Seedream implementation & registration
    └── video_gen/
        └── volcengine/
            ├── plugin.yaml     # Video gen backend metadata
            └── __init__.py     # Seedance wrapper & registration
```

---

## Installation

### Automatic Installation

An interactive installer `install.sh` is provided in the repository. It automatically scans your environment to locate active Hermes Agent profile homes (detecting folders with `SOUL.md`, `config.yaml`, and `home/`), lists them, and prompts you to select one.

Run the installer via:
```bash
bash install.sh
```

**What the installer does:**
1. Detects profile paths (e.g. `~/.hermes` or `/opt/data/profiles/athena`).
2. Prompts you to pick a target directory.
3. Copies the plugin code to the correct folder structure in that profile.
4. Cleans up older `volces-engine` plugin folders.
5. Uses Python to safely append/configure the plugins and active providers in `config.yaml` without breaking your existing settings.

### Manual Installation

If automatic installation is not available, you can copy and edit configurations manually:

1. **Copy the plugin folders** to your target Hermes profile's `plugins/` directory:
   ```bash
   cp -r plugins/model-providers/volcengine [HERMES_HOME]/plugins/model-providers/
   cp -r plugins/image_gen/volcengine [HERMES_HOME]/plugins/image_gen/
   cp -r plugins/video_gen/volcengine [HERMES_HOME]/plugins/video_gen/
   ```
2. **Enable the plugins** in `[HERMES_HOME]/config.yaml`:
   ```yaml
   plugins:
     enabled:
       - image_gen/volcengine
       - video_gen/volcengine
   ```
3. **Configure the active backends** in `[HERMES_HOME]/config.yaml`:
   ```yaml
   image_gen:
     provider: volcengine
     model: doubao-seedream-5.0-lite

   video_gen:
     provider: volcengine
     model: doubao-seedance-2.0
   ```

---

## Agent Guidance (智能体引导机制)

To ensure that the calling LLM Agent operates with high efficiency and avoids confusion, this plugin implements a dedicated **Agent Guidance Mechanism**. Every tool execution response (both successful results and failure responses) returns a structured `"agent_guidance"` field in its JSON payload.

### Core Capabilities of the Guidance:
1. **Expected Durations**: Communicates standard timeframes to the Agent (e.g., images take ~8-25s, videos take ~2-3m).
2. **Synchronous Polling Details**: Explains the task status (for image generation, it's synchronous and already complete; for video generation, the tool's internal polling loop has fully executed and finished).
3. **Local Cache Handling & Rendering**: Concrete recommendations for rendering (such as displaying the file locally using the standard markdown notation `![description](file://<path>)`) and explicitly urging the Agent to directly present the result to the user instead of querying further or re-generating the file.
4. **Actionable Troubleshooting**: If an execution fails, it guides the Agent step-by-step on how to inspect environment variables (`VOLCENGINE_API_KEY`) and account permissions.

#### Success Payload Example:
```json
{
  "success": true,
  "image": "/opt/data/profiles/athena/cache/images/volc_doubao-seedream-5.0-lite_20260522_081344_72a34af6.png",
  "model": "doubao-seedream-5.0-lite",
  "prompt": "a simple red dot",
  "aspect_ratio": "landscape",
  "provider": "volcengine",
  "size": "2560x1440",
  "agent_guidance": "[AGENT GUIDANCE]\n- 预计耗时 (Estimated Duration): Doubao Seedream 5.0 Lite/Pro 耗时约 10s-25s，Seedream 4.0 约 8s。\n- 任务状态 (Task Status): 该任务为同步生成，已实时阻塞并成功完成。图片文件已下载保存。\n- 本地文件 (Local File): 图片已成功缓存到本地。请使用绝对路径展示该图片，例如：![图片](file:///opt/data/profiles/athena/cache/images/volc_doubao-seedream-5.0-lite_20260522_081344_72a34af6.png)。\n- 渲染/后续建议: 图像生成任务已全部成功完成，请直接展示给用户，无需重复调用生成。"
}
```

---

## Configuration

To authorize API requests, configure your Volcano Engine Ark API key. The primary environment variable is `VOLCENGINE_API_KEY`, with `ARK_API_KEY` supported as a secondary fallback:

Add to your environment file (`[HERMES_HOME]/.env`):
```bash
VOLCENGINE_API_KEY=your-volcengine-api-key-here
```

---

## Usage

### 1. LLM Models
When the provider is registered, you can configure your default models or auxiliary models to use `volcengine`:
```yaml
model:
  default: ark-code-latest
  provider: custom
  base_url: https://ark.cn-beijing.volces.com/api/plan/v3
  api_key: your-api-key
```

### 2. Image Generation
Using the Hermes CLI or agents, trigger image generation. The `volcengine` backend will handle it:
```bash
hermes image "a futuristic neon metropolis at sunset" --aspect landscape
```
This maps to a `2560x1440` pixel generation request using `doubao-seedream-5.0-lite`.

To override the model to the pro or v4 variants, pass it in kwargs or via config:
```yaml
image_gen:
  provider: volcengine
  model: doubao-seedream-5.0-pro
```

### 3. Video Generation
Generate video files using the Doubao Seedance backend:
```bash
hermes video "a hummingbird hovering next to a blooming flower"
```
This routes through the wrapped `volcengine` video backend. Stderr logs will track task creation and polling.
