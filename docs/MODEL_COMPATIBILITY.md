# Model and hardware compatibility record

Last updated: 20 July 2026. Measurements marked **not run** must be completed on the actual booth system. Earlier direct-runtime evidence is retained only as historical context and does not validate the current ModelDeck route.

## Current production candidate

| Item | Required value |
|---|---|
| Public route | `scenechat-vision` |
| Protocol contract | `scene-analysis-v1` |
| Required capabilities | `image_input`, `structured_output` |
| Model | `google/gemma-4-E2B-it` |
| Runtime | SceneChat Gemma 4 trusted runtime |
| Precision | BF16 |
| Context | 8,192 tokens |
| Maximum Worker output | 512 tokens |
| Lifecycle | on-demand |
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

The restricted workspace cannot validate the physical camera, GPU devices or ModelDeck Worker. Those results must come from the explicit PowerShell acceptance procedure.

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
| ModelDeck version and active Event revision | not run |
| Worker definition/runtime fingerprint | not run |
| Exact model revision and artefact fingerprint | not run for current route |
| Gateway alias, protocol and capabilities | not run |
| Prepared JPEG/PNG request and strict schema | not run |
| Ten-request median/p95 and failure count | not run |
| Prompt/completion token metrics and limit hits | not run |
| Gateway-outage/Worker-not-ready drill | not run |
| Reset during inference | not run against current route |
| Privacy during inference | not run against current route |
| 60-minute camera run | not run |
| Two-hour camera plus model stability | not run |
| Physical camera disconnect/reconnect | not run |
| Cold reboot and independent operator rehearsal | not run |

The opt-in acceptance uses only the committed synthetic `demo_booth.png`. It does not print model descriptions or persist a request image.

## Preliminary host evidence

- Camera device 0 previously sustained 1,769 frames over 60.01 seconds at 1280×720, or 29.48 effective FPS, with no read failures. This is not the required 60-minute run.
- Ten camera close/reopen cycles returned a frame. A physical USB disconnect/reconnect drill remains required.
- A historical Gemma 4 E2B direct-runtime probe produced structured image responses with roughly six-second median latency across ten requests. That path did not use the current ModelDeck gateway, trusted-runtime Worker or published Event route.
- The earlier application flow rejected a concurrent request, rejected a result made stale by reset, blocked analysis while privacy was active, and degraded to camera-only mode after runtime failure. Current offline tests cover the equivalent ModelDeck-facing logic, but physical confirmation remains required.
- Earlier YOLO11 measurements are superseded by the promptable YOLOE/YOLO-World design and do not approve a live detector for Open Day use.

## Decision

The code-level integration is ready for current-route physical acceptance. Open Day status remains **no-go** until the prepared ModelDeck Worker fingerprint, gateway checks, outage and privacy/reset drills, long-duration runs, cold reboot and operator handover are recorded as passed. Replay and live-camera-only operation remain the approved explicit fallbacks. There is no automatic cloud or provider failover.
