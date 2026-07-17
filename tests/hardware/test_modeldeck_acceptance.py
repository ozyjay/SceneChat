"""Opt-in acceptance checks for SceneChat's real ModelDeck integration.

These tests deliberately use SceneChat's prepared replay image and refuse to run
while the camera is active. They never log model-generated descriptions.
"""

import asyncio
import json
import math
import os
import statistics
import time

import httpx
import pytest

from scenechat.models import AppState, SceneAnalysis


SCENECHAT_URL = "http://127.0.0.1:3700"
REQUEST_TIMEOUT_SECONDS = 120.0
WARMUP_REQUESTS = 2
MEASURED_REQUESTS = 10
MAX_MEDIAN_LATENCY_MS = 8_000.0
MAX_P95_LATENCY_MS = 12_000.0
ENABLE_ENVIRONMENT_VARIABLE = "SCENECHAT_MODELDECK_ACCEPTANCE"

pytestmark = [
    pytest.mark.hardware,
    pytest.mark.skipif(
        os.getenv(ENABLE_ENVIRONMENT_VARIABLE) != "1",
        reason=f"set {ENABLE_ENVIRONMENT_VARIABLE}=1 to run the live ModelDeck checks",
    ),
]


def _percentile(values: list[float], percentile: float) -> float:
    """Return a nearest-rank percentile suitable for a small acceptance sample."""
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _assert_safe_preconditions(state: AppState) -> None:
    assert state.provider == "modeldeck", "select the ModelDeck provider before testing"
    assert state.provider_available, "ModelDeck is marked unavailable"
    assert not state.camera_running, "stop the camera; acceptance uses the prepared image"
    assert not state.privacy_screen, "disable the privacy screen before testing"
    assert not state.auto_analyse, "disable automatic scene analysis before testing"
    assert state.internal_mode != "detector-only", "enable scene analysis before testing"


async def _assert_raster_prepared_frame(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/frame")
    assert response.status_code == 200
    media_type = response.headers.get("content-type", "").partition(";")[0]
    assert media_type in {"image/jpeg", "image/png"}, (
        "the prepared benchmark frame is not a supported raster image; restart SceneChat"
    )


async def _request_analysis(
    client: httpx.AsyncClient, question: str
) -> tuple[float, SceneAnalysis, bool]:
    started = time.perf_counter()
    response = await client.post("/api/analyse", json={"question": question})
    elapsed_ms = (time.perf_counter() - started) * 1_000
    assert response.status_code == 200, (
        f"SceneChat returned HTTP {response.status_code}; inspect private service logs for details"
    )
    payload = response.json()
    analysis = SceneAnalysis.model_validate(payload["analysis"])
    assert analysis.provider == "modeldeck"
    assert analysis.latency_ms is not None
    return elapsed_ms, analysis, bool(payload["applied"])


@pytest.mark.anyio
async def test_modeldeck_scene_analysis_latency_and_schema_acceptance(capsys):
    """Measure ten sequential production-route requests using a prepared image."""
    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(base_url=SCENECHAT_URL, timeout=timeout) as client:
        state_response = await client.get("/api/state")
        assert state_response.status_code == 200, "SceneChat is not running on port 3700"
        initial_state = AppState.model_validate(state_response.json())
        _assert_safe_preconditions(initial_state)
        await _assert_raster_prepared_frame(client)

        config_response = await client.get("/api/config")
        assert config_response.status_code == 200
        questions = config_response.json()["questions"]
        assert questions

        try:
            for index in range(WARMUP_REQUESTS):
                _, _, applied = await _request_analysis(
                    client, questions[index % len(questions)]
                )
                assert applied

            end_to_end_ms: list[float] = []
            gateway_ms: list[float] = []
            overhead_ms: list[float] = []
            prompt_tokens: list[int] = []
            completion_tokens: list[int] = []
            completion_token_limits: list[int] = []
            observed_completion_tokens_per_second: list[float] = []
            for index in range(MEASURED_REQUESTS):
                elapsed, analysis, applied = await _request_analysis(
                    client, questions[index % len(questions)]
                )
                assert applied
                assert analysis.prompt_tokens is not None
                assert analysis.completion_tokens is not None
                assert analysis.completion_token_limit is not None
                assert analysis.latency_ms > 0
                end_to_end_ms.append(elapsed)
                gateway_ms.append(analysis.latency_ms)
                overhead_ms.append(max(0.0, elapsed - analysis.latency_ms))
                prompt_tokens.append(analysis.prompt_tokens)
                completion_tokens.append(analysis.completion_tokens)
                completion_token_limits.append(analysis.completion_token_limit)
                observed_completion_tokens_per_second.append(
                    analysis.completion_tokens / (analysis.latency_ms / 1_000)
                )

                current = AppState.model_validate((await client.get("/api/state")).json())
                assert current.scene_analysis is not None
                assert current.last_model_latency_ms == analysis.latency_ms
        finally:
            await client.post("/api/analysis/clear")

    result = {
        "route": f"{SCENECHAT_URL}/api/analyse",
        "provider": "modeldeck",
        "model_alias": "scenechat-vision",
        "prepared_scenario": initial_state.replay_scenario,
        "warmup_requests": WARMUP_REQUESTS,
        "measured_requests": MEASURED_REQUESTS,
        "end_to_end_ms": {
            "mean": round(statistics.fmean(end_to_end_ms), 1),
            "median": round(statistics.median(end_to_end_ms), 1),
            "p95": round(_percentile(end_to_end_ms, 0.95), 1),
        },
        "modeldeck_round_trip_ms": {
            "mean": round(statistics.fmean(gateway_ms), 1),
            "median": round(statistics.median(gateway_ms), 1),
            "p95": round(_percentile(gateway_ms, 0.95), 1),
        },
        "scenechat_overhead_ms": {
            "mean": round(statistics.fmean(overhead_ms), 1),
            "median": round(statistics.median(overhead_ms), 1),
            "p95": round(_percentile(overhead_ms, 0.95), 1),
        },
        "tokens": {
            "prompt_median": statistics.median(prompt_tokens),
            "completion_median": statistics.median(completion_tokens),
            "completion_minimum": min(completion_tokens),
            "completion_maximum": max(completion_tokens),
            "configured_completion_limit": completion_token_limits[0],
            "completion_limit_hits": sum(
                tokens >= limit
                for tokens, limit in zip(
                    completion_tokens, completion_token_limits, strict=True
                )
            ),
            "observed_completion_tokens_per_second_median": round(
                statistics.median(observed_completion_tokens_per_second), 2
            ),
        },
    }
    with capsys.disabled():
        print("\nSceneChat ModelDeck acceptance result:")
        print(json.dumps(result, indent=2))

    assert statistics.median(end_to_end_ms) <= MAX_MEDIAN_LATENCY_MS
    assert _percentile(end_to_end_ms, 0.95) <= MAX_P95_LATENCY_MS


@pytest.mark.anyio
async def test_reset_rejects_a_real_modeldeck_result_made_stale():
    """Reset during real inference and confirm its eventual result is not displayed."""
    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(base_url=SCENECHAT_URL, timeout=timeout) as client:
        initial = AppState.model_validate((await client.get("/api/state")).json())
        if not initial.provider_available:
            pytest.skip("the primary ModelDeck route check marked the provider unavailable")
        _assert_safe_preconditions(initial)
        await _assert_raster_prepared_frame(client)
        await client.post("/api/analysis/clear")

        request_task = asyncio.create_task(
            client.post("/api/analyse", json={"question": "Describe the scene."})
        )
        observed_in_progress = False
        try:
            for _ in range(50):
                state = AppState.model_validate((await client.get("/api/state")).json())
                if state.analysis_in_progress:
                    observed_in_progress = True
                    break
                if request_task.done():
                    break
                await asyncio.sleep(0.1)

            if not observed_in_progress:
                pytest.skip("the model completed before the active request could be reset")

            reset_response = await client.post("/api/reset")
            assert reset_response.status_code == 200
            response = await request_task
            assert response.status_code == 200
            assert response.json()["applied"] is False

            final = AppState.model_validate((await client.get("/api/state")).json())
            assert final.scene_analysis is None
            assert final.analysis_in_progress is False
            assert final.last_model_latency_ms is None
        finally:
            if not request_task.done():
                request_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await request_task
            await client.post("/api/analysis/clear")
