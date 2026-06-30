import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE_PROVIDER_PATH = ROOT / "plugins" / "image_gen" / "volcengine" / "__init__.py"
VIDEO_PROVIDER_PATH = ROOT / "plugins" / "video_gen" / "volcengine" / "__init__.py"


def install_fake_image_agent_module(monkeypatch):
    agent = types.ModuleType("agent")
    image_module = types.ModuleType("agent.image_gen_provider")
    image_module.DEFAULT_ASPECT_RATIO = "landscape"

    class ImageGenProvider:
        pass

    def error_response(**kwargs):
        return {"success": False, **kwargs}

    def success_response(image, model, prompt, aspect_ratio, provider, extra=None, **kwargs):
        return {
            "success": True,
            "image": image,
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "provider": provider,
            **(extra or {}),
            **kwargs,
        }

    def resolve_aspect_ratio(value):
        return value if value in {"landscape", "square", "portrait"} else "landscape"

    def save_b64_image(*args, **kwargs):
        return Path("C:/tmp/fake.png")

    image_module.ImageGenProvider = ImageGenProvider
    image_module.error_response = error_response
    image_module.resolve_aspect_ratio = resolve_aspect_ratio
    image_module.save_b64_image = save_b64_image
    image_module.success_response = success_response
    monkeypatch.setitem(sys.modules, "agent", agent)
    monkeypatch.setitem(sys.modules, "agent.image_gen_provider", image_module)


def install_fake_video_agent_module(monkeypatch):
    agent = types.ModuleType("agent")
    video_module = types.ModuleType("agent.video_gen_provider")
    video_module.DEFAULT_ASPECT_RATIO = "16:9"

    class VideoGenProvider:
        pass

    def error_response(**kwargs):
        return {"success": False, **kwargs}

    def success_response(video, model, prompt, modality, aspect_ratio, duration, provider, extra=None, **kwargs):
        return {
            "success": True,
            "video": video,
            "model": model,
            "prompt": prompt,
            "modality": modality,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "provider": provider,
            **(extra or {}),
            **kwargs,
        }

    video_module.VideoGenProvider = VideoGenProvider
    video_module.error_response = error_response
    video_module.success_response = success_response
    monkeypatch.setitem(sys.modules, "agent", agent)
    monkeypatch.setitem(sys.modules, "agent.video_gen_provider", video_module)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_image_provider_exposes_only_seedream_5_lite(monkeypatch):
    install_fake_image_agent_module(monkeypatch)
    module = load_module(IMAGE_PROVIDER_PATH, "volcengine_image_provider_contract")
    provider = module.VolcengineImageGenProvider()

    assert module.DEFAULT_MODEL == "doubao-seedream-5.0-lite"
    assert provider.default_model() == "doubao-seedream-5.0-lite"
    assert [model["id"] for model in provider.list_models()] == ["doubao-seedream-5.0-lite"]
    assert provider.capabilities() == {"modalities": ["text"], "max_reference_images": 0}


def test_image_provider_rejects_source_images_for_text_only_model(monkeypatch):
    install_fake_image_agent_module(monkeypatch)
    module = load_module(IMAGE_PROVIDER_PATH, "volcengine_image_provider_text_only")
    provider = module.VolcengineImageGenProvider()

    result = provider.generate("改成赛博朋克风", image_url="https://example.test/source.png")

    assert result["success"] is False
    assert result["error_type"] == "unsupported_modality"
    assert "text-to-image only" in result["error"]
    assert result["model"] == "doubao-seedream-5.0-lite"


def test_image_provider_rejects_unknown_model_before_network(monkeypatch):
    install_fake_image_agent_module(monkeypatch)
    module = load_module(IMAGE_PROVIDER_PATH, "volcengine_image_provider_unknown_model")
    provider = module.VolcengineImageGenProvider()

    result = provider.generate("一只猫", model="doubao-seedream-5.0-pro")

    assert result["success"] is False
    assert result["error_type"] == "unsupported_model"
    assert "doubao-seedream-5.0-lite" in result["error"]


def test_video_provider_defaults_to_seedance_1_5_pro(monkeypatch):
    install_fake_video_agent_module(monkeypatch)
    module = load_module(VIDEO_PROVIDER_PATH, "volcengine_video_provider_contract")
    provider = module.VolcengineVideoGenProvider()

    assert module.DEFAULT_MODEL == "doubao-seedance-1.5-pro"
    assert provider.default_model() == "doubao-seedance-1.5-pro"
    assert [model["id"] for model in provider.list_models()] == ["doubao-seedance-1.5-pro"]
    assert provider.capabilities()["modalities"] == ["text", "image"]
    assert provider.capabilities()["max_reference_images"] == 1


def test_video_payload_uses_default_seedance_model(monkeypatch):
    install_fake_video_agent_module(monkeypatch)
    module = load_module(VIDEO_PROVIDER_PATH, "volcengine_video_provider_payload")
    provider = module.VolcengineVideoGenProvider()
    captured = {}

    class FakeCreateResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "task-123"}

    class FakeStatusResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "succeeded", "result": {"video_url": "https://example.test/video.mp4"}}

    class FakeVideoResponse:
        content = b"fake-video"

        def raise_for_status(self):
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, *, json, headers, timeout):
            captured["url"] = url
            captured["payload"] = json
            captured["headers"] = headers
            return FakeCreateResponse()

        def get(self, url, *, headers=None, timeout=None):
            if url.endswith("/task-123"):
                return FakeStatusResponse()
            return FakeVideoResponse()

    monkeypatch.setenv("VOLCENGINE_API_KEY", "test-key")
    monkeypatch.setattr(module.httpx, "Client", lambda: FakeClient())
    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)

    # Import inside provider is patched by replacing sys.modules helper.
    sys.modules["agent.video_gen_provider"].save_bytes_video = lambda raw, prefix="video", extension="mp4": Path("C:/tmp/fake.mp4")

    result = provider.generate("生成一个海边日落视频")

    assert result["success"] is True
    assert captured["payload"]["model"] == "doubao-seedance-1.5-pro"
    assert captured["payload"]["content"] == [{"type": "text", "text": "生成一个海边日落视频"}]
    assert captured["payload"]["ratio"] == "16:9"
    assert result["model"] == "doubao-seedance-1.5-pro"
    assert result["task_id"] == "task-123"

