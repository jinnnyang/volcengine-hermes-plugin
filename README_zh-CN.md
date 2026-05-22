# 火山引擎豆包插件与 Hermes Agent 集成 (`volces-engine`)

本集成插件为 Hermes Agent 提供了对火山引擎（Volcengine）模型的原生支持，包括豆包大语言模型（Doubao LLM）、豆包图像生成大模型（Doubao Seedream 5.0）和豆包视频生成大模型（Doubao Seedance 2.0）。

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

Hermes Agent 原生支持一系列标准模型供应商（如 OpenAI、FAL 等），但缺乏对火山引擎（火山方舟）的开箱即用支持。火山引擎提供了行业领先的基础模型：
- **豆包大语言模型**（提供 Agent Plan / Coding Plan）
- **豆包 Seedream 5.0**（高质量图像生成）
- **豆包 Seedance 2.0**（视频生成）

为了在 Hermes Agent 智能体中无缝使用这些模型，我们基于 Hermes Agent 的插件系统开发了 `volces-engine` 插件包，将这些模型作为一等公民（First-class providers）注册到 Agent 的配置体系中。

---

## 设计思路与架构

Hermes Agent 发现和加载不同类型的扩展采用了两种独立机制：
1. **模型供应商 (Model Providers)**：由系统级 `providers/` 目录扫描器自动加载并发现。
2. **生成式后端 (Image/Video Gen)**：由 Hermes 核心的 `PluginManager` 动态发现并装载。

因此，我们的集成方案在 `volces-engine` 品牌名下被拆分为三个独立的插件：

### 1. 模型供应商插件 (Model Provider)
注册一个名为 `volces-engine` 的自定义 LLM provider profile，指向火山引擎企业级端点（`https://ark.cn-beijing.volces.com/api/plan/v3`），并绑定 `doubao` 别名以及具体的 Coding/Agent 方案。

### 2. 图像生成插件 (`Seedream 5.0`)
这是一款高度定制的图像生成后端，重点解决了以下技术细节：
- **企业级端点适配**：使用企业方案专用的 `/api/plan/v3/images/generations` API 路径。
- **高像素限制要求**：豆包 Seedream 5.0 要求生成分辨率 $\ge 3,686,400$ 像素（即 3.68MP）。插件将标准比例映射为高分辨率：
  - `landscape` (横屏) $\rightarrow$ `2560x1440`
  - `square` (方形) $\rightarrow$ `2048x2048`
  - `portrait` (竖屏) $\rightarrow$ `1440x2560`
- **超长请求超时**：由于高分辨率图像生成较慢，使用 `httpx.Timeout` 分离了连接超时（10s）与读取超时（120s），防止由于网络请求被提前切断而导致生成失败。
- **模型切换能力**：完全支持 `model` 覆写参数（默认使用 `doubao-seedream-5.0-lite`，可通过参数一键切换至 `doubao-seedream-5.0-pro`）。
- **稳健的分层异常处理**：捕获 HTTP 状态错误，提取火山 API 返回的具体错误消息，并输出 warning 日志及优雅降级提示。

### 3. 视频生成插件 (`Seedance 2.0`)
对 Hermes Agent 内置的 `VolcengineVideoGenProvider` 进行轻量包裹，并在 `volces-engine` 命名空间下重新导出，确保品牌与调用名称的完全统一。

---

## 目录结构

```
.
├── install.sh                  # 交互式自动安装脚本
├── README.md                   # 英文文档
├── README_zh-CN.md             # 中文文档
└── plugins/
    ├── model-providers/
    │   └── volces-engine/
    │       ├── plugin.yaml     # LLM 供应商元数据
    │       └── __init__.py     # 模块级注册入口
    ├── image_gen/
    │   └── volces-engine/
    │       ├── plugin.yaml     # 图像生成后端元数据
    │       └── __init__.py     # Seedream 逻辑及注册实现
    └── video_gen/
        └── volces-engine/
            ├── plugin.yaml     # 视频生成后端元数据
            └── __init__.py     # Seedance 轻量包装与注册实现
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
4. 使用 Python 脚本安全地修改该 Profile 下的 `config.yaml` 文件：自动向 `plugins.enabled` 追加启用项，并将 `image_gen` 和 `video_gen` 的 provider 字段切换为 `volces-engine`，不破坏用户原有的其它配置。

### 手动安装

如果您的环境无法运行自动脚本，请按照以下步骤手动部署：

1. **拷贝插件文件夹**至您的 Hermes Profile 对应的 `plugins/` 目录：
   ```bash
   cp -r plugins/model-providers/volces-engine [HERMES_HOME]/plugins/model-providers/
   cp -r plugins/image_gen/volces-engine [HERMES_HOME]/plugins/image_gen/
   cp -r plugins/video_gen/volces-engine [HERMES_HOME]/plugins/video_gen/
   ```
2. **在配置文件中启用插件**：打开 `[HERMES_HOME]/config.yaml`，并在 `plugins.enabled` 列表下追加：
   ```yaml
   plugins:
     enabled:
       - image_gen/volces-engine
       - video_gen/volces-engine
   ```
3. **配置默认生成后端**：在 `[HERMES_HOME]/config.yaml` 中，更新对应的 provider 配置：
   ```yaml
   image_gen:
     provider: volces-engine
     model: doubao-seedream-5.0-lite

   video_gen:
     provider: volces-engine
     model: doubao-seedance-2.0
   ```

---

## 配置说明

要授权火山引擎的 API 请求，请在目标 Profile 根目录的 `.env` 文件（即 `[HERMES_HOME]/.env`）中写入您的火山方舟 API Key：

```bash
ARK_API_KEY=your-volcengine-ark-api-key-here
```
*(插件也会同时检查并支持名为 `VOLCENGINE_API_KEY` 的环境变量)*。

---

## 使用方法

### 1. LLM 大语言模型
注册完成后，您可以直接在 `config.yaml` 的模型配置部分指定 `volces-engine` 的端点和模型：
```yaml
model:
  default: ark-code-latest
  provider: custom
  base_url: https://ark.cn-beijing.volces.com/api/plan/v3
  api_key: 您的API_KEY
```

### 2. 图像生成
在终端或与 Agent 对话时触发图像生成，Hermes 将调用 `volces-engine` 后端处理：
```bash
hermes image "日落时分充满科幻霓虹色彩的未来都市" --aspect landscape
```
这将使用 `doubao-seedream-5.0-lite` 产生一张宽高为 `2560x1440` 的高分辨率图片。

若要选用更高画质的 pro 版本模型，可在配置中覆写：
```yaml
image_gen:
  provider: volces-engine
  model: doubao-seedream-5.0-pro
```

### 3. 视频生成
使用豆包视频生成大模型生成视频：
```bash
hermes video "一只蜂鸟在盛开的花朵旁盘旋吸蜜"
```
系统将通过我们包装的 `volces-engine` 视频后端进行解析和任务推送。
