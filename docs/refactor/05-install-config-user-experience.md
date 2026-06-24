# 05. 安装、配置与用户体验方案

## 1. 目标

本仓库希望给其他 Hermes 用户使用，所以安装体验要做到：

- 非破坏式。
- 可 dry-run。
- 自动备份用户配置。
- 支持 Agent/Coding/API endpoint 选择。
- 支持启用图像、视频、web search provider。
- 支持用户手动输入 endpoint 和 model id。
- 支持通过 Hermes setup/tools 继续配置。

## 2. 配置优先级

总体原则：

```text
环境变量优先，安装脚本写入作为默认配置，用户显式 Hermes config 次之按 Hermes 自身解析规则处理。
```

本仓库内部 endpoint 解析建议：

```text
VOLCENGINE_BASE_URL
  > VOLCENGINE_PLAN_MODE
  > 默认 agent mode
```

model id：

```text
显式 Hermes model 配置 / 用户输入
  > VOLCENGINE_MODEL / VOLCENGINE_IMAGE_MODEL / VOLCENGINE_VIDEO_MODEL
  > provider 默认模型
```

## 3. 推荐环境变量

### 通用

```bash
VOLCENGINE_API_KEY=...
ARK_API_KEY=...
VOLCENGINE_PLAN_MODE=agent|coding|api
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/plan/v3
```

### 模型

```bash
VOLCENGINE_MODEL=ark-code-latest
VOLCENGINE_MODELS_CACHE_TTL_SECONDS=86400
VOLCENGINE_DISABLE_MODEL_CACHE=0
```

### 图像 / 视频

```bash
VOLCENGINE_IMAGE_MODEL=doubao-seedream-5.0-lite
VOLCENGINE_VIDEO_MODEL=doubao-seedance-1.5-pro
VOLCENGINE_VIDEO_TIMEOUT_SECONDS=300
VOLCENGINE_VIDEO_POLL_INTERVAL_SECONDS=10
```

### 搜索

```bash
VOLCENGINE_SEARCH_API_KEY=...
WEB_SEARCH_API_KEY=...
ASK_ECHO_SEARCH_INFINITY_API_KEY=...
VOLCENGINE_SEARCH_AUTH_LEVEL=0|1
VOLCENGINE_SEARCH_TIME_RANGE=OneDay|OneWeek|OneMonth|OneYear
VOLCENGINE_SEARCH_QUERY_REWRITE=true|false
```

## 4. install.sh 设计

建议支持交互和非交互两种模式。

### 交互模式

```bash
./install.sh
```

交互问题：

1. 选择 Hermes profile。
2. 选择 endpoint mode：
   - Agent Plan `/api/plan/v3`
   - Coding Plan `/api/coding/v3`
   - Ark API `/api/v3`
   - Custom base URL
3. 是否安装 model provider。
4. 是否安装 image provider。
5. 是否安装 video provider。
6. 是否安装 web search provider。
7. 是否设置 Volcengine 为默认 `web.search_backend`。
8. 是否写入默认 model / image model / video model。
9. 是否 dry-run。

### 非交互参数

```bash
./install.sh \
  --profile ~/.hermes/profiles/devops \
  --mode agent \
  --enable-model \
  --enable-image \
  --enable-video \
  --enable-web-search \
  --set-default-web-search \
  --dry-run
```

建议参数：

| 参数 | 说明 |
|---|---|
| `--mode agent|coding|api` | endpoint 模式 |
| `--base-url URL` | 自定义 base URL |
| `--profile PATH` | Hermes profile 路径 |
| `--enable-model` | 安装模型 provider |
| `--enable-image` | 安装图像 provider |
| `--enable-video` | 安装视频 provider |
| `--enable-web-search` | 安装 web search provider |
| `--set-default-web-search` | 设置 `web.search_backend=volcengine` |
| `--no-config` | 只复制插件，不改配置 |
| `--dry-run` | 只打印计划，不写文件 |
| `--backup` | 修改配置前备份，默认开启 |

## 5. 配置修改策略

修改前备份：

```text
config.yaml.bak.YYYYMMDD-HHMMSS
.env.bak.YYYYMMDD-HHMMSS
```

写入 config 时原则：

- 不删除用户已有无关配置。
- 不覆盖用户显式设置，除非用户确认。
- 新增 plugins.enabled 条目时去重。
- Secret 写入 `.env` 或提示用户手动 export，不写进 `config.yaml`。

## 6. Hermes 命令集成

安装完成后可提示用户：

```bash
hermes plugins list
hermes tools
hermes model
hermes doctor
```

如果启用搜索：

```bash
hermes config set web.search_backend volcengine
hermes tools enable web
```

如果选择模型：

```bash
hermes model
```

## 7. Search setup 体验

Web provider 实现 `get_setup_schema()` 后，Hermes tools/setup 应能展示：

```text
Volcengine Doubao Search
```

并提示：

```text
VOLCENGINE_SEARCH_API_KEY
```

链接：

```text
https://console.volcengine.com/search-infinity/api-key
```

Agent Plan 用户文档补充：

1. 先进入 Agent Plan 使用配置。
2. 配置 Harness。
3. 开通联网搜索/豆包搜索。
4. 到 Ark API Key 页复制 Key。

## 8. README 面向公开用户

README 需要补充：

- 这个仓库支持哪些 Hermes Agent 版本。
- 如何安装到指定 profile。
- 如何选择 Agent/Coding/API 模式。
- 如何动态选择模型。
- 如何启用 Volcengine web search backend。
- 常见错误码。
- 如何卸载。

## 9. 卸载策略

建议提供：

```bash
./install.sh --uninstall
```

行为：

- 删除复制到 Hermes profile 的插件目录。
- 从 `plugins.enabled` 移除本插件。
- 可选恢复备份。
- 不删除用户 API key，除非用户显式确认。

## 10. 验收标准

- dry-run 不写文件。
- 默认备份 config。
- 可安装到非默认 profile。
- `--mode coding` 写入 `/api/coding/v3`。
- `--mode api` 写入 `/api/v3`。
- `--base-url` 优先。
- 可启用 `web.search_backend=volcengine`。
- 重复运行不会产生重复配置。
