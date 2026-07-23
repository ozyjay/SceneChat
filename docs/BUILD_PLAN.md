# Build plan

## Phase 0 — environment and compatibility spike

**Goal:** verify the hardware pipeline without coupling application progress to it.  
**Files:** environment/port checks, ModelDeck gateway image probe, detector benchmark, this plan, and `MODEL_COMPATIBILITY.md`.
**Tests:** scripts execute safely; ModelDeck-served model and detector benchmarks are optional hardware tests.
**Gate:** a detector is usable, an image request through the ModelDeck gateway succeeds, and concurrent memory use is stable. Earlier host-level work confirmed camera access, two local YOLO candidates, and Gemma 4 E2B image inference on `gfx1151`, but it predates the required ModelDeck routing. This gate remains **not passed** until the gateway path and long-duration runs complete.

## Phase 1 — recorded-image vertical slice

**Goal:** provide the complete offline flow.  
**Delivered:** validated configuration and schemas, synthetic replay asset and boxes, mock/replay providers, unified visitor/operator route, health, curated questions, analysis, SSE state, privacy screen, and reset.

**Acceptance:** starts with one command after setup, works offline, changes responses for prepared questions, and resets cleanly.

## Phase 2 — live detector

**Goal:** add recoverable camera capture without delaying the UI.  
**Delivered foundation:** optional OpenCV camera thread, latest-frame-only buffering, promptable YOLOE and YOLO-World adapters, camera controls, frame endpoint, FPS state, privacy and detector-only controls.
**Hardware gate:** benchmark two local detector candidates, test device reconnection, then complete a 60-minute run. Do not select production detector weights before this comparison.

**Current scope decision (11 July 2026):** production live-detector selection is deferred. Live model validation uses `DETECTOR_BACKEND=none`, while replay keeps prepared object labels. Detector benchmarks and licensing are not gating the current model-focused work, and the live UI must not claim object detection is active.

## Phase 3 — ModelDeck scene analysis

**Goal:** use a multimodal model through the ModelDeck gateway without affecting detection.
**Delivered foundation:** `ModelDeckProvider`, dedicated gateway vision routing, the pinned `scenechat-vision` alias and `scene-analysis-v1` capability checks, gateway-only URL validation, JPEG/PNG data-URL input, strict structured response validation, prompt/output safeguards, one-request lock, timeout, automatic interval, generation-aware stale success/failure rejection, explicit replay fallback, and detector-only degradation without provider failover.
**Hardware gate:** exact gateway image request and combined-load measurements in `MODEL_COMPATIBILITY.md`. Request shape, route/capability readiness, concurrency, reset/privacy invalidation, timeout, explicit fallback and outage degradation have offline coverage. ModelDeck promoted the runtime-package-0.2.2, 140-visual-token candidate in Open2026 revision 35 under a recorded operator exception after 70 schema-valid isolated requests. SceneChat synchronised the revised exact prompt and passed all ten measured structured requests after preserving the prepared PNG, but its 9.20-second median missed the 8-second application target; its 10.17-second p95 passed. The two-hour camera-plus-model burn-in also remains.

## Phase 4 — Open Day interface

**Goal:** make the demo readable and operable without a terminal.  
**Delivered foundation:** large public layout, obvious mode, boxes, object counts, curated questions, limitations/privacy messages, and an integrated operator controls/diagnostics panel.

**User gate:** 2–3 metre readability review and an operator handover using the runbook.

## Phase 5 — hardening

**Goal:** production rehearsal and freeze.  
**Delivered foundation:** one deterministic `.env`-driven launcher, privacy defaults, graceful resource release, and offline tests.
**Remaining model-focused gate:** resolve or explicitly waive SceneChat's 9.20-second median result against the frozen revision-35 fingerprint. Reset-during-inference and privacy-during-inference passed against the promoted Worker; the earlier gateway-outage drill has not been repeated against it. The physical camera-disconnect drill, 60-minute camera test, two-hour camera-plus-model burn-in, cold reboot and staff rehearsal remain.

## Risks and go/no-go rules

- **Strix Halo runtime:** ModelDeck promoted the Worker under a documented latency and qualification exception; treat the SceneChat end-to-end route as unverified until its current acceptance and burn-in evidence is recorded, and keep replay and detector-only ready.
- **Unified-memory pressure:** use E2B first, restrict model context, record memory before and during combined use, and avoid concurrent analyses.
- **Camera enumeration:** select named devices in operator controls and rehearse reconnect; camera failure must route to replay.
- **Detector licence/performance:** deferred while the live model path uses no detector; reassess before re-enabling live object detection.
- **Structured-output variance:** validate every response, retain the last valid description, and show no raw exception publicly.
- **Public privacy:** no storage, curated inputs only, immediate holding screen, reset between visitors, and visible signage.

Open Day is **no-go** until every remaining hardware and operational gate above is recorded as passed.
