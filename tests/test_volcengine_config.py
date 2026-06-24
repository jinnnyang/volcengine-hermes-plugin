import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "plugins" / "_volcengine_common" / "config.py"


def load_config_module():
    spec = importlib.util.spec_from_file_location("volcengine_common_config", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_default_base_url_uses_agent_plan(monkeypatch):
    monkeypatch.delenv("VOLCENGINE_BASE_URL", raising=False)
    monkeypatch.delenv("VOLCENGINE_PLAN_MODE", raising=False)

    config = load_config_module()

    assert config.resolve_volcengine_base_url() == "https://ark.cn-beijing.volces.com/api/plan/v3"


def test_plan_mode_coding_uses_coding_plan_url(monkeypatch):
    monkeypatch.delenv("VOLCENGINE_BASE_URL", raising=False)
    monkeypatch.setenv("VOLCENGINE_PLAN_MODE", "coding")

    config = load_config_module()

    assert config.resolve_volcengine_base_url() == "https://ark.cn-beijing.volces.com/api/coding/v3"


def test_plan_mode_api_uses_pay_as_you_go_url(monkeypatch):
    monkeypatch.delenv("VOLCENGINE_BASE_URL", raising=False)
    monkeypatch.setenv("VOLCENGINE_PLAN_MODE", "api")

    config = load_config_module()

    assert config.resolve_volcengine_base_url() == "https://ark.cn-beijing.volces.com/api/v3"


def test_explicit_base_url_overrides_plan_mode_and_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("VOLCENGINE_PLAN_MODE", "coding")
    monkeypatch.setenv("VOLCENGINE_BASE_URL", "https://example.test/custom/v3/")

    config = load_config_module()

    assert config.resolve_volcengine_base_url() == "https://example.test/custom/v3"


def test_endpoint_joins_suffix_without_double_slash(monkeypatch):
    monkeypatch.setenv("VOLCENGINE_BASE_URL", "https://example.test/base/")

    config = load_config_module()

    assert config.resolve_volcengine_endpoint("/models") == "https://example.test/base/models"
