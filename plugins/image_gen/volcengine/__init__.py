"""Volcengine Doubao Seedream image generation backend."""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

import httpx

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    success_response,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations"

_MODELS: Dict[str, Dict[str, Any]] = {
    "doubao-seedream-5.0-lite": {
        "display": "Doubao Seedream 5.0 Lite",
        "speed": "~10s",
        "strengths": "5.0大模型，生成速度较快",
        "price": "paid",
    },
    "doubao-seedream-5.0-pro": {
        "display": "Doubao Seedream 5.0 Pro",
        "speed": "~25s",
        "strengths": "5.0大模型，高质量画质",
        "price": "paid",
    },
    "doubao-seedream-4.0": {
        "display": "Doubao Seedream 4.0",
        "speed": "~8s",
        "strengths": "4.0版模型，稳定基础版本",
        "price": "paid",
    },
}

DEFAULT_MODEL = "doubao-seedream-5.0-lite"

# Seedream 5.0 requires >= 3.68 million pixels (e.g. 2048x2048)
_SIZES_V5 = {
    "landscape": "2560x1440",
    "square": "2048x2048",
    "portrait": "1440x2560",
}

# Seedream 4.0 supports standard sizes
_SIZES_V4 = {
    "landscape": "1792x1024",
    "square": "1024x1024",
    "portrait": "1024x1792",
}

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


def _get_api_key() -> str | None:
    return os.environ.get("VOLCENGINE_API_KEY") or os.environ.get("ARK_API_KEY")


class VolcengineImageGenProvider(ImageGenProvider):
    """Volcengine Doubao Seedream image generation backend.

    AGENT GUIDANCE (指引):
    1. Typical Duration (生成耗时):
       - Seedream 4.0: ~8 seconds
       - Seedream 5.0 Lite: ~10 seconds
       - Seedream 5.0 Pro: ~25 seconds
       Generation runs synchronously. Stderr outputs step-by-step progress logs.
    2. How to Download/Access (下载与获取方式):
       - The plugin automatically retrieves the base64-encoded image from Volcano Engine's server,
         decodes it, and saves it locally inside the profile's cache directory.
       - The returned `image` field contains the absolute local filesystem path (e.g. `/opt/data/profiles/athena/cache/images/volc_...png`).
    3. How to Render (展示方式):
       - Always use standard markdown syntax: `![description](file:///absolute/local/path.png)`
         to render the image. The container gateway will serve it to the user.
    """

    @property
    def name(self) -> str:
        return "volcengine"

    @property
    def display_name(self) -> str:
        return "火山引擎 (Seedream)"

    def is_available(self) -> bool:
        return bool(_get_api_key())

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": mid, **meta}
            for mid, meta in _MODELS.items()
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "火山引擎 (Seedream)",
            "badge": "paid",
            "tag": "Doubao Seedream — 字节跳动官方图像生成",
            "env_vars": [
                {
                    "key": "VOLCENGINE_API_KEY",
                    "prompt": "火山引擎 API Key (ARK API Key)",
                    "url": "https://console.volcengine.com/ark/region:ark+cn-beijing/apikey",
                },
            ],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        res = self._generate_core(prompt, aspect_ratio, **kwargs)
        if res.get("success"):
            image_ref = res.get("image")
            res["agent_guidance"] = (
                "[AGENT GUIDANCE]\n"
                "- 预计耗时 (Estimated Duration): Doubao Seedream 5.0 Lite/Pro 耗时约 10s-25s，Seedream 4.0 约 8s。\n"
                "- 任务状态 (Task Status): 该任务为同步生成，已实时阻塞并成功完成。图片文件已下载保存。\n"
                f"- 本地文件 (Local File): 图片已成功缓存到本地。请使用绝对路径展示该图片，例如：![图片](file://{image_ref})。\n"
                "- 渲染/后续建议: 图像生成任务已全部成功完成，请直接展示给用户，无需重复调用生成。"
            )
        else:
            error = res.get("error", "Unknown error")
            res["agent_guidance"] = (
                "[AGENT GUIDANCE]\n"
                f"- 失败原因 (Failure Reason): {error}\n"
                "- 预计耗时 (Estimated Duration): 图像生成本需 8s-25s，但由于上述错误已终止。\n"
                "- 确认与排查 (Verification): 请检查您的 VOLCENGINE_API_KEY / ARK_API_KEY 环境变量配置是否正确，"
                "并确保选择的 model 在您的 Volcano Engine 账户中已被授权使用。\n"
                "- 后续动作 (Next Steps): 修复配置后可以重新调用生成工具。"
            )
        return res

    def _generate_core(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        model = kwargs.get("model", DEFAULT_MODEL)

        # Print detailed execution info to stderr to resolve black-box issues
        print(f"[volcengine] Calling Image Generation: model={model}, aspect_ratio={aspect}", file=sys.stderr)
        print(f"[volcengine] Prompt: \"{prompt}\"", file=sys.stderr)

        if not prompt:
            return error_response(
                error="Prompt is required",
                error_type="invalid_argument",
                provider="volcengine",
                aspect_ratio=aspect,
            )

        api_key = _get_api_key()
        if not api_key:
            return error_response(
                error="VOLCENGINE_API_KEY or ARK_API_KEY not set. Configure it via environment variable or hermes tools.",
                error_type="auth_required",
                provider="volcengine",
                aspect_ratio=aspect,
            )

        # Route resolution sizes based on the model version (Seedream 5.0 vs 4.0)
        if "5.0" in model:
            size = _SIZES_V5.get(aspect, _SIZES_V5["square"])
        else:
            size = _SIZES_V4.get(aspect, _SIZES_V4["square"])

        print(f"[volcengine] Mapped resolution size: {size}", file=sys.stderr)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "prompt": prompt,
            "response_format": "b64_json",
            "size": size,
        }

        try:
            resp = httpx.post(BASE_URL, json=payload, headers=headers, timeout=_TIMEOUT)
            resp.raise_for_status()
            res_data = resp.json()
        except httpx.HTTPStatusError as exc:
            error_msg = f"HTTP {exc.response.status_code}"
            try:
                err_body = exc.response.json()
                if "error" in err_body:
                    error_msg += f": {err_body['error'].get('message', str(err_body['error']))}"
            except Exception:
                error_msg += f": {exc.response.text[:200]}"
            print(f"[volcengine] API call failed: {error_msg}", file=sys.stderr)
            return error_response(
                error=f"API 调用失败: {error_msg}",
                error_type="api_error",
                provider="volcengine",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except httpx.RequestError as exc:
            print(f"[volcengine] Network error: {exc}", file=sys.stderr)
            return error_response(
                error=f"网络错误: {exc}",
                error_type="network_error",
                provider="volcengine",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except Exception as exc:
            print(f"[volcengine] Unexpected error: {exc}", file=sys.stderr)
            return error_response(
                error=f"图像生成失败: {exc}",
                error_type="api_error",
                provider="volcengine",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        data = res_data.get("data", [])
        if not data:
            return error_response(
                error="Volcengine returned no image data",
                error_type="empty_response",
                provider="volcengine",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        first = data[0]
        b64 = first.get("b64_json")
        url = first.get("url")

        if b64:
            try:
                saved_path = save_b64_image(b64, prefix=f"volc_{model}")
            except Exception as exc:
                return error_response(
                    error=f"Could not save image to cache: {exc}",
                    error_type="io_error",
                    provider="volcengine",
                    model=model,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            image_ref = str(saved_path)
        elif url:
            image_ref = url
        else:
            return error_response(
                error="Response contained neither b64_json nor URL",
                error_type="empty_response",
                provider="volcengine",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        print(f"[volcengine] Image generation successful. Saved to: {image_ref}", file=sys.stderr)
        return success_response(
            image=image_ref,
            model=model,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="volcengine",
            extra={"size": size},
        )


def register(ctx) -> None:
    ctx.register_image_gen_provider(VolcengineImageGenProvider())
    print("[volcengine] Image Gen provider registered successfully.", file=sys.stderr)
