# Test plan

## Automated offline tests

The suite covers configuration safety, detector box validation, prompt safeguards, structured model parsing, replay manifest safety, provider selection, state reset, stale response rejection, mock analysis, API health/state/reset/privacy, provider failure degradation, and curated-question rejection. It must not require a camera, large model, model download, or network.

Run `& .venv/bin/python -m pytest` and `pwsh -NoProfile -File scripts/smoke_test.ps1` with the service active.

## Optional hardware tests

1. Benchmark at least two locally approved detector weights on the same 300+ frame booth video.
2. Run empty room, one person, several people, clutter, partial occlusion, reflections, poor light, and backlight cases.
3. Disconnect and reconnect the camera; confirm replay remains usable and memory remains bounded.
4. Send ten Gemma 4 image requests; record median/p95 latency and failure count.
5. Stop vLLM during a request; confirm no UI freeze, retained valid description, and detector-only degradation.
6. Trigger reset during a slow model response; confirm the stale response never appears.
7. Repeatedly activate privacy; confirm the browser and `/api/frame` hide the image immediately.
8. Attempt a non-curated and sensitive question through the API; confirm rejection.
9. Run camera for 60 minutes, then combined mode for two hours while observing process/GPU/system memory.
10. Cold reboot and follow only `OPEN_DAY_RUNBOOK.md` with an operator who did not build the project.

## Acceptance record

Record dates, software/model hashes, operators, mean/p95 metrics, maximum memory, and pass/fail evidence in `MODEL_COMPATIBILITY.md`. Hardware-dependent items are not passed merely because the offline suite passes.
