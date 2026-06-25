"""Volcengine Doubao TTS provider plugin."""
from __future__ import annotations

try:
    from plugins.tts.volcengine.provider import VolcengineTTSProvider
except ModuleNotFoundError:  # pragma: no cover - local file-loading fallback
    import importlib.util
    from pathlib import Path

    provider_path = Path(__file__).with_name("provider.py")
    spec = importlib.util.spec_from_file_location("volcengine_tts_provider", provider_path)
    provider_module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(provider_module)
    VolcengineTTSProvider = provider_module.VolcengineTTSProvider


def register(ctx) -> None:
    """Register the Volcengine Doubao TTS provider with Hermes."""
    ctx.register_tts_provider(VolcengineTTSProvider())
