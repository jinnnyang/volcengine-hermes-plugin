from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README_EN = ROOT / "README.md"
README_ZH = ROOT / "README_zh-CN.md"


def test_readmes_document_voice_plugins_and_installation():
    english = README_EN.read_text(encoding="utf-8")
    chinese = README_ZH.read_text(encoding="utf-8")

    for text in (english, chinese):
        assert "plugins/tts/volcengine" in text
        assert "plugins/transcription/volcengine" in text
        assert "tts/volcengine" in text
        assert "transcription/volcengine" in text
        assert "tts:" in text
        assert "stt:" in text
        assert "VOLCENGINE_API_KEY=[REDACTED]" in text
        assert "doubao-seed-tts-2.0" in text
        assert "doubao-seed-asr-2.0" in text


def test_readmes_explain_registry_key_provider_name_and_secret_policy():
    english = README_EN.read_text(encoding="utf-8")
    chinese = README_ZH.read_text(encoding="utf-8")

    assert "registry key" in english
    assert "provider name" in english
    assert "registry key" in chinese
    assert "provider name" in chinese
    assert "never" in english
    assert "config.yaml" in english
    assert "never in" in english

    assert "不要写入" in chinese
    assert "config.yaml" in chinese

