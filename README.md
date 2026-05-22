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
- **Durable Task Processing**: Volcengine Video Generation is asynchronous by nature. The plugin implements a resilient synchronous wrapper around the asynchronous task creation (`POST /api/plan/v3/contents/generations/tasks`) and background status polling (`GET /api/plan/v3/contents/generations/tasks/{id}`) lifecycle.
- **Real-Time Logs**: Prints the task creation status, Task ID, and current state (`queued`, `running`, etc.) directly to standard error (`sys.stderr`) to provide high visibility into the execution flow.

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
