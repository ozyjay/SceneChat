"""Gemma 4 adapter for a local vLLM OpenAI-compatible endpoint."""

import base64
import time

import httpx

from scenechat.models import SceneAnalysis
from scenechat.vision.base import VisionProviderError, build_prompt, parse_scene_analysis


class VllmGemmaProvider:
    name = "vllm"

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            response = await self._client.get(f"{self.base_url}/models")
            return response.is_success
        except httpx.HTTPError:
            return False

    async def analyse_scene(self, image: bytes, question: str) -> SceneAnalysis:
        encoded = base64.b64encode(image).decode("ascii")
        media_type = "image/png" if image.startswith(b"\x89PNG") else "image/jpeg"
        if image.lstrip().startswith(b"<svg"):
            media_type = "image/svg+xml"
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
            "max_tokens": 700,
            "response_format": {"type": "json_object"},
        }
        try:
            response = await self._client.post(
                f"{self.base_url}/chat/completions", json=payload
            )
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]
            analysis = parse_scene_analysis(raw, self.name)
            analysis.latency_ms = round((time.perf_counter() - started) * 1000, 1)
            return analysis
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise VisionProviderError("The local vision model is unavailable.") from exc
