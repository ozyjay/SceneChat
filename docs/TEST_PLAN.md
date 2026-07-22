# Test plan

## Automated offline tests

The suite covers port ownership, ModelDeck gateway URL restrictions, the dedicated route, alias and non-streaming JPEG/PNG request, published-route readiness, required capabilities, unavailable-route handling, explicit provider/fallback selection, configuration safety, detector box validation, prompt safeguards, active-prompt preservation, automatic curated-question pools and interval limits, strict structured model parsing, unsafe-output rejection, replay manifest safety, state reset, stale success and failure rejection, privacy invalidation, previous-result retention, mock analysis, API health/state/reset/privacy, provider failure degradation, camera read and detector failure cleanup, and curated-question rejection. It must not require a camera, large model, model download, ModelDeck, or network.

Run `& .venv/bin/python -m pytest -m "not hardware"`.

## Optional hardware tests

The current Qwen3.5-focused scope runs these checks with `DETECTOR_BACKEND=none`. Detector-candidate benchmarking is deferred and is required only before live object detection is re-enabled.

1. Before re-enabling live detection, benchmark at least two locally approved detector weights on the same 300+ frame booth video.
2. Run empty room, one person, several people, clutter, partial occlusion, reflections, poor light, and backlight cases.
3. Disconnect and reconnect the camera; confirm replay remains usable and memory remains bounded.
4. Send ten approved image requests through the ModelDeck gateway; record median/p95 latency, prompt and completion tokens, completion-limit hits, observed token throughput, and failure count. With the prepared Worker ready and SceneChat running, stop the camera, disable automatic analysis, select `modeldeck`, run `pwsh -NoProfile -File scripts/check_modeldeck.ps1`, then run `pwsh -NoProfile -File benchmarks/run.ps1`. The test verifies the alias, capabilities and disabled cloud fallback, uses only the prepared raster replay image, performs two warm-ups followed by ten measured requests, reports gateway and end-to-end latency without printing descriptions, and fails above an 8-second median or 12-second p95.
5. Through ModelDeck management, stop the prepared Worker during or before a request; confirm the structured unavailable route causes no UI freeze, retains the valid description, leaves `modeldeck` selected, provides sanitised Worker guidance, and degrades to camera/detector-only mode. SceneChat must not perform the stop.
6. Trigger reset during a slow model response; confirm the stale response never appears.
7. Repeatedly activate privacy, including during inference; confirm the browser and `/api/frame` hide the image immediately and the in-flight result is not applied.
8. Attempt a non-curated and sensitive question through the API; confirm rejection.
9. Run camera for 60 minutes, then camera plus the ModelDeck-served model for two hours while observing process/GPU/system memory.
10. Verify SceneChat never binds `3600`, `8600`, or any Worker port, and sends only gateway requests to `8600`. Confirm it has no Worker credential and never calls management or lifecycle endpoints.
11. Cold reboot and follow only `OPEN_DAY_RUNBOOK.md` with an operator who did not build the project.

## Acceptance record

Record dates, software/model hashes, operators, mean/p95 metrics, maximum memory, and pass/fail evidence in `MODEL_COMPATIBILITY.md`. Hardware-dependent items are not passed merely because the offline suite passes.
