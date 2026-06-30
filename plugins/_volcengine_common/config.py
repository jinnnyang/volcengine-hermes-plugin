"""Shared configuration helpers for Volcengine Hermes plugins."""
from __future__ import annotations

import os

DEFAULT_REGION_BASE_URL = "https://ark.cn-beijing.volces.com"

_PLAN_MODE_PATHS = {
    "agent": "/api/plan/v3",
    "agent_plan": "/api/plan/v3",
    "plan": "/api/plan/v3",
    "coding": "/api/coding/v3",
    "coding_plan": "/api/coding/v3",
    "api": "/api/v3",
    "ark": "/api/v3",
    "payg": "/api/v3",
    "pay_as_you_go": "/api/v3",
}


def _strip_trailing_slash(value: str) -> str:
    return value.rstrip("/")


def resolve_volcengine_base_url() -> str:
    """Resolve the OpenAI-compatible Volcengine base URL.

    Precedence:
    1. VOLCENGINE_BASE_URL, if explicitly provided.
    2. VOLCENGINE_PLAN_MODE mapped to a known Ark API path.
    3. Agent Plan as the default.
    """
    explicit_base_url = os.environ.get("VOLCENGINE_BASE_URL", "").strip()
    if explicit_base_url:
        return _strip_trailing_slash(explicit_base_url)

    mode = os.environ.get("VOLCENGINE_PLAN_MODE", "agent").strip().lower()
    path = _PLAN_MODE_PATHS.get(mode, _PLAN_MODE_PATHS["agent"])
    return DEFAULT_REGION_BASE_URL + path


def resolve_volcengine_endpoint(suffix: str) -> str:
    """Join the resolved base URL with an endpoint suffix."""
    return resolve_volcengine_base_url().rstrip("/") + "/" + suffix.lstrip("/")


def resolve_volcengine_speech_api_key() -> str:
    """Resolve the API key for Volcengine speech providers.

    Precedence:
    1. VOLCENGINE_API_KEY, the shared Volcengine API key.
    2. ARK_API_KEY, the official Ark-compatible fallback name.
    """
    for name in ("VOLCENGINE_API_KEY", "ARK_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""
