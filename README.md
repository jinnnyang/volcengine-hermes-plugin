# Volcengine Doubao Plugin Integration for Hermes Agent (`volces-engine`)

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

Hermes Agent natively supports standard model backends (like OpenAI, FAL, etc.) but lacks built-in integrations for Volcano Engine (火山引擎). Volcano Engine provides high-quality foundation models, notably:
- **Doubao LLMs** (Agent and Coding plans)
- **Doubao Seedream 5.0** (State-of-the-art Image Generation)
- **Doubao Seedance 2.0** (Video Generation)

By leveraging Hermes Agent's extensibility, this project implements a set of customized plugins (`volces-engine`) to seamlessly register and use these models directly inside your agent profiles.

---

## Design & Architecture

Hermes Agent discovers different types of extensions through two distinct mechanisms:
1. **Model Providers**: Discovered and loaded at the system level via `providers/` scanner.
2. **Backends (Image/Video Gen)**: Loaded dynamically by Hermes' `PluginManager`.

Because of this, the integration is split into three independent plug-and-play plugins under the brand namespace `volces-engine`:

### 1. Model Provider Plugin
Registers a custom LLM provider profile (`volces-engine`) pointing to Volcano Engine's enterprise endpoint (`https://ark.cn-beijing.volces.com/api/plan/v3`). It registers the `doubao` alias alongside specific Coding/Agent plans.

### 2. Image Generation Plugin (`Seedream 5.0`)
A custom backend that handles:
- **Enterprise Endpoints**: Uses the `/api/plan/v3/images/generations` path required by enterprise plans.
- **Strict Size/Resolution Requirements**: Doubao Seedream 5.0 requires resolutions $\ge 3,686,400$ pixels. The plugin maps the standard aspect ratios as follows:
  - `landscape` $\rightarrow$ `2560x1440`
  - `square` $\rightarrow$ `2048x2048`
  - `portrait` $\rightarrow$ `1440x2560`
- **Timeouts & Reliability**: Separated connect (10s) and read (120s) timeouts using `httpx.Timeout` to prevent premature failures on slow generations.
- **Model Parameters**: Fully respects the `model` override parameter in generation calls (defaults to `doubao-seedream-5.0-lite`, with support for `doubao-seedream-5.0-pro`).
- **Resilient Error Handling**: Catches HTTP errors, extracts structured API error details when possible, logs warnings, and handles fallback.

### 3. Video Generation Plugin (`Seedance 2.0`)
A thin wrapper over Hermes Agent's built-in `VolcengineVideoGenProvider` that registers under the custom `volces-engine` provider namespace for consistency.

---

## Directory Structure

```
.
├── install.sh                  # Interactive installation script
├── README.md                   # English documentation
├── README_zh-CN.md             # Chinese documentation
└── plugins/
    ├── model-providers/
    │   └── volces-engine/
    │       ├── plugin.yaml     # Model provider metadata
    │       └── __init__.py     # Module-level registry call
    ├── image_gen/
    │   └── volces-engine/
    │       ├── plugin.yaml     # Image gen backend metadata
    │       └── __init__.py     # Seedream implementation & registration
    └── video_gen/
        └── volces-engine/
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
4. Uses Python to safely append/configure the plugins and active providers in `config.yaml` without breaking your existing settings.

### Manual Installation

If automatic installation is not available, you can copy and edit configurations manually:

1. **Copy the plugin folders** to your target Hermes profile's `plugins/` directory:
   ```bash
   cp -r plugins/model-providers/volces-engine [HERMES_HOME]/plugins/model-providers/
   cp -r plugins/image_gen/volces-engine [HERMES_HOME]/plugins/image_gen/
   cp -r plugins/video_gen/volces-engine [HERMES_HOME]/plugins/video_gen/
   ```
2. **Enable the plugins** in `[HERMES_HOME]/config.yaml`:
   ```yaml
   plugins:
     enabled:
       - image_gen/volces-engine
       - video_gen/volces-engine
   ```
3. **Configure the active backends** in `[HERMES_HOME]/config.yaml`:
   ```yaml
   image_gen:
     provider: volces-engine
     model: doubao-seedream-5.0-lite

   video_gen:
     provider: volces-engine
     model: doubao-seedance-2.0
   ```

---

## Configuration

To authorize API requests, add your Volcano Engine Ark API key to the profile's environment file (`[HERMES_HOME]/.env`):

```bash
ARK_API_KEY=your-volcengine-ark-api-key-here
```
*(Alternatively, the plugin also checks for the `VOLCENGINE_API_KEY` environment variable).*

---

## Usage

### 1. LLM Models
When the provider is registered, you can configure your default models or auxiliary models to use `volces-engine`:
```yaml
model:
  default: ark-code-latest
  provider: custom
  base_url: https://ark.cn-beijing.volces.com/api/plan/v3
  api_key: your-api-key
```

### 2. Image Generation
Using the Hermes CLI or agents, trigger image generation. The `volces-engine` backend will handle it:
```bash
hermes image "a futuristic neon metropolis at sunset" --aspect landscape
```
This maps to a `2560x1440` pixel generation request using `doubao-seedream-5.0-lite`.

To override the model to the pro variant, pass it in kwargs or via config:
```yaml
image_gen:
  provider: volces-engine
  model: doubao-seedream-5.0-pro
```

### 3. Video Generation
Generate video files using the Doubao Seedance backend:
```bash
hermes video "a hummingbird hovering next to a blooming flower"
```
This routes through the wrapped `volces-engine` video backend.
