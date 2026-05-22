"""Volcengine Doubao model provider — Agent Plan / Coding Plan."""
import sys
from providers import register_provider
from providers.base import ProviderProfile

# Print loading status to resolve black-box issues
print("[volcengine] Model Provider plugin loaded.", file=sys.stderr)

volcengine_provider = ProviderProfile(
    name="volcengine",
    aliases=("volcengine-coding-plan", "volcengine-agent-plan", "doubao", "volces-engine"),
    api_mode="chat_completions",
    env_vars=("VOLCENGINE_API_KEY", "ARK_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/plan/v3",
    auth_type="api_key",
    default_aux_model="doubao-seed-2.0-lite",
)

register_provider(volcengine_provider)
print("[volcengine] Model Provider 'volcengine' successfully registered.", file=sys.stderr)
