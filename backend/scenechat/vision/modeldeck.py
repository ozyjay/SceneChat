"""ModelDeck gateway adapter for dedicated SceneChat vision requests."""

import base64
import logging
import time
from dataclasses import dataclass

import cv2
import httpx
import numpy as np

from scenechat.config import MODELDECK_REQUIRED_CAPABILITIES
from scenechat.models import SceneAnalysis
from scenechat.vision.base import (
    ProviderStatus,
    VisionProviderError,
    build_prompt,
    parse_scene_analysis,
)


ANALYSIS_JPEG_QUALITY = 82
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedAnalysisImage:
    encoded: bytes
    media_type: str
    original_width: int
    original_height: int
    transmitted_width: int
    transmitted_height: int
    resize_ms: float


def analysis_dimensions(width: int, height: int, max_edge: int) -> tuple[int, int]:
    """Return aspect-ratio-preserving dimensions bounded by ``max_edge``."""
    if max_edge == 0 or (width <= max_edge and height <= max_edge):
        return width, height
    if width >= height:
        return max_edge, max(1, round(height * max_edge / width))
    return max(1, round(width * max_edge / height)), max_edge


def prepare_analysis_image(image: bytes, max_edge: int) -> PreparedAnalysisImage:
    """Validate and optionally downscale an in-memory JPEG or PNG request copy."""
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        source_media_type = "image/png"
    elif image.startswith(b"\xff\xd8\xff"):
        source_media_type = "image/jpeg"
    else:
        raise VisionProviderError(
            "The selected frame is not a supported JPEG or PNG image.",
            code="unsupported_image",
        )

    try:
        decoded = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error as exc:
        raise VisionProviderError(
            "The selected JPEG or PNG image could not be decoded.",
            code="invalid_image",
        ) from exc
    if decoded is None:
        raise VisionProviderError(
            "The selected JPEG or PNG image could not be decoded.",
            code="invalid_image",
        )

    original_height, original_width = decoded.shape[:2]
    transmitted_width, transmitted_height = analysis_dimensions(
        original_width, original_height, max_edge
    )
    resize_ms = 0.0
    if (transmitted_width, transmitted_height) == (original_width, original_height):
        encoded = image
        media_type = source_media_type
    else:
        try:
            resize_started = time.perf_counter()
            decoded = cv2.resize(
                decoded,
                (transmitted_width, transmitted_height),
                interpolation=cv2.INTER_AREA,
            )
            resize_ms = round((time.perf_counter() - resize_started) * 1000, 1)
            encoded_ok, resized_encoded = cv2.imencode(
                ".jpg", decoded, [cv2.IMWRITE_JPEG_QUALITY, ANALYSIS_JPEG_QUALITY]
            )
        except cv2.error as exc:
            raise VisionProviderError(
                "The analysis image could not be encoded as JPEG.",
                code="image_encode_failed",
            ) from exc
        if not encoded_ok:
            raise VisionProviderError(
                "The analysis image could not be encoded as JPEG.",
                code="image_encode_failed",
            )
        encoded = resized_encoded.tobytes()
        media_type = "image/jpeg"

    return PreparedAnalysisImage(
        encoded=encoded,
        media_type=media_type,
        original_width=original_width,
        original_height=original_height,
        transmitted_width=transmitted_width,
        transmitted_height=transmitted_height,
        resize_ms=resize_ms,
    )


class ModelDeckProvider:
    """Send scene analysis only through the configured ModelDeck gateway."""

    name = "modeldeck"

    def __init__(
        self,
        gateway_url: str,
        model: str,
        timeout: float,
        max_tokens: int = 1024,
        health_timeout: float = 2.0,
        *,
        analysis_max_edge: int = 0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.analysis_max_edge = analysis_max_edge
        self.health_timeout = health_timeout
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 2.0)), transport=transport
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> ProviderStatus:
        try:
            models_response = await self._client.get(
                f"{self.gateway_url}/v1/models", timeout=self.health_timeout
            )
            models_response.raise_for_status()
            models_payload = models_response.json()
            models = models_payload.get("data") if isinstance(models_payload, dict) else None
            if not isinstance(models, list):
                return ProviderStatus(
                    False,
                    "invalid_health_response",
                    "ModelDeck returned an invalid route status.",
                )
            route = next(
                (
                    item
                    for item in models
                    if isinstance(item, dict) and item.get("id") == self.model
                ),
                None,
            )
            if route is None:
                return ProviderStatus(
                    False,
                    "route_not_published",
                    f"ModelDeck has not published the {self.model} route.",
                )

            capabilities_response = await self._client.get(
                f"{self.gateway_url}/v1/capabilities", timeout=self.health_timeout
            )
            capabilities_response.raise_for_status()
            capabilities_payload = capabilities_response.json()
            capabilities = (
                capabilities_payload.get(self.model)
                if isinstance(capabilities_payload, dict)
                else None
            )
            missing = [
                capability
                for capability in MODELDECK_REQUIRED_CAPABILITIES
                if not isinstance(capabilities, dict)
                or capabilities.get(capability) is not True
            ]
            if missing:
                return ProviderStatus(
                    False,
                    "capability_mismatch",
                    "ModelDeck route is missing required capabilities: "
                    + ", ".join(missing)
                    + ".",
                )
            if route.get("ready") is not True:
                return ProviderStatus(
                    False,
                    "worker_not_ready",
                    "Start the SceneChat Worker in ModelDeck and wait for ready.",
                )
            return ProviderStatus(
                True,
                "available",
                (
                    "ModelDeck scenechat-vision is ready with image_input "
                    "and structured_output."
                ),
            )
        except (httpx.HTTPError, ValueError):
            return ProviderStatus(
                False,
                "gateway_unavailable",
                "The ModelDeck gateway is unavailable on port 8600.",
            )

    async def analyse_scene(self, image: bytes, question: str) -> SceneAnalysis:
        started = time.perf_counter()
        prepared = prepare_analysis_image(image, self.analysis_max_edge)
        encoded = base64.b64encode(prepared.encoded).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{prepared.media_type};base64,{encoded}"
                            },
                        },
                        {"type": "text", "text": build_prompt(question)},
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        outcome = "cancelled"
        http_status: int | None = None
        try:
            response = await self._client.post(
                f"{self.gateway_url}/v1/vision/analyse", json=payload
            )
            http_status = response.status_code
            if response.status_code == 503:
                try:
                    error_payload = response.json()
                except ValueError:
                    error_payload = {}
                error = error_payload.get("error") if isinstance(error_payload, dict) else None
                if isinstance(error, dict) and error.get("code") == "local_route_unavailable":
                    raise VisionProviderError(
                        "Scene analysis is temporarily unavailable.",
                        code="worker_not_ready",
                        staff_message=(
                            "The scenechat-vision route has no ready Worker. "
                            "Start it in ModelDeck and wait for ready."
                        ),
                    )
            response.raise_for_status()
            response_payload = response.json()
            if not isinstance(response_payload, dict):
                raise TypeError("response was not an object")
            raw = response_payload["choices"][0]["message"]["content"]
            if not isinstance(raw, str):
                raise TypeError("response content was not text")
            analysis = parse_scene_analysis(raw, self.name)
            analysis.latency_ms = round((time.perf_counter() - started) * 1000, 1)
            # Operational metrics come only from ModelDeck's trusted response
            # envelope, never from model-generated JSON content.
            analysis.prompt_tokens = None
            analysis.completion_tokens = None
            usage = response_payload.get("usage")
            if isinstance(usage, dict):
                analysis.prompt_tokens = _non_negative_int(usage.get("prompt_tokens"))
                analysis.completion_tokens = _non_negative_int(
                    usage.get("completion_tokens")
                )
            analysis.completion_token_limit = self.max_tokens
            outcome = "success"
            return analysis
        except VisionProviderError:
            outcome = "provider_error"
            raise
        except httpx.TimeoutException as exc:
            outcome = "timeout"
            raise VisionProviderError(
                "Scene analysis timed out.",
                code="timeout",
                staff_message="The ModelDeck scene-analysis request timed out.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            outcome = "gateway_error"
            raise VisionProviderError(
                "Scene analysis is temporarily unavailable.",
                code="gateway_error",
                staff_message="The ModelDeck gateway rejected the scene-analysis request.",
            ) from exc
        except httpx.HTTPError as exc:
            outcome = "gateway_unavailable"
            raise VisionProviderError(
                "Scene analysis is temporarily unavailable.",
                code="gateway_unavailable",
                staff_message="The ModelDeck gateway is unavailable on port 8600.",
            ) from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            outcome = "invalid_response"
            raise VisionProviderError(
                "The model returned an invalid structured response.",
                code="invalid_response",
                staff_message="ModelDeck returned an invalid scene-analysis response.",
            ) from exc
        finally:
            logger.info(
                "ModelDeck scene analysis outcome=%s original_width=%d "
                "original_height=%d original_bytes=%d transmitted_width=%d "
                "transmitted_height=%d transmitted_bytes=%d resize_ms=%.1f "
                "provider_latency_ms=%.1f http_status=%s",
                outcome,
                prepared.original_width,
                prepared.original_height,
                len(image),
                prepared.transmitted_width,
                prepared.transmitted_height,
                len(prepared.encoded),
                prepared.resize_ms,
                (time.perf_counter() - started) * 1000,
                http_status if http_status is not None else "none",
            )


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None
