# 10. 实施检查清单

本文件用于后续真正开始编码时逐项勾选。当前不执行实现。

## 全局检查

- [ ] 当前分支不是 `main`。
- [ ] `git status --short` 已确认没有意外修改。
- [ ] 每个阶段先写测试或至少写 mock 验证。
- [ ] 不提交任何 API key/token/secrets。
- [ ] 不删除历史 alias。
- [ ] 不强制用户迁移环境变量。

## Phase 1：endpoint 兼容

- [ ] 添加或整理 `resolve_volcengine_base_url()`。
- [ ] 添加 `VOLCENGINE_PLAN_MODE` 解析。
- [ ] 添加 `VOLCENGINE_BASE_URL` 覆盖。
- [ ] model provider 使用 resolver。
- [ ] image provider 使用 resolver。
- [ ] video provider 使用 resolver。
- [ ] 添加 base URL 单元测试。
- [ ] 手动检查默认仍是 `/api/plan/v3`。

## Phase 2：动态模型列表

- [ ] fallback list 包含 `ark-code-latest`。
- [ ] fallback list 更新到当前讨论确认的模型。
- [ ] 实现 `/models` 请求。
- [ ] 实现请求失败 fallback。
- [ ] 实现可选缓存。
- [ ] README 说明用户可以手动输入 model id。
- [ ] 添加 `/models` mock 测试。

## Phase 3：图像/视频

- [ ] 图像默认模型为 `doubao-seedream-5.0-lite`。
- [ ] 图像模型列表只保留 `doubao-seedream-5.0-lite`。
- [ ] 视频默认模型为 `doubao-seedance-1.5-pro`。
- [ ] 视频 payload 传递 `resolution`。
- [ ] 视频 payload 传递 `generate_audio`。
- [ ] 视频 payload 条件传递 `draft/watermark/camera_fixed/return_last_frame`。
- [ ] Seedance 2.0 下谨慎处理 `seed`。
- [ ] Coding Plan 多模态错误提示清晰。
- [ ] 添加 image/video 测试。

## Phase 4：Web Search Provider

- [ ] 新建 `plugins/web/volcengine/plugin.yaml`。
- [ ] 新建 `plugins/web/volcengine/__init__.py`。
- [ ] 新建 `plugins/web/volcengine/provider.py`。
- [ ] provider name 为 `volcengine`。
- [ ] display name 为 `Volcengine Doubao Search`。
- [ ] 实现 `is_available()`。
- [ ] 实现 API key 优先级。
- [ ] 实现 `search(query, limit)`。
- [ ] 请求 `POST https://open.feedcoopapi.com/search_api/web_search`。
- [ ] 请求头包含 `Authorization: Bearer <api-key>`。
- [ ] 请求头包含 `X-Traffic-Tag: skill_web_search_common`。
- [ ] body 包含 `Query/SearchType/Count/NeedSummary`。
- [ ] 响应映射为 Hermes `data.web`。
- [ ] 实现 API 错误映射。
- [ ] 实现 `get_setup_schema()`。
- [ ] 添加 mock 测试。

## Phase 5：安装脚本

- [ ] `--mode agent|coding|api`。
- [ ] `--base-url URL`。
- [ ] `--profile PATH`。
- [ ] `--enable-model`。
- [ ] `--enable-image`。
- [ ] `--enable-video`。
- [ ] `--enable-web-search`。
- [ ] `--set-default-web-search`。
- [ ] `--no-config`。
- [ ] `--dry-run`。
- [ ] 修改前备份。
- [ ] config 写入去重。
- [ ] secrets 不写入 `config.yaml`。
- [ ] 添加临时 profile 测试。

## Phase 6：测试

- [ ] 添加 pytest 配置或 pyproject。
- [ ] 添加 resolver 测试。
- [ ] 添加 model provider 测试。
- [ ] 添加 image provider 测试。
- [ ] 添加 video provider 测试。
- [ ] 添加 web search provider 测试。
- [ ] 添加 install.sh 测试。
- [ ] 可选添加 GitHub Actions。

## Phase 7：文档

- [ ] 更新 `README.md`。
- [ ] 更新 `README_zh-CN.md`。
- [ ] 加 endpoint mode 表格。
- [ ] 加动态模型说明。
- [ ] 加手动 model id 说明。
- [ ] 加图像/视频模型说明。
- [ ] 加 web_search backend 说明。
- [ ] 加错误码说明。
- [ ] 加卸载说明。

## 发布前检查

```bash
git status --short
uv run pytest
hermes plugins list
hermes doctor
```

真实 API 测试仅在用户明确授权并提供测试 key 时执行。
