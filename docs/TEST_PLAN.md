# Test plan

## Automated offline tests

The suite covers port ownership, ModelDeck gateway URL restrictions, the dedicated route, alias and non-streaming JPEG/PNG request, `/v1/routes` presence/readiness and contract identity, required capabilities, malformed discovery and analysis responses, unavailable-route and gateway failure handling, explicit provider/fallback selection, configuration safety, detector box validation, prompt safeguards, automatic curated-question pools, interval limits and camera-off suspension, strict structured model parsing, unsafe-output rejection, replay manifest safety, state reset, stale success and failure rejection, privacy invalidation, previous-result retention, mock analysis, API health/state/reset/privacy, provider failure degradation and readiness recovery, camera read and detector failure cleanup, and curated-question rejection. Detector prompt tests cover safe non-allowlisted learning, every conservative rejection category, generic `person`, duplicate handling, non-disclosure of rejected labels, protected baseline capacity, oldest-learned eviction, manual and clear/reset restoration, stale/reset/privacy rejection, detector switching, and equivalent YOLOE/YOLO-World behaviour. It must not require a camera, large model, model download, ModelDeck, or network.

Run `& .venv/bin/python -m pytest -m "not hardware"`.

## Optional hardware tests

The current Qwen3.5-focused scope runs these checks with `DETECTOR_BACKEND=none`. Detector-candidate benchmarking is deferred and is required only before live object detection is re-enabled.

1. Before re-enabling live detection, benchmark at least two locally approved detector weights on the same 300+ frame booth video.
2. Run empty room, one person, several people, clutter, partial occlusion, reflections, poor light, and backlight cases.
3. Disconnect and reconnect the camera; confirm replay remains usable and memory remains bounded.
4. Begin hardware acceptance with one request using the committed fixed raster image. Confirm the currently published `scenechat-vision` route, `scene-analysis-v1` contract, capabilities, strict response schema and disabled cloud fallback before any camera use. If that passes, perform only a short attended camera check while monitoring memory and temperature. Do not start unattended camera inference or sustained benchmarking. Longer latency or stability runs require a separate explicit decision and the current ModelDeck configuration fingerprint; do not assume a historical Routing Profile revision remains active.
5. Through ModelDeck management, stop the prepared Worker during or before a request; confirm the structured unavailable route causes no UI freeze, retains the valid description, leaves `modeldeck` selected, provides sanitised Worker guidance, and degrades to camera/detector-only mode. SceneChat must not perform the stop.
6. Trigger reset during a slow model response; confirm the stale response never appears.
7. Repeatedly activate privacy, including during inference; confirm the browser and `/api/frame` hide the image immediately and the in-flight result is not applied.
8. Attempt a non-curated and sensitive question through the API; confirm rejection.
9. Run camera for 60 minutes, then camera plus the ModelDeck-served model for two hours while observing process/GPU/system memory.
10. Verify SceneChat never binds `3600`, `8600`, or any Worker port, and sends only gateway requests to `8600`. Confirm it has no Worker credential and never calls management or lifecycle endpoints.
11. Cold reboot and follow only `OPEN_DAY_RUNBOOK.md` with an operator who did not build the project.

## Acceptance record

Record dates, software/model hashes, operators, mean/p95 metrics, maximum memory, and pass/fail evidence in `MODEL_COMPATIBILITY.md`. Hardware-dependent items are not passed merely because the offline suite passes.
