"""ModelDeck gateway adapter for dedicated SceneChat vision requests."""

import base64
import time

import httpx

from scenechat.config import MODELDECK_REQUIRED_CAPABILITIES
from scenechat.models import SceneAnalysis
from scenechat.vision.base import (
    ProviderStatus,
    VisionProviderError,
    build_prompt,
    parse_scene_analysis,
)


class ModelDeckProvider:
    """Send scene analysis only through the configured ModelDeck gateway."""

    name = "modeldeck"

    def __init__(
        self,
        gateway_url: str,
        model: str,
        timeout: float,
        max_tokens: int = 512,
        health_timeout: float = 2.0,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
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
        if image.startswith(b"\x89PNG\r\n\x1a\n"):
            media_type = "image/png"
        elif image.startswith(b"\xff\xd8\xff"):
            media_type = "image/jpeg"
        else:
            raise VisionProviderError(
                "The selected frame is not a supported JPEG or PNG image.",
                code="unsupported_image",
            )
        encoded = base64.b64encode(image).decode("ascii")
        started = time.perf_counter()
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{encoded}"},
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
        try:
            response = await self._client.post(
                f"{self.gateway_url}/v1/vision/analyse", json=payload
            )
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
            return analysis
        except VisionProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise VisionProviderError(
                "Scene analysis timed out.",
                code="timeout",
                staff_message="The ModelDeck scene-analysis request timed out.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise VisionProviderError(
                "Scene analysis is temporarily unavailable.",
                code="gateway_error",
                staff_message="The ModelDeck gateway rejected the scene-analysis request.",
            ) from exc
        except httpx.HTTPError as exc:
            raise VisionProviderError(
                "Scene analysis is temporarily unavailable.",
                code="gateway_unavailable",
                staff_message="The ModelDeck gateway is unavailable on port 8600.",
            ) from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise VisionProviderError(
                "The model returned an invalid structured response.",
                code="invalid_response",
                staff_message="ModelDeck returned an invalid scene-analysis response.",
            ) from exc


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None
