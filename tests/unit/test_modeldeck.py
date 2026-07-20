import json

import httpx
import pytest

from scenechat.vision.base import VisionProviderError
from scenechat.vision.modeldeck import ModelDeckProvider


def response_payload():
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": "A prepared scene is visible.",
                            "objects": [],
                            "relationships": [],
                            "uncertainties": [],
                            "safety_notes": [],
                        }
                    )
                }
            }
        ]
    }


@pytest.mark.anyio
async def test_modeldeck_provider_uses_only_gateway_api_paths():
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(
                200,
                json={"data": [{"id": "scenechat-vision", "ready": True}]},
            )
        if request.url.path == "/v1/capabilities":
            return httpx.Response(
                200,
                json={
                    "scenechat-vision": {
                        "image_input": True,
                        "structured_output": True,
                    }
                },
            )
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
        "scenechat-vision",
        2,
        512,
        transport=httpx.MockTransport(handle),
    )
    try:
        assert (await provider.health()).available is True
        result = await provider.analyse_scene(b"\xff\xd8\xffjpeg", "Describe the scene.")
    finally:
        await provider.close()

    assert result.provider == "modeldeck"
    assert result.prompt_tokens == 420
    assert result.completion_tokens == 125
    assert result.completion_token_limit == 512
    assert [request.url.path for request in requests] == [
        "/v1/models",
        "/v1/capabilities",
        "/v1/vision/analyse",
    ]
    assert {request.url.port for request in requests} == {8600}
    vision_payload = json.loads(requests[2].content)
    assert vision_payload["model"] == "scenechat-vision"
    assert vision_payload["max_tokens"] == 512
    assert vision_payload["messages"][0]["content"][0]["type"] == "image_url"
    assert vision_payload["messages"][0]["content"][1]["type"] == "text"
    assert vision_payload["response_format"] == {"type": "json_object"}
    assert vision_payload["stream"] is False
    assert "authorization" not in requests[2].headers


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("models", "capabilities", "code"),
    [
        ({"data": []}, {}, "route_not_published"),
        (
            {"data": [{"id": "scenechat-vision", "ready": False}]},
            {"scenechat-vision": {"image_input": True, "structured_output": True}},
            "worker_not_ready",
        ),
        (
            {"data": [{"id": "scenechat-vision", "ready": True}]},
            {"scenechat-vision": {"image_input": True, "structured_output": False}},
            "capability_mismatch",
        ),
    ],
)
async def test_modeldeck_health_requires_published_ready_capable_route(
    models, capabilities, code
):
    def handle(request: httpx.Request) -> httpx.Response:
        payload = models if request.url.path == "/v1/models" else capabilities
        return httpx.Response(200, json=payload)

    provider = ModelDeckProvider(
        "http://127.0.0.1:8600",
        "scenechat-vision",
        2,
        transport=httpx.MockTransport(handle),
    )
    try:
        status = await provider.health()
    finally:
        await provider.close()

    assert status.available is False
    assert status.code == code


@pytest.mark.anyio
async def test_modeldeck_accepts_png_and_rejects_unknown_image_bytes():
    provider = ModelDeckProvider(
        "http://127.0.0.1:8600",
        "scenechat-vision",
        2,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=response_payload())
        ),
    )
    try:
        result = await provider.analyse_scene(
            b"\x89PNG\r\n\x1a\nprepared", "Describe the scene."
        )
        with pytest.raises(VisionProviderError, match="JPEG or PNG"):
            await provider.analyse_scene(b"<svg/>", "Describe the scene.")
    finally:
        await provider.close()

    assert result.summary == "A prepared scene is visible."


@pytest.mark.anyio
async def test_modeldeck_unavailable_route_has_worker_guidance():
    provider = ModelDeckProvider(
        "http://127.0.0.1:8600",
        "scenechat-vision",
        2,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                503,
                json={"error": {"code": "local_route_unavailable"}},
            )
        ),
    )
    try:
        with pytest.raises(VisionProviderError) as error:
            await provider.analyse_scene(b"\xff\xd8\xffjpeg", "Describe the scene.")
    finally:
        await provider.close()

    assert error.value.code == "worker_not_ready"
    assert "Start it in ModelDeck" in error.value.staff_message


@pytest.mark.anyio
async def test_modeldeck_rejects_model_generated_operational_metrics():
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
        "scenechat-vision",
        2,
        512,
        transport=httpx.MockTransport(handle),
    )
    try:
        with pytest.raises(VisionProviderError, match="invalid structured response"):
            await provider.analyse_scene(b"\xff\xd8\xffjpeg", "Describe the scene.")
    finally:
        await provider.close()
