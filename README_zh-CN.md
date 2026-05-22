# 火山引擎豆包插件与 Hermes Agent 集成 (`volcengine`)

本集成插件为 Hermes Agent 提供了对火山引擎（Volcengine）模型的原生支持，包括豆包大语言模型（Doubao LLM）、豆包图像生成大模型（Doubao Seedream）和豆包视频生成大模型（Doubao Seedance）。

## 目录
- [起因与背景](#起因与背景)
- [设计思路与架构](#设计思路与架构)
- [目录结构](#目录结构)
- [安装方法](#安装方法)
  - [自动安装（推荐）](#自动安装推荐)
  - [手动安装](#手动安装)
- [配置说明](#配置说明)
- [使用方法](#使用方法)
  - [1. LLM 大语言模型](#1-llm-大语言模型)
  - [2. 图像生成](#2-图像生成)
  - [3. 视频生成](#3-视频生成)

---

## 起因与背景

Hermes Agent 原生支持一系列标准模型供应商，但缺乏对火山引擎（火山方舟）的柔性、全功能支持。火山引擎提供了行业领先的基础模型：
- **豆包大语言模型**（提供 Agent Plan / Coding Plan）
- **豆包 Seedream**（图像生成）
- **豆包 Seedance**（视频生成）

为了在 Hermes Agent 智能体中无缝使用这些模型，我们基于 Hermes Agent 的插件系统开发了 `volcengine` 插件包，将这些模型作为一等公民（First-class providers）注册到 Agent 的配置体系中。

---

## 设计思路与架构

Hermes Agent 发现和加载不同类型的扩展采用了两种独立机制：
1. **模型供应商 (Model Providers)**：由系统级 `providers/` 目录扫描器自动加载并发现。
2. **生成式后端 (Image/Video Gen)**：由 Hermes 核心的 `PluginManager` 动态发现并装载。

因此，本集成方案在 `volcengine` 标准命名空间下被拆分为三个独立的插件：

### 1. 模型供应商插件 (Model Provider)
注册一个名为 `volcengine` 的自定义 LLM provider profile，指向火山引擎企业级端点（`https://ark.cn-beijing.volces.com/api/plan/v3`）。它同时注册了 `doubao` 和 `volces-engine` 别名，确保与旧配置结构的完整向后兼容。

### 2. 图像生成插件 (`Seedream`)
这是一款高度定制的图像生成后端，重点实现了以下技术细节：
- **状态透明化（解决黑盒状态）**：在插件加载与执行时，直接向标准错误输出（`sys.stderr`）打印显式的初始化与执行日志（例如 `[volcengine] ...`），方便开发者了解插件的工作状态。
- **企业级端点适配**：使用企业方案专用的 `/api/plan/v3/images/generations` API 路径。
- **动态分辨率映射**：
  - **Seedream 5.0**（如 `doubao-seedream-5.0-lite`、`doubao-seedream-5.0-pro`）：要求高分辨率（$\ge 3.68$ 百万像素），防止 API 校验失败：
    - `landscape` (横屏) $\rightarrow$ `2560x1440`
    - `square` (方形) $\rightarrow$ `2048x2048`
    - `portrait` (竖屏) $\rightarrow$ `1440x2560`
  - **Seedream 4.0**（如 `doubao-seedream-4.0`）：自动降级为标准分辨率：
    - `landscape` (横屏) $\rightarrow$ `1792x1024`
    - `square` (方形) $\rightarrow$ `1024x1024`
    - `portrait` (竖屏) $\rightarrow$ `1024x1792`
- **超长请求超时**：使用 `httpx.Timeout` 分离了连接超时（10s）与读取超时（120s），防止由于高分辨率图片生成慢而导致网络请求提前超时。

### 3. 视频生成插件 (`Seedance 2.0`)
- **异步任务生命周期管理**：火山视频生成 API 是异步的。本插件在同步的 `generate` 方法中，实现了一套稳健的异步协程包装器，包含了任务提交（`POST /api/plan/v3/contents/generations/tasks`）和后台状态轮询（`GET /api/plan/v3/contents/generations/tasks/{id}`）。
- **实时输出日志**：生成过程中，会将创建状态、任务 ID 以及当前轮询状态（`queued`, `running` 等）实时打印到标准错误（`sys.stderr`），保证执行过程清晰透明。

---

## 目录结构

```
.
├── install.sh                  # 交互式自动安装脚本
├── README.md                   # 英文文档
├── README_zh-CN.md             # 中文文档
└── plugins/
    ├── model-providers/
    │   └── volcengine/
    │       ├── plugin.yaml     # LLM 供应商元数据
    │       └── __init__.py     # 模块级注册入口及别名导出
    ├── image_gen/
    │   └── volcengine/
    │       ├── plugin.yaml     # 图像生成后端元数据
    │       └── __init__.py     # Seedream 逻辑及注册实现
    └── video_gen/
        └── volcengine/
            ├── plugin.yaml     # 视频生成后端元数据
            └── __init__.py     # Seedance 异步包装与注册实现
```

---

## 安装方法

### 自动安装（推荐）

我们在项目根目录提供了一个交互式安装脚本 `install.sh`。它能自动扫描当前系统环境下的所有 Hermes Agent Profile 目录（通过识别目录下是否包含 `SOUL.md`、`config.yaml` 和 `home/` 子目录），列出来并等待你选择安装。

运行以下命令执行安装：
```bash
bash install.sh
```

**脚本的自动化处理逻辑：**
1. 自动扫描候选路径（如 `~/.hermes` 或 `/opt/data/profiles/athena`）。
2. 列出检测到的 Profile 目录，用户输入对应序号并回车确认。
3. 自动将插件文件拷贝到对应 Profile 的插件目录。
4. 自动清除目标 Profile 中可能残留的旧版 `volces-engine` 插件目录。
5. 使用 Python 脚本安全地修改该 Profile 下的 `config.yaml` 文件：自动向 `plugins.enabled` 追加启用项，并将 `image_gen` 和 `video_gen` 的 provider 字段切换为 `volcengine`，不破坏用户原有的其它配置。

### 手动安装

如果您的环境无法运行自动脚本，请按照以下步骤手动部署：

1. **拷贝插件文件夹**至您的 Hermes Profile 对应的 `plugins/` 目录：
   ```bash
   cp -r plugins/model-providers/volcengine [HERMES_HOME]/plugins/model-providers/
   cp -r plugins/image_gen/volcengine [HERMES_HOME]/plugins/image_gen/
   cp -r plugins/video_gen/volcengine [HERMES_HOME]/plugins/video_gen/
   ```
2. **在配置文件中启用插件**：打开 `[HERMES_HOME]/config.yaml`，并在 `plugins.enabled` 列表下追加：
   ```yaml
   plugins:
     enabled:
       - image_gen/volcengine
       - video_gen/volcengine
   ```
3. **配置默认生成后端**：在 `[HERMES_HOME]/config.yaml` 中，更新对应的 provider 配置：
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

为了确保调用的 LLM Agent 能够高效操作并避免混淆，本插件实现了一套专用的**智能体引导机制**（Agent Guidance Mechanism）。每一次工具执行的响应中（无论是成功还是失败），其 JSON 结构中都会附加一个专门的 `"agent_guidance"` 字段。

### 引导机制的核心能力：
1. **预估耗时引导**：告知 Agent 标准执行时间（例如：图片生成需要 8s-25s，视频生成需要 2-3 分钟），让 Agent 能够合理预期并对用户进行安抚。
2. **任务状态透明**：说明当前任务的处理逻辑（图像生成是同步的，已经实时阻塞并完成；视频生成是异步的，但工具内置了同步轮询，当前已经完全执行完毕并缓存）。
3. **本地缓存与渲染建议**：提供具体的渲染方式（如使用标准的 Markdown 语法 `![图片](file://<path>)` 来展示本地绝对路径的文件），并明确要求 Agent 优先展示已有结果，避免不必要的重复生成或无休止的状态查询。
4. **可操作的排查建议**：如果执行失败，会详细指导 Agent 如何检查环境变量（`VOLCENGINE_API_KEY`）和火山引擎账户的服务开通状态，方便 Agent 自我纠错和重试。

#### 成功响应的 JSON 载荷示例：
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

## 配置说明

要授权火山引擎的 API 请求，请配置您的火山方舟 API Key。主环境变量为 `VOLCENGINE_API_KEY`，并同时向下兼容 `ARK_API_KEY` 作为备用参数：

在目标 Profile 根目录的 `.env` 文件（即 `[HERMES_HOME]/.env`）中写入：
```bash
VOLCENGINE_API_KEY=your-volcengine-api-key-here
```

---

## 使用方法

### 1. LLM 大语言模型
注册完成后，您可以直接在 `config.yaml` 的模型配置部分指定 `volcengine` 的端点 and 模型：
```yaml
model:
  default: ark-code-latest
  provider: custom
  base_url: https://ark.cn-beijing.volces.com/api/plan/v3
  api_key: 您的API_KEY
```

### 2. 图像生成
在终端或与 Agent 对话时触发图像生成，Hermes 将调用 `volcengine` 后端处理：
```bash
hermes image "日落时分充满科幻霓虹色彩的未来都市" --aspect landscape
```
这将使用 `doubao-seedream-5.0-lite` 产生一张宽高为 `2560x1440` 的高分辨率图片。

若要选用更高画质的 pro 版本模型，可在配置中覆写：
```yaml
image_gen:
  provider: volcengine
  model: doubao-seedream-5.0-pro
```

### 3. 视频生成
使用豆包视频生成大模型生成视频：
```bash
hermes video "一只蜂鸟在盛开的花朵旁盘旋吸蜜"
```
系统将通过我们包装的 `volcengine` 视频后端进行解析和任务推送，并在标准错误流中输出实时排队与生成进度日志。
