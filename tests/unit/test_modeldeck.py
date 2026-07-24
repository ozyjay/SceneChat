import base64
import json
import logging

import cv2
import httpx
import numpy as np
import pytest

from scenechat.vision.base import VisionProviderError
from scenechat.vision.modeldeck import (
    ANALYSIS_JPEG_QUALITY,
    ModelDeckProvider,
    analysis_dimensions,
    prepare_analysis_image,
)


def encoded_image(width: int, height: int, extension: str = ".jpg") -> bytes:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :, 0] = np.arange(width, dtype=np.uint16) % 256
    image[:, :, 1] = np.arange(height, dtype=np.uint16)[:, None] % 256
    image[:, :, 2] = 127
    parameters = (
        [cv2.IMWRITE_JPEG_QUALITY, ANALYSIS_JPEG_QUALITY]
        if extension == ".jpg"
        else []
    )
    success, encoded = cv2.imencode(extension, image, parameters)
    assert success
    return encoded.tobytes()


def request_image(request: httpx.Request) -> bytes:
    payload = json.loads(request.content)
    data_url = payload["messages"][0]["content"][0]["image_url"]["url"]
    prefix, encoded = data_url.split(",", 1)
    assert prefix in {"data:image/jpeg;base64", "data:image/png;base64"}
    return base64.b64decode(encoded)


def request_media_type(request: httpx.Request) -> str:
    payload = json.loads(request.content)
    data_url = payload["messages"][0]["content"][0]["image_url"]["url"]
    return data_url.partition(";")[0].removeprefix("data:")


def image_dimensions(image: bytes) -> tuple[int, int]:
    decoded = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    height, width = decoded.shape[:2]
    return width, height


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
        result = await provider.analyse_scene(
            encoded_image(320, 240), "Describe the scene."
        )
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
    assert "max_soft_tokens" not in json.dumps(vision_payload)
    assert "image_token_budget" not in json.dumps(vision_payload)
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
@pytest.mark.parametrize("extension", [".jpg", ".png"])
async def test_modeldeck_accepts_supported_jpeg_and_png_inputs(extension):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=response_payload())

    provider = ModelDeckProvider(
        "http://127.0.0.1:8600",
        "scenechat-vision",
        2,
        transport=httpx.MockTransport(handle),
    )
    source = encoded_image(400, 300, extension)
    try:
        result = await provider.analyse_scene(source, "Describe the scene.")
    finally:
        await provider.close()

    assert result.summary == "A prepared scene is visible."
    assert image_dimensions(request_image(requests[0])) == (400, 300)
    assert request_image(requests[0]) == source
    assert request_media_type(requests[0]) == (
        "image/png" if extension == ".png" else "image/jpeg"
    )


@pytest.mark.anyio
async def test_modeldeck_rejects_unknown_and_malformed_image_bytes():
    provider = ModelDeckProvider(
        "http://127.0.0.1:8600",
        "scenechat-vision",
        2,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=response_payload())
        ),
    )
    try:
        with pytest.raises(VisionProviderError, match="JPEG or PNG"):
            await provider.analyse_scene(b"<svg/>", "Describe the scene.")
        with pytest.raises(VisionProviderError, match="could not be decoded"):
            await provider.analyse_scene(b"\xff\xd8\xffmalformed", "Describe the scene.")
    finally:
        await provider.close()


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
            await provider.analyse_scene(encoded_image(320, 240), "Describe the scene.")
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
            await provider.analyse_scene(encoded_image(320, 240), "Describe the scene.")
    finally:
        await provider.close()


def test_prepare_analysis_image_fails_explicitly_when_reencoding_fails(monkeypatch):
    source = encoded_image(1280, 720)
    monkeypatch.setattr(cv2, "imencode", lambda *_args, **_kwargs: (False, None))

    with pytest.raises(VisionProviderError, match="could not be encoded as JPEG"):
        prepare_analysis_image(source, max_edge=512)


@pytest.mark.parametrize(
    ("source", "max_edge", "expected"),
    [
        ((1280, 720), 0, (1280, 720)),
        ((1280, 720), 512, (512, 288)),
        ((720, 1280), 512, (288, 512)),
        ((500, 300), 512, (500, 300)),
    ],
)
def test_analysis_dimensions_preserve_aspect_ratio(source, max_edge, expected):
    assert analysis_dimensions(*source, max_edge=max_edge) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [((1280, 720), (512, 288)), ((720, 1280), (288, 512))],
)
def test_prepare_analysis_image_downscales_landscape_and_portrait(source, expected):
    prepared = prepare_analysis_image(encoded_image(*source), max_edge=512)

    assert (prepared.original_width, prepared.original_height) == source
    assert (prepared.transmitted_width, prepared.transmitted_height) == expected
    assert image_dimensions(prepared.encoded) == expected
    assert prepared.media_type == "image/jpeg"


def test_prepare_analysis_image_does_not_upscale_smaller_image():
    source = encoded_image(320, 180)
    prepared = prepare_analysis_image(source, max_edge=512)

    assert (prepared.original_width, prepared.original_height) == (320, 180)
    assert (prepared.transmitted_width, prepared.transmitted_height) == (320, 180)
    assert prepared.encoded == source
    assert prepared.media_type == "image/jpeg"


def test_prepare_analysis_image_keeps_full_dimensions_when_resizing_is_disabled():
    source = encoded_image(1280, 720, ".png")
    prepared = prepare_analysis_image(source, max_edge=0)

    assert (prepared.original_width, prepared.original_height) == (1280, 720)
    assert (prepared.transmitted_width, prepared.transmitted_height) == (1280, 720)
    assert prepared.encoded == source
    assert prepared.media_type == "image/png"
    assert prepared.resize_ms == 0.0


@pytest.mark.anyio
async def test_modeldeck_request_contains_resized_copy_and_preserves_original():
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=response_payload())

    original = encoded_image(1280, 720)
    original_for_other_components = original
    provider = ModelDeckProvider(
        "http://127.0.0.1:8600",
        "scenechat-vision",
        2,
        analysis_max_edge=512,
        transport=httpx.MockTransport(handle),
    )
    try:
        await provider.analyse_scene(original, "Describe the scene.")
    finally:
        await provider.close()

    transmitted = request_image(requests[0])
    assert image_dimensions(transmitted) == (512, 288)
    assert transmitted != original
    assert original_for_other_components is original
    assert image_dimensions(original_for_other_components) == (1280, 720)


@pytest.mark.anyio
async def test_modeldeck_logs_privacy_safe_success_diagnostics(caplog):
    provider = ModelDeckProvider(
        "http://127.0.0.1:8600",
        "scenechat-vision",
        2,
        analysis_max_edge=512,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=response_payload())
        ),
    )
    with caplog.at_level(logging.INFO, logger="scenechat.vision.modeldeck"):
        try:
            await provider.analyse_scene(
                encoded_image(1280, 720), "private prompt marker"
            )
        finally:
            await provider.close()

    assert "outcome=success" in caplog.text
    assert "original_width=1280 original_height=720 original_bytes=" in caplog.text
    assert "transmitted_width=512 transmitted_height=288 transmitted_bytes=" in caplog.text
    assert "resize_ms=" in caplog.text
    assert "provider_latency_ms=" in caplog.text
    assert "http_status=200" in caplog.text
    assert "private prompt marker" not in caplog.text
    assert "A prepared scene is visible" not in caplog.text
    assert "base64" not in caplog.text


@pytest.mark.anyio
async def test_modeldeck_logs_privacy_safe_timeout_diagnostics(caplog):
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = ModelDeckProvider(
        "http://127.0.0.1:8600",
        "scenechat-vision",
        2,
        analysis_max_edge=512,
        transport=httpx.MockTransport(timeout),
    )
    with caplog.at_level(logging.INFO, logger="scenechat.vision.modeldeck"):
        try:
            with pytest.raises(VisionProviderError, match="timed out"):
                await provider.analyse_scene(
                    encoded_image(720, 1280), "private prompt marker"
                )
        finally:
            await provider.close()

    assert "outcome=timeout" in caplog.text
    assert "original_width=720 original_height=1280 original_bytes=" in caplog.text
    assert "transmitted_width=288 transmitted_height=512 transmitted_bytes=" in caplog.text
    assert "resize_ms=" in caplog.text
    assert "provider_latency_ms=" in caplog.text
    assert "http_status=none" in caplog.text
    assert "private prompt marker" not in caplog.text
