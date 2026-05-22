"""Volcengine video generation — thin wrapper over the built-in backend."""
from __future__ import annotations

from plugins.video_gen.volcengine import VolcengineVideoGenProvider


class VolcesVideoGenProvider(VolcengineVideoGenProvider):
    """User-profile wrapper providing a custom provider name."""

    @property
    def name(self) -> str:
        return "volces-engine"

    @property
    def display_name(self) -> str:
        return "火山引擎 (Seedance)"


def register(ctx) -> None:
    ctx.register_video_gen_provider(VolcesVideoGenProvider())
