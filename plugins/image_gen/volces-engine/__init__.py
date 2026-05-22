"""Volcengine Doubao Seedream image generation backend."""
from __future__ import annotations

import logging
import os
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
        "strengths": "快速生成，适合迭代",
        "price": "paid",
    },
    "doubao-seedream-5.0-pro": {
        "display": "Doubao Seedream 5.0 Pro",
        "speed": "~25s",
        "strengths": "高质量，适合最终产出",
        "price": "paid",
    },
}

DEFAULT_MODEL = "doubao-seedream-5.0-lite"

_SIZES = {
    "landscape": "2560x1440",
    "square": "2048x2048",
    "portrait": "1440x2560",
}

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


def _get_api_key() -> str | None:
    return os.environ.get("ARK_API_KEY") or os.environ.get("VOLCENGINE_API_KEY")


class VolcImageGenProvider(ImageGenProvider):
    """Volcengine Doubao Seedream image generation backend."""

    @property
    def name(self) -> str:
        return "volces-engine"

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
            "tag": "Doubao Seedream 5.0 — 字节跳动官方图像生成",
            "env_vars": [
                {
                    "key": "ARK_API_KEY",
                    "prompt": "火山引擎 ARK API Key",
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
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        model = kwargs.get("model", DEFAULT_MODEL)

        if not prompt:
            return error_response(
                error="Prompt is required",
                error_type="invalid_argument",
                provider="volces-engine",
                aspect_ratio=aspect,
            )

        api_key = _get_api_key()
        if not api_key:
            return error_response(
                error="ARK_API_KEY not set. Run `hermes tools` → Image Generation → 火山引擎 to configure.",
                error_type="auth_required",
                provider="volces-engine",
                aspect_ratio=aspect,
            )

        size = _SIZES.get(aspect)
        if size is None:
            logger.warning("Unknown aspect ratio '%s', falling back to square", aspect)
            size = _SIZES["square"]

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

        logger.info("Volcengine image gen: model=%s, prompt_len=%d, size=%s", model, len(prompt), size)

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
            logger.warning("Volcengine image gen failed: %s", error_msg)
            return error_response(
                error=f"API 调用失败: {error_msg}",
                error_type="api_error",
                provider="volces-engine",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except httpx.RequestError as exc:
            logger.warning("Volcengine image gen network error: %s", exc)
            return error_response(
                error=f"网络错误: {exc}",
                error_type="network_error",
                provider="volces-engine",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except Exception as exc:
            logger.warning("Volcengine image gen unexpected error: %s", exc, exc_info=True)
            return error_response(
                error=f"图像生成失败: {exc}",
                error_type="api_error",
                provider="volces-engine",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        data = res_data.get("data", [])
        if not data:
            return error_response(
                error="Volcengine returned no image data",
                error_type="empty_response",
                provider="volces-engine",
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
                    provider="volces-engine",
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
                provider="volces-engine",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        logger.info("Volcengine image gen success: model=%s", model)
        return success_response(
            image=image_ref,
            model=model,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="volces-engine",
            extra={"size": size},
        )


def register(ctx) -> None:
    ctx.register_image_gen_provider(VolcImageGenProvider())
