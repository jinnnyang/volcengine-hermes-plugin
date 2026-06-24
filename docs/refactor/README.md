# Volcengine Hermes Plugin 重构方案索引

本目录记录 `volcengine-hermes-plugin` 面向新版 Hermes Agent 的重构方案。当前阶段只撰写和收敛方案，不直接进入代码实现。

## 背景

目标是把本仓库重构为面向 Hermes Agent 的火山方舟插件集合，兼容：

- Agent Plan：默认 `/api/plan/v3`
- Coding Plan：切换到 `/api/coding/v3`
- 普通火山 Ark API：切换到 `/api/v3`
- 图像生成、视频生成独立 provider
- Volcengine / 豆包搜索作为 Hermes `web_search` backend，达到 Tavily-like 使用体验

同时重点补齐：

- 自动拉取模型列表
- 用户可选择模型
- 用户可手动输入 model id 和 endpoint
- 测试与验证
- 面向其他用户发布的安装与文档体验

## 已确认决策

1. 项目定位可以重新定义，但必须保持历史兼容。
2. 文本 provider 默认使用 Agent Plan `/api/plan/v3`。
3. 通过切换 base URL 支持 Coding Plan `/api/coding/v3` 和普通 Ark API `/api/v3`。
4. 图像、视频、模型 provider 保持独立。
5. 模型列表需要动态获取，同时保留 fallback list。
6. 保留 `ark-code-latest`。
7. 视频默认模型改为 `doubao-seedance-1.5-pro`。
8. 图像模型只保留页面明确支持的 `doubao-seedream-5.0-lite`。
9. 允许用户手动输入 model id 和 endpoint。
10. 安装和配置同时支持交互选择与环境变量，环境变量优先。
11. 代码层面允许 `/api/coding/v3` 用于多模态，但文档应明确：Coding Plan 推荐用于文本/编码工具，多模态优先使用 Agent Plan 或普通 Ark API。
12. 重构不得直接在 `main` 分支进行，当前方案和后续实现应在独立分支完成。

## 文档结构

| 文档 | 内容 |
|---|---|
| [`00-context-and-decisions.md`](00-context-and-decisions.md) | 背景、范围、已确认决策、非目标 |
| [`01-hermes-plugin-architecture.md`](01-hermes-plugin-architecture.md) | 最新 Hermes 插件体系与本仓库目标结构 |
| [`02-model-provider-dynamic-models.md`](02-model-provider-dynamic-models.md) | 文本模型 provider、动态模型拉取、用户选择模型 |
| [`03-image-video-providers.md`](03-image-video-providers.md) | 图像/视频 provider 独立重构方案 |
| [`04-web-search-provider.md`](04-web-search-provider.md) | Volcengine Web Search Provider / 豆包搜索 direct API schema |
| [`05-install-config-user-experience.md`](05-install-config-user-experience.md) | 安装脚本、配置、Hermes setup/tools 体验 |
| [`06-testing-and-acceptance.md`](06-testing-and-acceptance.md) | 测试设计、验收标准、mock 与 smoke test |
| [`07-implementation-phases.md`](07-implementation-phases.md) | 分阶段实施计划和提交边界 |
| [`08-detailed-phase-breakdown.md`](08-detailed-phase-breakdown.md) | 每个阶段的细任务、伪代码、测试点 |
| [`09-interface-pseudocode-and-config-examples.md`](09-interface-pseudocode-and-config-examples.md) | 接口伪代码与 Hermes 配置示例 |
| [`10-implementation-checklists.md`](10-implementation-checklists.md) | 后续编码实施检查清单 |
| [`11-development-priority-task-map.md`](11-development-priority-task-map.md) | 开发优先级与任务包划分 |

## 官方 Hermes 文档参考

建议阅读顺序：

1. <https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins>
2. <https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin>
3. <https://hermes-agent.nousresearch.com/docs/user-guide/features/built-in-plugins>
4. <https://hermes-agent.nousresearch.com/docs/developer-guide/model-provider-plugin>
5. <https://hermes-agent.nousresearch.com/docs/developer-guide/web-search-provider-plugin>

## 当前状态

- 当前阶段：方案撰写与需求收敛。
- 当前分支要求：不得在 `main` 上直接重构。
- 后续实现前仍需确认：部分火山接口在不同套餐下的实际支持范围、动态模型列表接口在 Agent/Coding Plan 下的真实返回差异、专业数据集搜索 direct API schema。
