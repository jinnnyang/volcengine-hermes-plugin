import importlib.util
import os
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_PROVIDER_PATH = ROOT / "plugins" / "model-providers" / "volcengine" / "__init__.py"


def install_fake_providers(monkeypatch, fetched_models=None):
    registered = []
    providers_module = types.ModuleType("providers")
    base_module = types.ModuleType("providers.base")

    class ProviderProfile:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        def fetch_models(self, *, api_key=None, base_url=None, timeout=8.0):
            self.last_fetch_args = {"api_key": api_key, "base_url": base_url, "timeout": timeout}
            return fetched_models

    def register_provider(provider):
        registered.append(provider)

    providers_module.register_provider = register_provider
    base_module.ProviderProfile = ProviderProfile
    monkeypatch.setitem(sys.modules, "providers", providers_module)
    monkeypatch.setitem(sys.modules, "providers.base", base_module)
    return registered


def load_model_provider_module(monkeypatch, fetched_models=None):
    registered = install_fake_providers(monkeypatch, fetched_models=fetched_models)
    spec = importlib.util.spec_from_file_location("volcengine_model_provider", MODEL_PROVIDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module, registered


def clear_volcengine_env(monkeypatch):
    for key in (
        "VOLCENGINE_BASE_URL",
        "VOLCENGINE_PLAN_MODE",
        "VOLCENGINE_API_KEY",
        "ARK_API_KEY",
        "VOLCENGINE_MODEL",
        "ARK_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_provider_uses_resolved_agent_plan_base_url_by_default(monkeypatch):
    clear_volcengine_env(monkeypatch)
    module, registered = load_model_provider_module(monkeypatch)

    assert len(registered) == 1
    provider = registered[0]

    assert provider.base_url == "https://ark.cn-beijing.volces.com/api/plan/v3"
    assert provider.models_url == "https://ark.cn-beijing.volces.com/api/plan/v3/models"
    assert module.volcengine_provider is provider


def test_provider_honors_endpoint_mode_and_explicit_base_url(monkeypatch):
    clear_volcengine_env(monkeypatch)
    monkeypatch.setenv("VOLCENGINE_PLAN_MODE", "coding")
    _module, registered = load_model_provider_module(monkeypatch)

    assert registered[0].base_url == "https://ark.cn-beijing.volces.com/api/coding/v3"
    assert registered[0].models_url == "https://ark.cn-beijing.volces.com/api/coding/v3/models"

    clear_volcengine_env(monkeypatch)
    monkeypatch.setenv("VOLCENGINE_PLAN_MODE", "coding")
    monkeypatch.setenv("VOLCENGINE_BASE_URL", "https://example.test/custom/v3/")
    _module, registered = load_model_provider_module(monkeypatch)

    assert registered[0].base_url == "https://example.test/custom/v3"
    assert registered[0].models_url == "https://example.test/custom/v3/models"


def test_fetch_models_uses_volcengine_api_key_before_ark_key(monkeypatch):
    clear_volcengine_env(monkeypatch)
    monkeypatch.setenv("VOLCENGINE_API_KEY", "volc-key")
    monkeypatch.setenv("ARK_API_KEY", "ark-key")
    _module, registered = load_model_provider_module(monkeypatch, fetched_models=["live-a"])
    provider = registered[0]

    models = provider.fetch_models(timeout=12.5)

    assert provider.last_fetch_args == {
        "api_key": "volc-key",
        "base_url": provider.base_url,
        "timeout": 12.5,
    }
    assert models[:1] == ["live-a"]
    assert "ark-code-latest" in models


def test_fetch_models_merges_live_fallback_and_manual_model(monkeypatch):
    clear_volcengine_env(monkeypatch)
    monkeypatch.setenv("ARK_MODEL", "custom-endpoint-id")
    _module, registered = load_model_provider_module(
        monkeypatch,
        fetched_models=["live-a", "ark-code-latest", "live-a"],
    )
    provider = registered[0]

    models = provider.fetch_models(api_key="explicit-key")

    assert models[0:2] == ["live-a", "ark-code-latest"]
    assert "custom-endpoint-id" in models
    assert len(models) == len(set(models))


def test_provider_fallback_models_include_manual_model_from_env(monkeypatch):
    clear_volcengine_env(monkeypatch)
    monkeypatch.setenv("VOLCENGINE_MODEL", "manual-model-id")
    _module, registered = load_model_provider_module(monkeypatch)

    provider = registered[0]

    assert provider.default_aux_model == "manual-model-id"
    assert provider.fallback_models[0] == "manual-model-id"
    assert "ark-code-latest" in provider.fallback_models
