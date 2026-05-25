"""Volcengine Doubao model provider — Agent Plan / Coding Plan."""
import sys
import os
from providers import register_provider
from providers.base import ProviderProfile

# Print loading status to resolve black-box issues
print("[volcengine] Model Provider plugin loaded.", file=sys.stderr)

class VolcengineProviderProfile(ProviderProfile):
    """Volcengine Ark model provider supporting dynamic /models fetching."""

    def fetch_models(self, *, api_key: str | None = None, timeout: float = 8.0):
        # If API key is not passed, try env vars
        if not api_key:
            api_key = os.environ.get("ARK_API_KEY") or os.environ.get("VOLCENGINE_API_KEY")
        
        # Use parent's fetch_models to query {base_url}/models
        models = super().fetch_models(api_key=api_key, timeout=timeout) or []
        fallback = [
            "doubao-seed-2.0-lite",
            "doubao-seed-2.0-mini",
            "doubao-seed-2.0-pro",
            "doubao-seed-2.0-code",
            "ark-code-latest",
        ]
        
        # Return merged unique list ensuring fallback is always present
        seen = set()
        merged = [m for m in models + fallback if not (m in seen or seen.add(m))]
        print(f"[volcengine] Live model fetch loaded {len(merged)} models (including {len(models)} live endpoints).", file=sys.stderr)
        return merged

volcengine_provider = VolcengineProviderProfile(
    name="volcengine",
    display_name="Volcengine AI",
    description="Volcengine AI (Doubao models — direct API)",
    aliases=("volcengine-coding-plan", "volcengine-agent-plan", "doubao", "volces-engine"),
    api_mode="chat_completions",
    env_vars=("VOLCENGINE_API_KEY", "ARK_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/plan/v3",
    auth_type="api_key",
    default_aux_model="doubao-seed-2.0-lite",
    fallback_models=(
        "doubao-seed-2.0-lite",
        "doubao-seed-2.0-mini",
        "doubao-seed-2.0-pro",
        "doubao-seed-2.0-code",
        "ark-code-latest",
    )
)

register_provider(volcengine_provider)
print("[volcengine] Model Provider 'volcengine' successfully registered.", file=sys.stderr)

