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
    """Volcengine Doubao Seedance video generation backend.

    AGENT GUIDANCE (指引):
    1. Typical Duration (生成耗时):
       - Doubao Seedance 2.0: ~2 to 3 minutes.
       - Generating video is a long-running task. The tool call will block during this period.
         Please be patient and do not interrupt.
    2. Background Task Polling (任务状态查询):
       - The API processes tasks asynchronously. The provider handles this seamlessly via an internal
         polling mechanism that queries the backend status every 10 seconds.
       - Progress states (e.g., `Task status: queued`, `Task status: running`, `Task status: succeeded`)
         are printed to `sys.stderr` in real time so the runner/agent is kept aware.
    3. Automatic Download & Local Cache (自动下载与本地缓存):
       - Once generated, the video is AUTOMATICALLY downloaded from the remote server's temporary URL
         and saved locally under the profile's video cache directory.
       - The returned `video` field contains the absolute local filesystem path (e.g., `/opt/data/profiles/athena/cache/videos/volc_...mp4`).
    4. How to Render (展示方式):
       - Always use standard markdown syntax: `![description](file:///absolute/local/path.mp4)`
         to render the video. The container gateway will serve it to the user.
    """

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

    def capabilities(self) -> Dict[str, Any]:
        return {
            "modalities": ["text", "image"],
            "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "landscape", "portrait", "square"],
            "resolutions": ["720p"],
            "max_duration": 10,
            "min_duration": 1,
            "supports_audio": True,
            "supports_negative_prompt": False,
            "max_reference_images": 5,
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
        res = self._generate_sync_wrapper(
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
            **kwargs
        )
        if res.get("success"):
            video_ref = res.get("video")
            task_id = res.get("task_id", "unknown")
            res["agent_guidance"] = (
                "[AGENT GUIDANCE]\n"
                "- 预计耗时 (Estimated Duration): Doubao Seedance 2.0 视频生成一般需要 2 至 3 分钟。\n"
                f"- 任务状态 (Task Status): 这是一个长耗时异步任务，但该工具内置了同步轮询机制（已实时查询完毕，Task ID: {task_id}）。当前任务已全部成功完成。\n"
                "- 自动下载 (Auto-Download): 视频已自动从临时链接下载并缓存在本地文件系统目录，支持离线/后续直接引用。\n"
                f"- 本地文件 (Local File): 请使用绝对路径展示或引用该视频，如：![视频](file://{video_ref})。\n"
                "- 渲染/后续建议: 视频已就绪，请直接渲染并返回给用户，避免重复生成或继续查询状态。"
            )
        else:
            error = res.get("error", "Unknown error")
            res["agent_guidance"] = (
                "[AGENT GUIDANCE]\n"
                f"- 失败原因 (Failure Reason): {error}\n"
                "- 预计耗时 (Estimated Duration): 视频生成本需 2-3 分钟，但由于上述错误已终止。\n"
                "- 确认与排查 (Verification): 请检查您的 VOLCENGINE_API_KEY / ARK_API_KEY 环境变量配置是否正确，"
                "并确保选择的 model (如 doubao-seedance-2.0) 在您的 Volcano Engine 账户中已开通并在服务列表中。\n"
                "- 后续动作 (Next Steps): 修复配置或网络问题后可重新调用该工具。"
            )
        return res

    def _generate_sync_wrapper(
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

            print(f"[volcengine] Video generation successful. Remote Video URL: {video_url}", file=sys.stderr)

            # Automatically download the video to the local profile's video cache
            print("[volcengine] Downloading video to local cache...", file=sys.stderr)
            try:
                from agent.video_gen_provider import save_bytes_video
                video_resp = await client.get(video_url, timeout=_TIMEOUT)
                video_resp.raise_for_status()
                local_path = save_bytes_video(video_resp.content, prefix=f"volc_{model}")
                video_ref = str(local_path)
                print(f"[volcengine] Video downloaded successfully: {video_ref}", file=sys.stderr)
            except Exception as exc:
                print(f"[volcengine] Failed to cache video locally: {exc}. Falling back to remote URL.", file=sys.stderr)
                video_ref = video_url

            return success_response(
                video=video_ref,
                model=model,
                prompt=prompt,
                modality="image" if image_url_norm else "text",
                aspect_ratio=aspect,
                duration=duration or 0,
                provider="volcengine",
                extra={"task_id": task_id, "remote_url": video_url},
            )


def register(ctx) -> None:
    ctx.register_video_gen_provider(VolcengineVideoGenProvider())
    print("[volcengine] Video Gen provider registered successfully.", file=sys.stderr)
