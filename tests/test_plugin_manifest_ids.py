from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PLUGIN_METADATA = {
    ROOT / "plugins" / "model-providers" / "volcengine" / "plugin.yaml": {
        "id": "model-provider-volcengine",
        "name": "Volcengine Model Provider",
        "key": "model-providers/volcengine",
    },
    ROOT / "plugins" / "web" / "volcengine" / "plugin.yaml": {
        "id": "web-search-volcengine",
        "name": "Volcengine Web Search Provider",
        "key": "web/volcengine",
    },
    ROOT / "plugins" / "image_gen" / "volcengine" / "plugin.yaml": {
        "id": "image-generation-volcengine",
        "name": "Volcengine Image Generation Provider",
        "key": "image_gen/volcengine",
    },
    ROOT / "plugins" / "video_gen" / "volcengine" / "plugin.yaml": {
        "id": "video-generation-volcengine",
        "name": "Volcengine Video Generation Provider",
        "key": "video_gen/volcengine",
    },
}


def read_manifest_scalar(path: Path, field: str) -> str:
    prefix = f"{field}:"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip().strip('"')
    raise AssertionError(f"manifest has no {field} field: {path}")


def plugin_key_for(path: Path) -> str:
    plugin_dir = path.parent
    return plugin_dir.relative_to(ROOT / "plugins").as_posix()


@pytest.mark.parametrize(("manifest_path", "expected"), EXPECTED_PLUGIN_METADATA.items())
def test_volcengine_plugin_manifest_has_stable_id_and_human_name(manifest_path, expected):
    assert manifest_path.is_file()

    assert read_manifest_scalar(manifest_path, "id") == expected["id"]
    assert read_manifest_scalar(manifest_path, "name") == expected["name"]
    assert plugin_key_for(manifest_path) == expected["key"]


def test_volcengine_plugin_manifest_ids_are_unique_machine_identifiers():
    ids = [read_manifest_scalar(path, "id") for path in EXPECTED_PLUGIN_METADATA]

    assert len(ids) == len(set(ids))
    assert all(id_ == id_.lower() for id_ in ids)
    assert all(" " not in id_ for id_ in ids)
    assert all(id_.endswith("-volcengine") for id_ in ids)


def test_volcengine_plugin_manifest_names_are_unique_and_readable():
    names = [read_manifest_scalar(path, "name") for path in EXPECTED_PLUGIN_METADATA]

    assert len(names) == len(set(names))
    assert all("-" not in name for name in names)
    assert all(name.startswith("Volcengine ") for name in names)


def test_volcengine_plugin_keys_are_unique():
    keys = [plugin_key_for(path) for path in EXPECTED_PLUGIN_METADATA]

    assert len(keys) == len(set(keys))
