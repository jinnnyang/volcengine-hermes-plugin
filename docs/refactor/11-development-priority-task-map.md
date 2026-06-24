# 11. 开发优先级与任务包划分

本文件用于从方案讨论阶段进入开发阶段前，对任务进行优先级拆分。执行时应按优先级推进，并保持小步提交。

## 1. 优先级原则

已确认优先级：

```text
模型与套餐适配 > 测试保障 > 代码结构质量 > 安装体验
```

搜索能力是明确目标，但它依赖 Hermes Web Search Provider 机制和豆包搜索 direct API schema，因此单独拆为 P1/P2 交界的独立任务包：

- 豆包搜索作为 Hermes `web_search` backend：P1，属于核心能力。
- 专业数据集搜索：P2/P3，等 API 形态进一步确认后实现。

## 2. 阶段边界

| 优先级 | 任务包 | 目标 | 是否阻塞开发主线 |
|---|---|---|---|
| P0 | 开发基线与测试骨架 | 建立可验证开发状态 | 是 |
| P1 | Endpoint 与模型选择 | 支持 Agent/Coding/API，动态模型与手动 model id | 是 |
| P1 | 图像/视频关键适配 | 保持多模态插件可用并符合已确认模型 | 是 |
| P1 | Volcengine Web Search Provider | 豆包搜索接入 Hermes `web_search` backend | 是 |
| P2 | 测试保障扩展 | 让核心能力可 mock 验证 | 是 |
| P2 | 代码结构质量 | 抽取共享配置、错误处理、重复逻辑 | 否，但应在功能稳定后做 |
| P3 | 安装体验 | install.sh、dry-run、backup、setup 指引 | 否，但发布前必须完成 |
| P3 | 文档发布 | README、错误码、迁移指南 | 发布前必须完成 |
| P4 | 专业数据集搜索 | 垂直搜索/私域检索工具 | 不阻塞第一版 |

## 3. P0：开发基线与测试骨架

### 目标

进入开发前先建立最小可运行的验证基础，避免后续只靠手工检查。

### 任务

1. 检查当前分支不是 `main`。
2. 确认当前方案文档已提交。
3. 添加测试依赖或测试运行说明。
4. 建立 `tests/` 目录。
5. 写第一个 resolver 测试文件。
6. 确认无真实 API key 参与测试。

### 候选文件

```text
tests/
tests/test_volcengine_config.py
pyproject.toml 或 requirements-dev.txt
```

### 验收

```bash
uv run pytest -q
```

如果项目暂未配置 `uv run pytest`，则先确认可用命令并写入文档。

## 4. P1-A：Endpoint 与套餐适配

### 目标

统一支持：

- Agent Plan：默认 `/api/plan/v3`
- Coding Plan：允许 `/api/coding/v3`
- 普通 Ark API：`/api/v3`
- 用户自定义完整 endpoint

### 任务

1. 写 endpoint resolver 的失败测试。
2. 实现 `VOLCENGINE_BASE_URL` 优先。
3. 实现 `VOLCENGINE_PLAN_MODE=agent|coding|api`。
4. 将 model provider 接入 resolver。
5. 将 image provider 接入 resolver。
6. 将 video provider 接入 resolver。
7. 文档注明：Coding Plan 代码层面允许，但推荐仅用于文本/编码工具；多模态优先 Agent Plan 或普通 Ark API。

### 验收

- 默认 base URL 是 `/api/plan/v3`。
- `VOLCENGINE_PLAN_MODE=coding` 得到 `/api/coding/v3`。
- `VOLCENGINE_PLAN_MODE=api` 得到 `/api/v3`。
- `VOLCENGINE_BASE_URL` 覆盖所有 mode。

## 5. P1-B：动态模型列表与用户选择

### 目标

让 Hermes 用户可以：

- 动态看到当前 API key 可用模型。
- 在动态拉取失败时仍有 fallback 模型。
- 手动输入 model id。

### 任务

1. 写 `/models` mock 成功测试。
2. 写 `/models` 失败 fallback 测试。
3. 保留 `ark-code-latest`。
4. 更新 fallback model list。
5. 实现动态模型拉取。
6. 实现超时和错误处理。
7. 若 Hermes provider setup 支持选择项，则接入模型选择；否则文档明确手动输入 model id。

### 验收

- 有 API key 且 `/models` 成功时，返回远端模型列表。
- `/models` 失败时，仍返回 fallback 模型。
- fallback 中包含 `ark-code-latest`。
- 用户可以通过 config 指定任意 model id。

## 6. P1-C：图像与视频关键适配

### 目标

保持图像/视频插件独立，并与已确认模型一致。

### 图像任务

1. 默认模型改为/保持 `doubao-seedream-5.0-lite`。
2. 图像模型列表只保留 `doubao-seedream-5.0-lite`。
3. 确认 payload 与当前火山接口一致。
4. 添加 mock 测试。

### 视频任务

1. 默认模型改为 `doubao-seedance-1.5-pro`。
2. 补齐 `resolution`、`generate_audio` 等参数。
3. 对 `seed` 等模型差异参数做条件处理。
4. 添加任务提交和轮询 mock 测试。

### 验收

- 图像默认模型符合要求。
- 视频默认模型符合要求。
- Coding Plan 下多模态失败时错误提示清晰。

## 7. P1-D：Volcengine Web Search Provider

### 目标

实现 `plugins/web/volcengine`，让豆包搜索成为 Hermes 标准 `web_search` backend。

### 任务

1. 创建 plugin manifest。
2. 实现 provider 注册。
3. 实现 API key resolver。
4. 实现 `is_available()`。
5. 实现 `search(query, limit)`。
6. 请求豆包搜索 direct API。
7. 映射 `WebResults` 到 Hermes `data.web`。
8. 实现错误码映射。
9. 实现 `get_setup_schema()`。
10. 添加 mock 测试。

### 验收

配置后模型仍调用：

```text
web_search(query="...", limit=5)
```

底层 backend 使用：

```text
Volcengine Doubao Search
```

## 8. P2：测试保障扩展

### 目标

覆盖核心行为，不依赖真实 API key。

### 测试包

```text
tests/test_volcengine_config.py
tests/test_model_provider_dynamic_models.py
tests/test_image_provider_payload.py
tests/test_video_provider_payload.py
tests/test_web_search_provider.py
tests/test_install_script.py
```

### 验收

```bash
uv run pytest -q
```

或仓库确认的等价测试命令通过。

## 9. P2：代码结构质量

### 目标

在功能测试稳定后抽取重复逻辑。

### 任务

1. 抽取 endpoint resolver。
2. 抽取 API key resolver。
3. 抽取 HTTP error formatter。
4. 抽取模型列表工具。
5. 保持插件安装后的 import 路径稳定。

### 验收

- 重构前后测试结果一致。
- 不改变公开配置接口。
- 不破坏现有 alias。

## 10. P3：安装体验

### 目标

让外部用户可以安全安装和配置。

### 任务

1. `install.sh --mode agent|coding|api`。
2. `install.sh --base-url URL`。
3. `install.sh --enable-web-search`。
4. `install.sh --set-default-web-search`。
5. `install.sh --dry-run`。
6. 修改 config 前自动备份。
7. secrets 写入 `.env` 或提示用户设置，不写入 `config.yaml`。
8. 输出后续命令和验证方式。

### 验收

- dry-run 不修改任何文件。
- 实际安装会备份旧配置。
- 可以配置 web_search backend。

## 11. P3：README 与发布文档

### 任务

1. 更新英文 README。
2. 更新中文 README。
3. 加 endpoint mode 表。
4. 加动态模型说明。
5. 加手动 model id 示例。
6. 加图像/视频模型说明。
7. 加 web_search backend 使用说明。
8. 加常见错误码。
9. 加卸载方式。

### 验收

新用户只看 README 即可完成：

1. 安装插件。
2. 选择 endpoint mode。
3. 选择/输入模型。
4. 启用 web search backend。

## 12. P4：专业数据集搜索

### 定位

不阻塞第一版。等 API schema 明确后决定：

- 如果返回形态类似通用网页搜索，则可扩展 web provider。
- 如果是私域/垂直检索，则做普通 Hermes tool。

### 候选工具名

```text
volcengine_dataset_search
volcengine_harness_search
```

## 13. 建议提交顺序

1. `docs: add volcengine hermes refactor plan`
2. `test: add volcengine config resolver tests`
3. `feat: support volcengine endpoint modes`
4. `test: cover dynamic model discovery`
5. `feat: add dynamic volcengine model discovery`
6. `feat: align volcengine image and video defaults`
7. `feat: add volcengine web search provider`
8. `test: cover installer and provider setup flows`
9. `refactor: extract shared volcengine configuration helpers`
10. `docs: update user-facing volcengine plugin setup guides`
