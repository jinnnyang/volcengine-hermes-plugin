"""Volcengine Doubao model provider — Agent Plan / Coding Plan."""
from providers import register_provider
from providers.base import ProviderProfile

volcengine_provider = ProviderProfile(
    name="volces-engine",
    aliases=("volcengine-coding-plan", "volcengine-agent-plan", "doubao"),
    api_mode="chat_completions",
    env_vars=("ARK_API_KEY", "VOLCENGINE_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/plan/v3",
    auth_type="api_key",
    default_aux_model="doubao-seed-2.0-lite",
)

register_provider(volcengine_provider)
