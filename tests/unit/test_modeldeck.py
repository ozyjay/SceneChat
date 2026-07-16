import json

import httpx
import pytest

from scenechat.vision.modeldeck import ModelDeckProvider


@pytest.mark.anyio
async def test_modeldeck_provider_uses_only_gateway_api_paths():
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": []})
        payload = {
            "summary": "A prepared scene is visible.",
            "objects": [],
            "relationships": [],
            "uncertainties": [],
            "safety_notes": [],
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    provider = ModelDeckProvider(
        "http://127.0.0.1:8600",
        "",
        "approved-model",
        2,
        transport=httpx.MockTransport(handle),
    )
    try:
        assert await provider.health() is True
        result = await provider.analyse_scene(b"jpeg", "Describe the scene.")
    finally:
        await provider.close()

    assert result.provider == "modeldeck"
    assert [request.url.path for request in requests] == [
        "/v1/models",
        "/v1/chat/completions",
    ]
    assert {request.url.port for request in requests} == {8600}
