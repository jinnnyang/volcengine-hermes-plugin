"""Volcengine Doubao model provider — Agent Plan / Coding Plan / Ark API."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Iterable

from providers import register_provider
from providers.base import ProviderProfile

try:
    from plugins._volcengine_common.config import (
        resolve_volcengine_base_url,
        resolve_volcengine_endpoint,
    )
except ModuleNotFoundError:  # pragma: no cover - local file-loading fallback
    config_path = Path(__file__).resolve().parents[2] / "_volcengine_common" / "config.py"
    spec = importlib.util.spec_from_file_location("volcengine_common_config", config_path)
    config_module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(config_module)
    resolve_volcengine_base_url = config_module.resolve_volcengine_base_url
    resolve_volcengine_endpoint = config_module.resolve_volcengine_endpoint


# Print loading status to resolve black-box issues
print("[volcengine] Model Provider plugin loaded.", file=sys.stderr)

FALLBACK_MODELS = (
    "auto",
    "doubao-seed-2.0-code",
    "doubao-seed-2.0-pro",
    "doubao-seed-2.0-lite",
    "doubao-seed-2.0-mini",
    "glm-5.2",
    "glm-latest",
    "kimi-k2.7-code",
    "minimax-m3",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "minimax-m2.7",
    "kimi-k2.6",
    "ark-code-latest",
)


def _first_non_empty(values: Iterable[str | None]) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _get_api_key() -> str:
    return _first_non_empty(
        (
            os.environ.get("VOLCENGINE_API_KEY"),
            os.environ.get("ARK_API_KEY"),
        )
    )


def _manual_model() -> str:
    return _first_non_empty(
        (
            os.environ.get("VOLCENGINE_MODEL"),
            os.environ.get("ARK_MODEL"),
        )
    )


def _unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def _fallback_models() -> tuple[str, ...]:
    manual = _manual_model()
    return tuple(_unique(([manual] if manual else []) + list(FALLBACK_MODELS)))


class VolcengineProviderProfile(ProviderProfile):
    """Volcengine Ark model provider supporting dynamic /models fetching."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ):
        if not api_key:
            api_key = _get_api_key()

        effective_base_url = (base_url or self.base_url).rstrip("/")
        models = (
            super().fetch_models(
                api_key=api_key,
                base_url=effective_base_url,
                timeout=timeout,
            )
            or []
        )
        merged = _unique(list(models) + list(self.fallback_models))
        print(
            f"[volcengine] Live model fetch loaded {len(merged)} models "
            f"(including {len(models)} live endpoints).",
            file=sys.stderr,
        )
        return merged


_DEFAULT_MODEL = _manual_model() or FALLBACK_MODELS[0]
_BASE_URL = resolve_volcengine_base_url()

volcengine_provider = VolcengineProviderProfile(
    name="volcengine",
    display_name="Volcengine AI",
    description="Volcengine AI (Doubao models — Agent Plan / Coding Plan / Ark API)",
    aliases=("volcengine-coding-plan", "volcengine-agent-plan", "doubao", "volces-engine"),
    api_mode="chat_completions",
    env_vars=("VOLCENGINE_API_KEY", "ARK_API_KEY"),
    base_url=_BASE_URL,
    models_url=resolve_volcengine_endpoint("models"),
    auth_type="api_key",
    default_aux_model=_DEFAULT_MODEL,
    fallback_models=_fallback_models(),
)

register_provider(volcengine_provider)
print("[volcengine] Model Provider 'volcengine' successfully registered.", file=sys.stderr)
