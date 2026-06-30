import base64
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVIDER_PATH = ROOT / "plugins" / "tts" / "volcengine" / "provider.py"
INIT_PATH = ROOT / "plugins" / "tts" / "volcengine" / "__init__.py"
PLUGIN_YAML_PATH = ROOT / "plugins" / "tts" / "volcengine" / "plugin.yaml"
CONFIG_PATH = ROOT / "plugins" / "_volcengine_common" / "config.py"


def load_provider_module():
    spec = importlib.util.spec_from_file_location("volcengine_tts_provider", PROVIDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_plugin_module():
    spec = importlib.util.spec_from_file_location("volcengine_tts_plugin", INIT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_config_module():
    spec = importlib.util.spec_from_file_location("volcengine_common_config_for_tts", CONFIG_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_plugin_manifest_and_register_function():
    assert PLUGIN_YAML_PATH.read_text(encoding="utf-8").splitlines()[:9] == [
        "id: text-to-speech-volcengine",
        "name: Volcengine Text to Speech Provider",
        "version: 0.1.0",
        "description: Volcengine Doubao Seed TTS backend for Hermes text_to_speech.",
        "author: jinnnyang",
        "kind: backend",
        "requires_env:",
        "  - VOLCENGINE_API_KEY",
        "provides_tts_providers:",
    ]

    module = load_plugin_module()

    class FakeContext:
        def __init__(self):
            self.providers = []

        def register_tts_provider(self, provider):
            self.providers.append(provider)

    ctx = FakeContext()
    module.register(ctx)

    assert len(ctx.providers) == 1
    assert ctx.providers[0].name == "volcengine"


def test_provider_identity_defaults_and_availability(monkeypatch):
    module = load_provider_module()
    provider = module.VolcengineTTSProvider()

    monkeypatch.delenv("VOLCENGINE_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    assert provider.name == "volcengine"
    assert provider.display_name == "Volcengine Doubao TTS"
    assert provider.is_available() is False
    assert provider.default_model() == "doubao-seed-tts-2.0"
    assert provider.default_voice() == "zh_female_vv_uranus_bigtts"
    assert provider.list_models() == [
        {"id": "doubao-seed-tts-2.0", "display": "Doubao Seed TTS 2.0"}
    ]
    assert provider.list_voices()[0]["id"] == "zh_female_vv_uranus_bigtts"

    monkeypatch.setenv("VOLCENGINE_API_KEY", "api-key")

    assert provider.is_available() is True


def test_speech_api_key_precedence(monkeypatch):
    config = load_config_module()

    monkeypatch.setenv("ARK_API_KEY", "ark-key")
    monkeypatch.setenv("VOLCENGINE_API_KEY", "volcengine-key")

    assert config.resolve_volcengine_speech_api_key() == "volcengine-key"

    monkeypatch.delenv("VOLCENGINE_API_KEY")
    assert config.resolve_volcengine_speech_api_key() == "ark-key"


def test_synthesize_posts_tts_request_and_writes_base64_chunks(monkeypatch, tmp_path):
    module = load_provider_module()
    provider = module.VolcengineTTSProvider()
    output_path = tmp_path / "speech.wav"
    captured = {}

    class FakeResponse:
        headers = {"X-Tt-Logid": "log-123"}

        def raise_for_status(self):
            return None

        def iter_lines(self):
            audio = base64.b64encode(b"fake-wav-bytes").decode("ascii")
            yield json.dumps({"code": 0, "data": audio})
            yield json.dumps({"code": 20000000, "message": "done"})

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("VOLCENGINE_API_KEY", "api-key")
    monkeypatch.setattr(module.httpx, "post", fake_post)

    result = provider.synthesize("今天天气很好", str(output_path))

    assert result == str(output_path)
    assert output_path.read_bytes() == b"fake-wav-bytes"
    assert captured["url"] == module.TTS_ENDPOINT
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "X-Api-Key": "api-key",
        "X-Api-Resource-Id": "seed-tts-2.0",
        "X-Control-Require-Usage-Tokens-Return": "*",
    }
    assert captured["json"] == {
        "req_params": {
            "text": "今天天气很好",
            "speaker": "zh_female_vv_uranus_bigtts",
            "audio_params": {
                "format": "wav",
                "sample_rate": 24000,
            },
        }
    }


def test_synthesize_raises_clear_error_with_log_id(monkeypatch, tmp_path):
    module = load_provider_module()
    provider = module.VolcengineTTSProvider()

    class FakeResponse:
        headers = {"X-Tt-Logid": "log-err"}

        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield json.dumps({"code": 45000000, "message": "bad request"})

    monkeypatch.setenv("VOLCENGINE_API_KEY", "api-key")
    monkeypatch.setattr(module.httpx, "post", lambda *args, **kwargs: FakeResponse())

    try:
        provider.synthesize("错误测试", str(tmp_path / "speech.wav"))
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    assert "45000000" in message
    assert "bad request" in message
    assert "log-err" in message
