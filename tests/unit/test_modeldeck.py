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
            json={
                "choices": [{"message": {"content": json.dumps(payload)}}],
                "usage": {"prompt_tokens": 420, "completion_tokens": 125},
            },
        )

    provider = ModelDeckProvider(
        "http://127.0.0.1:8600",
        "",
        "approved-model",
        2,
        350,
        transport=httpx.MockTransport(handle),
    )
    try:
        assert await provider.health() is True
        result = await provider.analyse_scene(b"jpeg", "Describe the scene.")
    finally:
        await provider.close()

    assert result.provider == "modeldeck"
    assert result.prompt_tokens == 420
    assert result.completion_tokens == 125
    assert result.completion_token_limit == 350
    assert [request.url.path for request in requests] == [
        "/v1/models",
        "/v1/vision/analyse",
    ]
    assert {request.url.port for request in requests} == {8600}
    vision_payload = json.loads(requests[1].content)
    assert vision_payload["model"] == "approved-model"
    assert vision_payload["max_tokens"] == 350
    assert vision_payload["messages"][0]["content"][0]["type"] == "image_url"
    assert vision_payload["messages"][0]["content"][1]["type"] == "text"
    assert vision_payload["response_format"] == {"type": "json_object"}


@pytest.mark.anyio
async def test_modeldeck_uses_only_envelope_token_metrics():
    model_payload = {
        "summary": "A prepared scene is visible.",
        "objects": [],
        "relationships": [],
        "uncertainties": [],
        "safety_notes": [],
        "prompt_tokens": 999_999,
        "completion_tokens": 999_999,
    }

    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(model_payload)}}]},
        )

    provider = ModelDeckProvider(
        "http://127.0.0.1:8600",
        "",
        "approved-model",
        2,
        350,
        transport=httpx.MockTransport(handle),
    )
    try:
        result = await provider.analyse_scene(b"jpeg", "Describe the scene.")
    finally:
        await provider.close()

    assert result.prompt_tokens is None
    assert result.completion_tokens is None
    assert result.completion_token_limit == 350
