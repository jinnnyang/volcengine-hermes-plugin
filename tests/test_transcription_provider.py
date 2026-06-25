import gzip
import importlib.util
import json
import struct
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVIDER_PATH = ROOT / "plugins" / "transcription" / "volcengine" / "provider.py"
PROTOCOL_PATH = ROOT / "plugins" / "transcription" / "volcengine" / "protocol.py"
INIT_PATH = ROOT / "plugins" / "transcription" / "volcengine" / "__init__.py"
PLUGIN_YAML_PATH = ROOT / "plugins" / "transcription" / "volcengine" / "plugin.yaml"


def load_provider_module():
    spec = importlib.util.spec_from_file_location("volcengine_transcription_provider", PROVIDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_protocol_module():
    spec = importlib.util.spec_from_file_location("volcengine_transcription_protocol", PROTOCOL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_plugin_module():
    spec = importlib.util.spec_from_file_location("volcengine_transcription_plugin", INIT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_plugin_manifest_and_register_function():
    assert PLUGIN_YAML_PATH.read_text(encoding="utf-8").splitlines()[:9] == [
        "id: speech-to-text-volcengine",
        "name: Volcengine Speech to Text Provider",
        "version: 0.1.0",
        "description: Volcengine Doubao Seed ASR backend for Hermes transcription.",
        "author: jinnnyang",
        "kind: backend",
        "requires_env:",
        "  - VOLCENGINE_SPEECH_API_KEY",
        "provides_transcription_providers:",
    ]

    module = load_plugin_module()

    class FakeContext:
        def __init__(self):
            self.providers = []

        def register_transcription_provider(self, provider):
            self.providers.append(provider)

    ctx = FakeContext()
    module.register(ctx)

    assert len(ctx.providers) == 1
    assert ctx.providers[0].name == "volcengine"


def test_provider_identity_defaults_and_availability(monkeypatch):
    module = load_provider_module()
    provider = module.VolcengineTranscriptionProvider()

    monkeypatch.delenv("VOLCENGINE_SPEECH_API_KEY", raising=False)
    monkeypatch.delenv("VOLCENGINE_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    assert provider.name == "volcengine"
    assert provider.display_name == "Volcengine Doubao ASR"
    assert provider.is_available() is False
    assert module.ASR_ASYNC_ENDPOINT == "wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_async"
    assert module.ASR_NOSTREAM_ENDPOINT == "wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_nostream"
    assert module.ASR_ENDPOINT == module.ASR_NOSTREAM_ENDPOINT
    assert provider.default_model() == "doubao-seed-asr-2.0"
    assert provider.list_models() == [
        {"id": "doubao-seed-asr-2.0", "display": "Doubao Seed ASR 2.0"}
    ]

    monkeypatch.setenv("VOLCENGINE_SPEECH_API_KEY", "speech-key")
    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: object() if name == "websockets" else None)

    assert provider.is_available() is True


def test_asr_headers_include_resource_and_request_ids(monkeypatch):
    module = load_provider_module()
    provider = module.VolcengineTranscriptionProvider()

    monkeypatch.setenv("VOLCENGINE_SPEECH_API_KEY", "speech-key")
    monkeypatch.setattr(module.uuid, "uuid4", lambda: "uuid-fixed")

    headers = provider._build_headers()

    assert headers == {
        "X-Api-Key": "speech-key",
        "X-Api-Resource-Id": "volc.seedasr.sauc.duration",
        "X-Api-Request-Id": "uuid-fixed",
        "X-Api-Connect-Id": "uuid-fixed",
        "X-Api-Sequence": "-1",
    }


def test_default_auto_language_does_not_send_language_hint(monkeypatch, tmp_path):
    module = load_provider_module()
    provider = module.VolcengineTranscriptionProvider()
    audio_path = tmp_path / "input.wav"
    audio_path.write_bytes(b"RIFF....WAVEfmt ")
    captured = {}

    async def fake_run_asr_websocket(file_path, *, headers, model, language, endpoint, chunk_size):
        captured["language"] = language
        return "今天天气很好"

    monkeypatch.setenv("VOLCENGINE_SPEECH_API_KEY", "speech-key")
    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: object() if name == "websockets" else None)
    monkeypatch.setattr(provider, "_run_asr_websocket", fake_run_asr_websocket)

    result = provider.transcribe(str(audio_path), language="auto")

    assert result == {
        "success": True,
        "transcript": "今天天气很好",
        "provider": "volcengine",
    }
    assert captured["language"] is None


def test_non_wav_input_is_converted_with_ffmpeg(monkeypatch, tmp_path):
    module = load_provider_module()
    provider = module.VolcengineTranscriptionProvider()
    source = tmp_path / "input.ogg"
    source.write_bytes(b"ogg-audio")
    converted = tmp_path / "converted.wav"
    calls = []

    def fake_run(args, *, check, capture_output):
        calls.append(args)
        converted.write_bytes(b"RIFF....WAVEfmt ")
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.shutil, "which", lambda name: "ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = provider._prepare_audio(str(source), output_path=str(converted))

    assert result == str(converted)
    assert calls == [[
        "ffmpeg", "-y", "-i", str(source), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(converted)
    ]]


def test_protocol_builds_and_parses_gzip_json_messages():
    protocol = load_protocol_module()
    payload = {"result": {"text": "今天天气很好"}}

    message = protocol.build_full_client_request(payload, sequence=1)

    assert message[:4] == bytes([0x11, 0x11, 0x11, 0x00])
    assert struct.unpack(">i", message[4:8])[0] == 1
    payload_size = int.from_bytes(message[8:12], "big", signed=True)
    compressed_payload = message[12:]
    assert payload_size == len(compressed_payload)
    assert json.loads(gzip.decompress(compressed_payload).decode("utf-8")) == payload


def test_protocol_builds_audio_only_frames_with_sequence_and_final_marker():
    protocol = load_protocol_module()

    audio = protocol.build_audio_only_request(b"audio", sequence=2)
    final = protocol.build_audio_only_request(b"", sequence=3, final=True)

    assert audio[:4] == bytes([0x11, 0x21, 0x00, 0x00])
    assert struct.unpack(">i", audio[4:8])[0] == 2
    assert struct.unpack(">I", audio[8:12])[0] == len(b"audio")
    assert audio[12:] == b"audio"

    assert final[:4] == bytes([0x11, 0x23, 0x00, 0x00])
    assert struct.unpack(">i", final[4:8])[0] == -3
    assert struct.unpack(">I", final[8:12])[0] == 0
    assert final[12:] == b""


def test_protocol_parses_asr_server_response_variants():
    protocol = load_protocol_module()
    payload = gzip.compress(json.dumps({"result": {"text": "识别成功"}}, ensure_ascii=False).encode("utf-8"))
    full_response = bytearray(bytes([0x11, 0x91, 0x11, 0x00]))
    full_response.extend(struct.pack(">i", 9))
    full_response.extend(struct.pack(">i", len(payload)))
    full_response.extend(payload)

    ack = bytearray(bytes([0x11, 0xB0, 0x00, 0x00]))
    ack.extend(struct.pack(">i", 10))

    error_payload = json.dumps({"message": "bad audio"}).encode("utf-8")
    error_response = bytearray(bytes([0x11, 0xF0, 0x10, 0x00]))
    error_response.extend(struct.pack(">I", 400))
    error_response.extend(struct.pack(">I", len(error_payload)))
    error_response.extend(error_payload)

    last_response = bytearray(bytes([0x11, 0x93, 0x11, 0x00]))
    last_response.extend(struct.pack(">i", -11))
    last_response.extend(struct.pack(">i", len(payload)))
    last_response.extend(payload)

    assert protocol.parse_server_response(bytes(full_response)) == {
        "is_last_package": False,
        "sequence": 9,
        "message": {"result": {"text": "识别成功"}},
        "size": len(payload),
    }
    assert protocol.parse_server_response(bytes(ack)) == {
        "is_last_package": False,
        "sequence": 10,
    }
    assert protocol.parse_server_response(bytes(error_response)) == {
        "is_last_package": False,
        "code": 400,
        "message": {"message": "bad audio"},
        "size": len(error_payload),
    }
    assert protocol.parse_server_response(bytes(last_response))["is_last_package"] is True


def test_transcribe_maps_websocket_result_and_errors(monkeypatch, tmp_path):
    module = load_provider_module()
    provider = module.VolcengineTranscriptionProvider()
    audio_path = tmp_path / "input.wav"
    audio_path.write_bytes(b"RIFF....WAVEfmt ")

    async def fake_success(*args, **kwargs):
        return "识别成功"

    async def fake_error(*args, **kwargs):
        raise RuntimeError("ASR API Error [400]: bad audio; request_id=req-1")

    monkeypatch.setenv("VOLCENGINE_SPEECH_API_KEY", "speech-key")
    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: object() if name == "websockets" else None)

    monkeypatch.setattr(provider, "_run_asr_websocket", fake_success)
    assert provider.transcribe(str(audio_path)) == {
        "success": True,
        "transcript": "识别成功",
        "provider": "volcengine",
    }

    monkeypatch.setattr(provider, "_run_asr_websocket", fake_error)
    result = provider.transcribe(str(audio_path))
    assert result["success"] is False
    assert result["transcript"] == ""
    assert result["provider"] == "volcengine"
    assert "ASR API Error [400]" in result["error"]
