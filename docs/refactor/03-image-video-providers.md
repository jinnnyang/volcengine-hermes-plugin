# 03. 图像与视频 Provider 重构方案

## 1. 总体原则

图像和视频保持独立 provider，不与文本模型 provider 合并。

原因：

- Hermes 对 model provider、image provider、video provider 使用不同插件接口。
- 图像/视频调用形态不是普通 chat completions。
- Agent/Coding/API endpoint 对多模态能力的支持范围可能不同。
- 独立 provider 更利于测试和错误提示。

## 2. 共享 endpoint 解析

图像和视频都应复用与 model provider 一致的 base URL 解析逻辑：

```text
VOLCENGINE_BASE_URL
  > VOLCENGINE_PLAN_MODE
  > 默认 agent mode /api/plan/v3
```

然后拼接具体接口路径。

示例：

```text
{base_url}/images/generations
{base_url}/contents/generations/tasks
```

## 3. 图像 provider

### 默认模型

```text
doubao-seedream-5.0-lite
```

### 模型列表

根据已确认决策，只保留页面明确支持的：

```python
IMAGE_MODELS = (
    "doubao-seedream-5.0-lite",
)
```

### endpoint

```http
POST {base_url}/images/generations
```

默认 base URL 下即：

```text
https://ark.cn-beijing.volces.com/api/plan/v3/images/generations
```

### 参数策略

保留现有能力：

- prompt
- aspect_ratio
- size 映射
- response_format=b64_json
- 本地缓存输出

建议保留 URL 响应兼容：如果 API 返回 URL 而非 b64，也可下载保存。

### 尺寸策略

当前尺寸可保留：

| aspect ratio | size |
|---|---|
| landscape | `2560x1440` |
| square | `2048x2048` |
| portrait | `1440x2560` |

如果官方后续要求不同尺寸，应通过配置或模型 metadata 调整。

### 错误提示

如果 endpoint 是 `/api/coding/v3` 且返回不支持，应提示：

> 当前 Coding Plan endpoint 可能不支持图像生成，请切换 Agent Plan 或普通 Ark API。

## 4. 视频 provider

### 默认模型

根据已确认决策，默认改为：

```text
doubao-seedance-1.5-pro
```

### 可选模型列表

建议：

```python
VIDEO_MODELS = (
    "doubao-seedance-1.5-pro",
    "doubao-seedance-2.0",
    "doubao-seedance-2.0-fast",
)
```

注意文档应说明：

- `doubao-seedance-1.5-pro`：Medium 及以上套餐可能支持。
- `doubao-seedance-2.0` / `2.0-fast`：可能需要 Large/Max 或普通 API 权限。
- Small 可能不支持视频。

具体可用性以火山控制台/API 返回为准。

### endpoint

创建任务：

```http
POST {base_url}/contents/generations/tasks
```

默认 base URL 下即：

```text
https://ark.cn-beijing.volces.com/api/plan/v3/contents/generations/tasks
```

轮询任务 endpoint 需根据现有代码和官方文档核对，保留当前可用逻辑。

## 5. 视频参数补齐

已查到 Seedance 创建任务接口支持的相关字段包括：

```text
model
content
callback_url
return_last_frame
service_tier
execution_expires_after
generate_audio
draft
tools
safety_identifier
priority
resolution
ratio
duration
frames
seed
camera_fixed
watermark
```

第一阶段建议传递安全子集：

| 参数 | 行为 |
|---|---|
| `resolution` | 当前代码声明但未传，应补上传递 |
| `ratio` | 继续传递 |
| `duration` | 继续传递 |
| `generate_audio` | 从现有 `audio` 参数映射 |
| `draft` | 可新增，主要面向 1.5 Pro |
| `watermark` | 可新增 |
| `camera_fixed` | 可新增 |
| `return_last_frame` | 可新增 |

谨慎处理：

| 参数 | 策略 |
|---|---|
| `seed` | 如果官方说明某模型不支持，则条件忽略或报友好错误 |
| `negative_prompt` | 暂不传，除非官方文档明确支持 |
| `priority` | 可后续支持，注意模型/套餐差异 |

## 6. 任务轮询

保留现有轮询逻辑，但测试覆盖：

- 创建任务成功。
- 创建任务失败。
- 轮询中。
- 轮询成功。
- 轮询失败。
- 轮询超时。
- 下载视频失败。

默认超时建议保持 300 秒，但允许环境变量覆盖：

```bash
VOLCENGINE_VIDEO_TIMEOUT_SECONDS=300
VOLCENGINE_VIDEO_POLL_INTERVAL_SECONDS=10
```

## 7. 用户配置

建议支持：

```bash
VOLCENGINE_IMAGE_MODEL=doubao-seedream-5.0-lite
VOLCENGINE_VIDEO_MODEL=doubao-seedance-1.5-pro
VOLCENGINE_PLAN_MODE=agent
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/plan/v3
```

如果用户设置未知模型，不直接拦截，以 API 返回为准。

## 8. 验收标准

图像：

- 默认模型是 `doubao-seedream-5.0-lite`。
- 模型列表只保留 `doubao-seedream-5.0-lite`。
- endpoint 按 mode 正确切换。
- b64_json 和 URL 响应均可处理。

视频：

- 默认模型是 `doubao-seedance-1.5-pro`。
- endpoint 按 mode 正确切换。
- payload 包含 `resolution`、`ratio`、`duration`、`generate_audio`。
- task success/fail/timeout 均有测试。
- Coding Plan 下失败时提示清晰。
