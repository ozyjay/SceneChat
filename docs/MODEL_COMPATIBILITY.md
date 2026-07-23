# Model and hardware compatibility record

Last updated: 23 July 2026. Measurements marked **not run** must be completed on the actual booth system. Earlier direct-runtime evidence is retained only as historical context and does not validate the current ModelDeck route.

## Current production candidate

| Item | Required value |
|---|---|
| Public route | `scenechat-vision` |
| Protocol contract | `scene-analysis-v1` |
| Required capabilities | `image_input`, `structured_output` |
| Model | Qwen3.5 0.8B |
| Runtime | ModelDeck Qwen3.5 ROCm Worker |
| Visual-token budget | 280 |
| SceneChat gateway | `http://127.0.0.1:8600` |
| Preferred endpoint | `POST /v1/vision/analyse` |

ModelDeck owns local model discovery, the immutable Worker definition, private Worker credential, lifecycle, readiness and routing. SceneChat owns only its loopback gateway URL, public alias, bounded request and strict response validation. It neither knows nor addresses the Worker port.

## Inspected host

| Item | Observed |
|---|---|
| OS | Fedora Linux 44 Workstation |
| Host Python | 3.14.6 through pyenv; SceneChat requires Python 3.12 or newer |
| GPU | AMD Strix Halo, reported as Radeon 8050S/8060S graphics |
| System memory | 125 GiB total, 117 GiB available during the earlier inspection |
| ROCm packages | Fedora ROCm 7.1.x packages were installed during the earlier inspection |
| GPU access | Approved host probes enumerated `gfx1151`, 40 compute units |
| Camera | Devices 0 and 2 returned frames during preliminary checks; device 0 was selected |
| Port ownership | SceneChat `3700`; ModelDeck management `3600`; ModelDeck gateway `8600`; private Worker routing owned by ModelDeck |

Ordinary restricted checks cannot validate the physical camera, GPU devices or ModelDeck Worker. Those results must come from the explicit PowerShell acceptance procedure recorded below.

## Required current acceptance

Start ModelDeck and the prepared Worker using `OPEN_DAY_RUNBOOK.md`, then run:

```powershell
pwsh -NoProfile -File scripts/check_modeldeck.ps1
pwsh -NoProfile -File scripts/run.ps1
pwsh -NoProfile -File benchmarks/run.ps1
```

Record one complete immutable fingerprint and the following results:

| Result | Value |
|---|---|
| ModelDeck version and active Event revision | ModelDeck 0.1.0 at `2d8d7ebe0decc36fa81c37568b9792f93189a501`; `Open2026` revision 34 |
| Worker definition/runtime fingerprint | `Qwen3.5 0.8B 280vt`; `qwen35-vision-language-transformers-rocm`; template `scenechat-qwen35` 0.1.0; bfloat16; 280 visual tokens; 512 maximum completion tokens |
| Exact model revision and artefact fingerprint | `Qwen/Qwen3.5-0.8B@2fc06364715b967f1860aea9cf38778875588b17`; locally cached source model |
| Gateway alias, protocol and capabilities | passed for `scenechat-vision`, `scene-analysis-v1`, `image_input` and `structured_output`; cloud fallback disabled |
| Prepared JPEG/PNG request and strict schema | failed: two warm-ups and five measured prepared-image requests passed, then the sixth measured curated question reached the 512-token limit and failed output validation |
| Ten-request median/p95 and failure count | failed before completion: five measured ModelDeck round trips had 9,432.2 ms median and 9,835.3 ms nearest-rank p95; one subsequent request failed after 14,887.5 ms; the 8,000 ms end-to-end median gate cannot pass when the provider median alone exceeds it |
| Prompt/completion token metrics and limit hits | incomplete because the run stopped on failure; the failed request used 512 of 512 completion tokens and was rejected as `token_limit_reached` |
| Gateway-outage/Worker-not-ready drill | passed: HTTP 503 was sanitised, `modeldeck` remained selected, the previous valid result was retained, the app degraded to detector-only mode, and explicit Worker restart/readiness recovery succeeded |
| Reset during inference | passed against the current route; the eventual result was discarded as stale |
| Privacy during inference | passed against the current route; `/api/frame` hid the image immediately and the eventual result was discarded as stale |
| 60-minute camera run | not run |
| Two-hour camera plus model stability | not run |
| Physical camera disconnect/reconnect | not run |
| Cold reboot and independent operator rehearsal | not run |

The opt-in acceptance uses only the committed synthetic `demo_booth.png`. It does not print model descriptions or persist a request image.

The 23 July attempt used SceneChat commit
`604d50accd6738af25464fc9ea2a84bf81709f1d` plus a local acceptance fix that
prevents a stopped camera's buffered frame from being used for analysis. Before
that fix, the benchmark safety check served the replay frame through `/api/frame`
but `/api/analyse` could still select the last buffered camera frame. The
corrected offline suite passed 152 tests, and all requests in the repeated
physical attempt used the same prepared 59,214-byte source image.

## Preliminary host evidence

- Camera device 0 previously sustained 1,769 frames over 60.01 seconds at 1280×720, or 29.48 effective FPS, with no read failures. This is not the required 60-minute run.
- Ten camera close/reopen cycles returned a frame. A physical USB disconnect/reconnect drill remains required.
- A historical Gemma 4 E2B direct-runtime probe produced structured image responses with roughly six-second median latency across ten requests. That superseded path did not use the current Qwen3.5 ROCm Worker profile, ModelDeck gateway or published Event route.
- The earlier application flow rejected a concurrent request, rejected a result made stale by reset, blocked analysis while privacy was active, and degraded to camera-only mode after runtime failure. Current offline tests cover the equivalent ModelDeck-facing logic, but physical confirmation remains required.
- Earlier YOLO11 measurements are superseded by the promptable YOLOE/YOLO-World design and do not approve a live detector for Open Day use.

## Decision

The current Qwen3.5 production candidate is **no-go**: its repeated prepared-image
acceptance run did not complete ten measured requests, exceeded the median latency
gate on the partial sample, and failed strict output validation when one curated
question reached the 512-token limit. Open Day status also remains no-go until the
long-duration runs, physical camera recovery, cold reboot and operator handover are
recorded as passed. Replay and live-camera-only operation remain the approved explicit
fallbacks. There is no automatic cloud or provider failover.
