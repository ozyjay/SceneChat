# Build plan

## Phase 0 — environment and compatibility spike

**Goal:** verify the hardware pipeline without coupling application progress to it.  
**Files:** environment/port checks, vLLM image probe, detector benchmark, this plan, and `MODEL_COMPATIBILITY.md`.  
**Tests:** scripts execute safely; vLLM and detector benchmarks are optional hardware tests.  
**Gate:** a detector is usable, a Gemma 4 image request succeeds, and concurrent memory use is stable. This gate is currently **not passed** because the execution environment exposes neither `/dev/kfd`, a camera, nor the container socket.

## Phase 1 — recorded-image vertical slice

**Goal:** provide the complete offline flow.  
**Delivered:** validated configuration and schemas, synthetic replay asset and boxes, mock/replay providers, public and staff routes, health, curated questions, analysis, SSE state, privacy screen, and reset.  
**Acceptance:** starts with one command after setup, works offline, changes responses for prepared questions, and resets cleanly.

## Phase 2 — live detector

**Goal:** add recoverable camera capture without delaying the UI.  
**Delivered foundation:** optional OpenCV camera thread, latest-frame-only buffering, optional YOLO adapter, camera controls, frame endpoint, FPS state, privacy and detector-only controls.  
**Hardware gate:** benchmark two local detector candidates, test device reconnection, then complete a 60-minute run. Do not select production detector weights before this comparison.

## Phase 3 — Gemma scene analysis

**Goal:** add a local Gemma 4 image endpoint without affecting detection.  
**Delivered foundation:** `VllmGemmaProvider`, data-URL image input, structured response validation, prompt safeguards, one-request lock, timeout, timestamps, automatic interval, stale-result rejection, and detector-only degradation.  
**Hardware gate:** exact image request and combined-load measurements in `MODEL_COMPATIBILITY.md`.

## Phase 4 — Open Day interface

**Goal:** make the demo readable and operable without a terminal.  
**Delivered foundation:** large public layout, obvious mode, boxes, object counts, curated questions, limitations/privacy messages, and staff controls/diagnostics.  
**User gate:** 2–3 metre readability review and an operator handover using the runbook.

## Phase 5 — hardening

**Goal:** production rehearsal and freeze.  
**Delivered foundation:** deterministic launch/check/smoke/stop scripts, privacy defaults, graceful resource release, and offline tests.  
**Remaining gate:** freeze model/detector artefacts, run camera disconnect and model outage drills, 60-minute camera test, two-hour combined burn-in, cold reboot, and staff rehearsal.

## Risks and go/no-go rules

- **Strix Halo vLLM kernels:** the current official Gemma 4 AMD recipe lists Instinct GPUs, not this integrated GPU. Treat support as unverified; keep replay and detector-only ready.
- **Unified-memory pressure:** use E2B first, restrict model context, record memory before and during combined use, and avoid concurrent analyses.
- **Camera enumeration:** select devices in staff controls and rehearse reconnect; camera failure must route to replay.
- **Detector licence/performance:** record the exact weights and licence and benchmark at least two candidates locally.
- **Structured-output variance:** validate every response, retain the last valid description, and show no raw exception publicly.
- **Public privacy:** no storage, curated inputs only, immediate holding screen, reset between visitors, and visible signage.

Open Day is **no-go** until every remaining hardware and operational gate above is recorded as passed.

