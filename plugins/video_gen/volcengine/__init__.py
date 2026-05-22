"""Volcengine Doubao Seedance video generation backend."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional

import httpx

from agent.video_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    VideoGenProvider,
    error_response,
    success_response,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/contents/generations/tasks"

_MODELS: Dict[str, Dict[str, Any]] = {
    "doubao-seedance-2.0": {
        "display": "Doubao Seedance 2.0",
        "speed": "~2-3m",
        "strengths": "2.0 视频生成模型，画面流畅度高",
        "price": "paid",
    },
}

DEFAULT_MODEL = "doubao-seedance-2.0"

_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_POLL_INTERVAL_SECONDS = 10


def _get_api_key() -> str | None:
    return os.environ.get("VOLCENGINE_API_KEY") or os.environ.get("ARK_API_KEY")


class VolcengineVideoGenProvider(VideoGenProvider):
    """Volcengine Doubao Seedance video generation backend."""

    @property
    def name(self) -> str:
        return "volcengine"

    @property
    def display_name(self) -> str:
        return "火山引擎 (Seedance)"

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
            "name": "火山引擎 (Seedance)",
            "badge": "paid",
            "tag": "Doubao Seedance — 字节跳动官方视频生成",
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
        *,
        model: Optional[str] = None,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        duration: Optional[int] = None,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        resolution: str = "720p",
        negative_prompt: Optional[str] = None,
        audio: Optional[bool] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._generate_async(
                    prompt=prompt,
                    model=model,
                    image_url=image_url,
                    reference_image_urls=reference_image_urls,
                    duration=duration,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                    negative_prompt=negative_prompt,
                    audio=audio,
                    seed=seed,
                ))
            finally:
                loop.close()
        except Exception as exc:
            logger.warning("Volcengine video gen unexpected failure: %s", exc, exc_info=True)
            return error_response(
                error=f"火山引擎视频生成失败: {exc}",
                error_type="api_error",
                provider="volcengine",
                model=model or DEFAULT_MODEL,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
            )

    async def _generate_async(
        self,
        *,
        prompt: str,
        model: Optional[str],
        image_url: Optional[str],
        reference_image_urls: Optional[List[str]],
        duration: Optional[int],
        aspect_ratio: str,
        resolution: str,
        negative_prompt: Optional[str],
        audio: Optional[bool],
        seed: Optional[int],
    ) -> Dict[str, Any]:
        api_key = _get_api_key()
        if not api_key:
            return error_response(
                error="VOLCENGINE_API_KEY or ARK_API_KEY not set. Configure it via environment variable or hermes tools.",
                error_type="auth_required",
                provider="volcengine",
                prompt=prompt,
            )

        prompt = (prompt or "").strip()
        model = model or DEFAULT_MODEL
        image_url_norm = (image_url or "").strip() or None
        aspect = (aspect_ratio or DEFAULT_ASPECT_RATIO).strip()

        # Print detailed execution info to stderr to resolve black-box issues
        print(f"[volcengine] Calling Video Generation: model={model}, aspect_ratio={aspect}", file=sys.stderr)
        print(f"[volcengine] Prompt: \"{prompt}\"", file=sys.stderr)

        if not prompt:
            return error_response(
                error="Prompt is required",
                error_type="invalid_argument",
                provider="volcengine",
                aspect_ratio=aspect,
            )

        # Build content list
        content = [{"type": "text", "text": prompt}]
        if image_url_norm:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": image_url_norm
                }
            })
        elif reference_image_urls and len(reference_image_urls) > 0:
            for ref_url in reference_image_urls:
                if ref_url.strip():
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": ref_url.strip()
                        }
                    })

        # Map aspect ratios to standard Seedance parameters
        ratio_map = {
            "16:9": "16:9",
            "9:16": "9:16",
            "1:1": "1:1",
            "4:3": "4:3",
            "3:4": "3:4",
            "3:2": "3:2",
            "2:3": "2:3",
            "landscape": "16:9",
            "portrait": "9:16",
            "square": "1:1",
        }
        mapped_ratio = ratio_map.get(aspect, "adaptive")

        payload: Dict[str, Any] = {
            "model": model,
            "content": content,
            "ratio": mapped_ratio,
        }
        if duration is not None:
            payload["duration"] = duration
        if audio is not None:
            payload["generate_audio"] = audio

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            try:
                # 1. Create task
                print(f"[volcengine] Creating video generation task...", file=sys.stderr)
                resp = await client.post(BASE_URL, json=payload, headers=headers, timeout=_TIMEOUT)
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
                print(f"[volcengine] Create task failed: {error_msg}", file=sys.stderr)
                return error_response(
                    error=f"API 调用失败: {error_msg}",
                    error_type="api_error",
                    provider="volcengine",
                    model=model,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            except Exception as exc:
                print(f"[volcengine] Create task error: {exc}", file=sys.stderr)
                return error_response(
                    error=f"创建视频任务失败: {exc}",
                    error_type="api_error",
                    provider="volcengine",
                    model=model,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )

            task_id = res_data.get("id")
            if not task_id:
                print(f"[volcengine] Response missing task id: {res_data}", file=sys.stderr)
                return error_response(
                    error="火山引擎接口未返回任务 ID",
                    error_type="api_error",
                    provider="volcengine",
                    model=model,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )

            print(f"[volcengine] Video task created. Task ID: {task_id}. Polling for status...", file=sys.stderr)

            # 2. Poll task status
            elapsed = 0.0
            poll_interval = DEFAULT_POLL_INTERVAL_SECONDS
            timeout = DEFAULT_TIMEOUT_SECONDS
            video_url = None

            while elapsed < timeout:
                try:
                    status_url = f"{BASE_URL}/{task_id}"
                    status_resp = await client.get(status_url, headers=headers, timeout=_TIMEOUT)
                    status_resp.raise_for_status()
                    status_data = status_resp.json()
                except Exception as exc:
                    print(f"[volcengine] Polling error: {exc}. Retrying...", file=sys.stderr)
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval
                    continue

                status = (status_data.get("status") or "").lower()
                print(f"[volcengine] Task status: {status}", file=sys.stderr)

                if status in ("succeeded", "success"):
                    result = status_data.get("result") or {}
                    video_url = result.get("video_url")
                    break
                elif status in ("failed", "error", "cancelled", "expired"):
                    err_obj = status_data.get("error") or {}
                    err_msg = err_obj.get("message") or f"Task ended with status: {status}"
                    print(f"[volcengine] Video generation failed: {err_msg}", file=sys.stderr)
                    return error_response(
                        error=f"视频生成失败: {err_msg}",
                        error_type=f"volcengine_{status}",
                        provider="volcengine",
                        model=model,
                        prompt=prompt,
                        aspect_ratio=aspect,
                    )

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            if not video_url:
                if elapsed >= timeout:
                    print(f"[volcengine] Task timed out after {timeout} seconds.", file=sys.stderr)
                    return error_response(
                        error=f"等待视频生成超时 ({timeout}秒)",
                        error_type="timeout",
                        provider="volcengine",
                        model=model,
                        prompt=prompt,
                        aspect_ratio=aspect,
                    )
                return error_response(
                    error="未能在成功的响应中找到视频 URL",
                    error_type="empty_response",
                    provider="volcengine",
                    model=model,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )

            print(f"[volcengine] Video generation successful. Video URL: {video_url}", file=sys.stderr)
            return success_response(
                video=video_url,
                model=model,
                prompt=prompt,
                modality="image" if image_url_norm else "text",
                aspect_ratio=aspect,
                duration=duration or 0,
                provider="volcengine",
                extra={"task_id": task_id},
            )


def register(ctx) -> None:
    ctx.register_video_gen_provider(VolcengineVideoGenProvider())
    print("[volcengine] Video Gen provider registered successfully.", file=sys.stderr)
