from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"


def test_install_script_exposes_voice_feature_flags():
    script = INSTALL.read_text(encoding="utf-8")

    for flag in [
        "--enable-tts",
        "--enable-stt",
        "--set-default-tts",
        "--set-default-stt",
        "--dry-run",
        "--no-config",
    ]:
        assert flag in script


def test_install_script_copies_and_enables_voice_plugins():
    script = INSTALL.read_text(encoding="utf-8")

    assert "plugins/_volcengine_common" in script
    assert "plugins/tts/volcengine" in script
    assert "plugins/transcription/volcengine" in script
    assert "tts/volcengine" in script
    assert "transcription/volcengine" in script
    assert "tts:" in script
    assert "stt:" in script
    assert "provider: volcengine" in script


def test_install_script_keeps_secrets_out_of_config_yaml():
    script = INSTALL.read_text(encoding="utf-8")
    updater = script.split("PYTHON_UPDATER=$(cat << 'EOF'", 1)[1].split("EOF", 1)[0]

    assert "VOLCENGINE_SPEECH_API_KEY" not in updater
    assert "VOLCENGINE_API_KEY" not in updater
    assert "ARK_API_KEY" not in updater
    assert "[HERMES_HOME]/.env" in script
    assert "VOLCENGINE_API_KEY=[REDACTED]" in script


def test_install_script_mentions_config_backup_and_deduplication():
    script = INSTALL.read_text(encoding="utf-8")

    assert "backup" in script.lower()
    assert "sorted(set(" in script or "dict.fromkeys" in script
