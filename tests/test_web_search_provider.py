import importlib.util
from pathlib import Path
from types import SimpleNamespace


PROVIDER_PATH = Path(__file__).resolve().parents[1] / "plugins" / "web" / "volcengine" / "provider.py"
INIT_PATH = Path(__file__).resolve().parents[1] / "plugins" / "web" / "volcengine" / "__init__.py"
PLUGIN_YAML_PATH = Path(__file__).resolve().parents[1] / "plugins" / "web" / "volcengine" / "plugin.yaml"


def load_provider_module():
    spec = importlib.util.spec_from_file_location("volcengine_web_provider", PROVIDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_provider_identity_and_capabilities():
    module = load_provider_module()
    provider = module.VolcengineWebSearchProvider()

    assert provider.name == "volcengine"
    assert provider.display_name == "Volcengine Doubao Search"
    assert provider.supports_search() is True
    assert provider.supports_extract() is False


def test_provider_availability_checks_supported_env_vars(monkeypatch):
    module = load_provider_module()
    provider = module.VolcengineWebSearchProvider()

    for key in module.SEARCH_API_KEY_ENV_VARS:
        monkeypatch.delenv(key, raising=False)

    assert provider.is_available() is False

    monkeypatch.setenv("VOLCENGINE_API_KEY", "volcengine-api-key")

    assert provider.is_available() is True


def test_search_without_api_key_returns_auth_error(monkeypatch):
    module = load_provider_module()
    provider = module.VolcengineWebSearchProvider()

    for key in module.SEARCH_API_KEY_ENV_VARS:
        monkeypatch.delenv(key, raising=False)

    result = provider.search("Hermes Agent", limit=3)

    assert result["success"] is False
    assert "VOLCENGINE_API_KEY" in result["error"]


def test_search_maps_doubao_web_results_to_hermes_shape(monkeypatch):
    module = load_provider_module()
    provider = module.VolcengineWebSearchProvider()
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ResponseMetadata": {},
                "Result": {
                    "WebResults": [
                        {
                            "SortId": 2,
                            "Title": "Hermes Agent Docs",
                            "SiteName": "Nous Research",
                            "AuthInfoDes": "Official",
                            "Url": "https://hermes-agent.nousresearch.com/docs",
                            "Summary": "Hermes Agent documentation.",
                            "Snippet": "Fallback snippet should not be used when summary exists.",
                        },
                        {
                            "Title": "Volcengine Ark",
                            "Url": "https://www.volcengine.com/product/ark",
                            "Snippet": "Volcengine Ark model platform.",
                        },
                    ]
                },
            }

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("VOLCENGINE_API_KEY", "test-search-key")
    monkeypatch.setattr(module.httpx, "post", fake_post)

    result = provider.search("Hermes Agent 火山", limit=99)

    assert captured["url"] == "https://open.feedcoopapi.com/search_api/web_search"
    assert captured["json"] == {
        "Query": "Hermes Agent 火山",
        "SearchType": "web",
        "Count": 50,
        "NeedSummary": True,
    }
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-search-key",
        "X-Traffic-Tag": "skill_web_search_common",
    }
    assert result == {
        "success": True,
        "data": {
            "web": [
                {
                    "title": "Hermes Agent Docs",
                    "url": "https://hermes-agent.nousresearch.com/docs",
                    "description": "Nous Research | Official\nHermes Agent documentation.",
                    "position": 2,
                },
                {
                    "title": "Volcengine Ark",
                    "url": "https://www.volcengine.com/product/ark",
                    "description": "Volcengine Ark model platform.",
                    "position": 2,
                },
            ]
        },
    }


def test_search_includes_optional_filters_from_env(monkeypatch):
    module = load_provider_module()
    provider = module.VolcengineWebSearchProvider()
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"Result": {"WebResults": []}}

    def fake_post(url, *, json, headers, timeout):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setenv("VOLCENGINE_API_KEY", "test-search-key")
    monkeypatch.setenv("VOLCENGINE_SEARCH_AUTH_LEVEL", "1")
    monkeypatch.setenv("VOLCENGINE_SEARCH_TIME_RANGE", "OneWeek")
    monkeypatch.setenv("VOLCENGINE_SEARCH_QUERY_REWRITE", "true")
    monkeypatch.setattr(module.httpx, "post", fake_post)

    result = provider.search("火山方舟 Agent Plan", limit=5)

    assert result["success"] is True
    assert captured["json"] == {
        "Query": "火山方舟 Agent Plan",
        "SearchType": "web",
        "Count": 5,
        "NeedSummary": True,
        "Filter": {"AuthInfoLevel": 1},
        "TimeRange": "OneWeek",
        "QueryControl": {"QueryRewrite": True},
    }


def test_search_maps_api_error_response(monkeypatch):
    module = load_provider_module()
    provider = module.VolcengineWebSearchProvider()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ResponseMetadata": {
                    "Error": {
                        "Code": "10403",
                        "Message": "invalid_api_key",
                    }
                }
            }

    monkeypatch.setenv("VOLCENGINE_API_KEY", "bad-key")
    monkeypatch.setattr(module.httpx, "post", lambda *args, **kwargs: FakeResponse())

    result = provider.search("Hermes", limit=3)

    assert result == {
        "success": False,
        "error": "Volcengine Doubao Search API Error [10403]: invalid_api_key",
    }


def test_setup_schema_exposes_primary_key_prompt():
    module = load_provider_module()
    provider = module.VolcengineWebSearchProvider()

    schema = provider.get_setup_schema()

    assert schema["name"] == "Volcengine Doubao Search"
    assert schema["badge"] == "paid"
    assert schema["env_vars"][0]["key"] == "VOLCENGINE_API_KEY"
    assert "search-infinity" in schema["env_vars"][0]["url"]


def test_plugin_manifest_and_register_function():
    assert PLUGIN_YAML_PATH.read_text(encoding="utf-8").splitlines()[:8] == [
        "id: web-search-volcengine",
        "name: Volcengine Web Search Provider",
        "version: 0.1.0",
        "description: Volcengine Doubao Search backend for Hermes web_search.",
        "author: jinnnyang",
        "kind: backend",
        "provides_web_providers:",
        "  - volcengine",
    ]

    spec = importlib.util.spec_from_file_location("volcengine_web_plugin", INIT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    class FakeContext:
        def __init__(self):
            self.providers = []

        def register_web_search_provider(self, provider):
            self.providers.append(provider)

    ctx = FakeContext()
    module.register(ctx)

    assert len(ctx.providers) == 1
    assert ctx.providers[0].name == "volcengine"
