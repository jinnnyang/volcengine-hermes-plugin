"""Volcengine Doubao Seed TTS backend for Hermes text_to_speech."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:  # Hermes runtime
    from agent.tts_provider import TTSProvider
except ModuleNotFoundError:  # Local plugin tests outside Hermes source tree
    class TTSProvider:  # type: ignore[no-redef]
        @property
        def name(self) -> str:
            raise NotImplementedError

        @property
        def display_name(self) -> str:
            return self.name

        def is_available(self) -> bool:
            return True

        def list_models(self) -> List[Dict[str, Any]]:
            return []

        def default_model(self) -> Optional[str]:
            models = self.list_models()
            return models[0].get("id") if models else None

        def list_voices(self) -> List[Dict[str, Any]]:
            return []

        def default_voice(self) -> Optional[str]:
            voices = self.list_voices()
            return voices[0].get("id") if voices else None

        def get_setup_schema(self) -> Dict[str, Any]:
            return {"name": self.display_name, "badge": "", "tag": "", "env_vars": []}

try:
    from plugins._volcengine_common.config import resolve_volcengine_speech_api_key
except ModuleNotFoundError:  # pragma: no cover - local file-loading fallback
    import importlib.util

    config_path = Path(__file__).resolve().parents[2] / "_volcengine_common" / "config.py"
    spec = importlib.util.spec_from_file_location("volcengine_common_config", config_path)
    config_module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(config_module)
    resolve_volcengine_speech_api_key = config_module.resolve_volcengine_speech_api_key


DEFAULT_MODEL = "doubao-seed-tts-2.0"
DEFAULT_RESOURCE_ID = "seed-tts-2.0"
DEFAULT_VOICE = "zh_female_vv_uranus_bigtts"
DEFAULT_FORMAT = "wav"
DEFAULT_SAMPLE_RATE = 24000
TTS_ENDPOINT = "https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional"
TTS_END_CODE = 20000000


class VolcengineTTSProvider(TTSProvider):
    """TTS provider for Volcengine Doubao Seed TTS."""

    @property
    def name(self) -> str:
        return "volcengine"

    @property
    def display_name(self) -> str:
        return "Volcengine Doubao TTS"

    def is_available(self) -> bool:
        return bool(resolve_volcengine_speech_api_key())

    def list_models(self) -> List[Dict[str, Any]]:
        return [{"id": DEFAULT_MODEL, "display": "Doubao Seed TTS 2.0"}]

    def default_model(self) -> str:
        return DEFAULT_MODEL

    def list_voices(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": DEFAULT_VOICE,
                "display": "Chinese Female Uranus (BigTTS)",
                "language": "zh-CN",
                "gender": "female",
            }
        ]

    def default_voice(self) -> str:
        return DEFAULT_VOICE

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Volcengine Doubao TTS",
            "badge": "paid",
            "tag": "Doubao Seed TTS 2.0 via Volcengine OpenSpeech",
            "env_vars": [
                {
                    "key": "VOLCENGINE_API_KEY",
                    "prompt": "Volcengine API Key (shared for all services)",
                    "url": "https://console.volcengine.com/ark/region:ark+cn-beijing/apikey",
                }
            ],
        }

    def synthesize(
        self,
        text: str,
        output_path: str,
        *,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        speed: Optional[float] = None,
        format: str = DEFAULT_FORMAT,
        **extra: Any,
    ) -> str:
        api_key = resolve_volcengine_speech_api_key()
        if not api_key:
            raise RuntimeError(
                "Missing Volcengine API key. Set VOLCENGINE_API_KEY or ARK_API_KEY."
            )

        selected_voice = voice or self.default_voice()
        selected_format = format or DEFAULT_FORMAT
        sample_rate = int(extra.get("sample_rate") or DEFAULT_SAMPLE_RATE)
        resource_id = str(extra.get("resource_id") or DEFAULT_RESOURCE_ID)
        endpoint = str(extra.get("base_url") or TTS_ENDPOINT)

        payload = {
            "req_params": {
                "text": text,
                "speaker": selected_voice,
                "audio_params": {
                    "format": selected_format,
                    "sample_rate": sample_rate,
                },
            }
        }
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "X-Api-Key": api_key,
            "X-Api-Resource-Id": resource_id,
            "X-Control-Require-Usage-Tokens-Return": "*",
        }

        response = httpx.post(endpoint, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        log_id = response.headers.get("X-Tt-Logid", "")

        audio_parts: list[bytes] = []
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            chunk = json.loads(line)
            code = int(chunk.get("code") or 0)
            if code == TTS_END_CODE:
                break
            if code > 0:
                message = str(chunk.get("message") or chunk.get("error") or "unknown error")
                raise RuntimeError(f"Volcengine TTS API Error [{code}]: {message}; log_id={log_id}")
            data = chunk.get("data")
            if data:
                audio_parts.append(base64.b64decode(data))

        if not audio_parts:
            raise RuntimeError(f"Volcengine TTS returned no audio data; log_id={log_id}")

        Path(output_path).write_bytes(b"".join(audio_parts))
        return output_path
