# Test plan

## Automated offline tests

The suite covers port ownership, ModelDeck gateway URL restrictions, the dedicated SceneChat vision route and alias, explicit provider/fallback selection, configuration safety, detector box validation, prompt safeguards, structured model parsing, replay manifest safety, state reset, stale response rejection, mock analysis, API health/state/reset/privacy, provider failure degradation, camera read and detector failure cleanup, and curated-question rejection. It must not require a camera, large model, model download, ModelDeck, or network.

Run `& .venv/bin/python -m pytest`.

## Optional hardware tests

The current Gemma-focused scope runs these checks with `DETECTOR_BACKEND=none`. Detector-candidate benchmarking is deferred and is required only before live object detection is re-enabled.

1. Before re-enabling live detection, benchmark at least two locally approved detector weights on the same 300+ frame booth video.
2. Run empty room, one person, several people, clutter, partial occlusion, reflections, poor light, and backlight cases.
3. Disconnect and reconnect the camera; confirm replay remains usable and memory remains bounded.
4. Send ten approved image requests through the ModelDeck gateway; record median/p95 latency, prompt and completion tokens, completion-limit hits, observed token throughput, and failure count; confirm every request targets port `8600`. With SceneChat and ModelDeck already running, stop the camera, disable automatic analysis, select the `modeldeck` provider, then run `& benchmarks/run.ps1`. The test uses only the prepared raster replay image, performs two warm-ups followed by ten measured requests, reports ModelDeck round-trip and SceneChat end-to-end latency without printing descriptions, and fails above an 8-second median or 12-second p95.
5. Make the ModelDeck gateway unavailable during a request; confirm no UI freeze, retained valid description, unchanged selected provider, and camera/detector-only degradation.
6. Trigger reset during a slow model response; confirm the stale response never appears.
7. Repeatedly activate privacy; confirm the browser and `/api/frame` hide the image immediately.
8. Attempt a non-curated and sensitive question through the API; confirm rejection.
9. Run camera for 60 minutes, then camera plus the ModelDeck-served model for two hours while observing process/GPU/system memory.
10. Verify SceneChat never binds `3600`, `8600`, or `8610–8699`, and never sends a request directly to a worker.
11. Cold reboot and follow only `OPEN_DAY_RUNBOOK.md` with an operator who did not build the project.

## Acceptance record

Record dates, software/model hashes, operators, mean/p95 metrics, maximum memory, and pass/fail evidence in `MODEL_COMPATIBILITY.md`. Hardware-dependent items are not passed merely because the offline suite passes.
