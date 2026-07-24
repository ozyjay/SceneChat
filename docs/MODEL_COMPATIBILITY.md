# Model and hardware compatibility record

Last updated: 24 July 2026. Measurements marked **not run** must be completed on the actual booth system. Earlier direct-runtime and revision-34 evidence is retained only as historical context and does not validate the current SceneChat path through the promoted ModelDeck route.

## Current production candidate

| Item | Required value |
|---|---|
| Public route | `scenechat-vision` |
| Protocol contract | `scene-analysis-v1` |
| Required capabilities | `image_input`, `structured_output` |
| Model | Qwen3.5 0.8B |
| Runtime | ModelDeck Qwen3.5 ROCm Worker |
| ModelDeck runtime package | 0.2.2 |
| Visual-token budget | 140 |
| Worker completion ceiling | 1,024 |
| SceneChat request ceiling | 1,024 |
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
| ModelDeck version and active Event revision | ModelDeck 0.1.0 at `278f436637cf3e003bf70645c281135455460034`; `Open2026` revision 35 |
| Worker definition/runtime fingerprint | immutable Worker `3ad2f88d-8936-4ffc-ac63-6b5e6543d4ed`; `qwen35-vision-language-transformers-rocm`; runtime package 0.2.2; bfloat16; 140 visual tokens; 1,024 Worker completion ceiling; SceneChat requests at most 1,024 |
| Exact model revision and artefact fingerprint | `Qwen/Qwen3.5-0.8B@2fc06364715b967f1860aea9cf38778875588b17`; locally cached source model |
| Gateway alias, protocol and capabilities | passed for `scenechat-vision`, `scene-analysis-v1`, `image_input` and `structured_output`; cloud fallback disabled |
| ModelDeck isolated qualification | passed functionally: all 70 measured responses were schema-valid with zero failures or length finishes; ModelDeck recorded 8.76-second p50 and 10.07-second p95 and promoted the Worker under an explicit operator exception to the 8-second median target |
| SceneChat prepared JPEG/PNG request and strict schema | passed after preserving the validated 59,214-byte PNG when resizing is disabled: two warm-ups and all ten measured requests were schema-valid with zero failures |
| SceneChat ten-request median/p95 and failure count | latency gate failed: 9,200.8 ms end-to-end median and 10,171.4 ms nearest-rank p95; the 8,000 ms median target failed and the 12,000 ms p95 target passed |
| Prompt/completion token metrics and limit hits | Qualification run: 518 prompt-token median; 315.5 completion-token median; 300–358 completion-token range; zero 512-token limit hits; 35.03 observed completion tokens/second median. Subsequent live-camera operation produced repeated 512-token truncations, so SceneChat now uses the Worker's 1,024-token ceiling; physical revalidation is pending. |
| Gateway-outage/Worker-not-ready drill | passed against revision 34: HTTP 503 was sanitised, `modeldeck` remained selected, the previous valid result was retained, the app degraded to detector-only mode, and explicit Worker restart/readiness recovery succeeded; **not rerun** against revision 35 |
| Reset during inference | passed against revision 35; the eventual result was discarded as stale |
| Privacy during inference | passed against revision 35; `/api/frame` hid the image immediately and the eventual result was discarded as stale |
| 60-minute camera run | not run |
| Two-hour camera plus model stability | not run |
| Physical camera disconnect/reconnect | not run |
| Cold reboot and independent operator rehearsal | not run |

The opt-in acceptance uses only the committed synthetic `demo_booth.png`. It does not print model descriptions or persist a request image.

The failed 23 July revision-34 attempt used SceneChat commit
`604d50accd6738af25464fc9ea2a84bf81709f1d` plus a local acceptance fix that
prevents a stopped camera's buffered frame from being used for analysis. Before
that fix, the benchmark safety check served the replay frame through `/api/frame`
but `/api/analyse` could still select the last buffered camera frame. The
corrected offline suite passed 152 tests, and all requests in the repeated
physical attempt used the same prepared 59,214-byte source image.

ModelDeck subsequently qualified runtime package 0.2.2 with 140 visual tokens,
bounded output wording and complete-JSON stopping. All 70 isolated responses were
valid. The recorded 8.76-second median exceeded the standard 8-second target, and
manual review, combined two-hour load and drills were not completed for that Worker.
On 24 July the operator explicitly accepted those exceptions and promoted it in
Open2026 revision 35. ModelDeck's native and gateway synthetic PNG smoke tests passed,
and SceneChat's application-level run confirmed the revised exact prompt, strict
parser and then-current 512-token request ceiling. The first SceneChat attempt re-encoded the
prepared PNG to JPEG and produced a deterministic schema violation for the
closest-object question. Preserving validated JPEG or PNG bytes when resizing is
disabled made all measured requests valid. The completed run still failed the
8-second median latency gate at 9.20 seconds; its 10.17-second p95 passed.

## Preliminary host evidence

- Camera device 0 previously sustained 1,769 frames over 60.01 seconds at 1280×720, or 29.48 effective FPS, with no read failures. This is not the required 60-minute run.
- Ten camera close/reopen cycles returned a frame. A physical USB disconnect/reconnect drill remains required.
- A historical Gemma 4 E2B direct-runtime probe produced structured image responses with roughly six-second median latency across ten requests. That superseded path did not use the current Qwen3.5 ROCm Worker profile, ModelDeck gateway or published Event route.
- The earlier application flow rejected a concurrent request, rejected a result made stale by reset, blocked analysis while privacy was active, and degraded to camera-only mode after runtime failure. Current offline tests cover the equivalent ModelDeck-facing logic, but physical confirmation remains required.
- Earlier YOLO11 measurements are superseded by the promptable YOLOE/YOLO-World design and do not approve a live detector for Open Day use.

## Decision

ModelDeck has promoted the current Qwen3.5 Worker under a documented operator
exception, but the complete SceneChat Open Day configuration remains **no-go**. Its
revision-35 functional acceptance and p95 latency gate passed, while its 9.20-second
median remains above the 8-second SceneChat target. That result, the long-duration
runs, physical camera recovery, cold reboot and operator handover must be recorded as
passed or explicitly waived.
Replay and live-camera-only operation remain the approved explicit fallbacks. There
is no automatic cloud or provider failover.
