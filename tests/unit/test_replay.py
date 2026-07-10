import json

import pytest

from scenechat.replay import ReplayRegistry


def test_committed_replay_manifest_loads():
    registry = ReplayRegistry()
    scenario = registry.get("demo_booth")
    assert len(scenario.detections) >= 1
    assert registry.image_path(scenario.id).is_file()


def test_replay_manifest_rejects_path_traversal(tmp_path):
    manifest = {
        "version": 1,
        "scenarios": [
            {
                "id": "unsafe",
                "title": "Unsafe",
                "image": "../visitor.jpg",
                "detections": [],
                "responses": {},
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="safe relative path"):
        ReplayRegistry(path)

