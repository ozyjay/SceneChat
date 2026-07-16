# Model and hardware compatibility record

Last updated: 16 July 2026. Measurements marked **not run** must be completed on the actual booth session. Short preliminary measurements and the superseded direct-runtime path are not substitutes for the required ModelDeck gateway and long-duration acceptance runs.

## Inspected environment

| Item | Observed |
|---|---|
| OS | Fedora Linux 44 Workstation |
| Host Python | 3.14.6 through pyenv; vLLM ROCm recipe calls for Python 3.12 |
| GPU | AMD Strix Halo, reported as Radeon 8050S/8060S graphics |
| System memory | 125 GiB total, 117 GiB available during inspection |
| ROCm packages | Fedora ROCm 7.1.x packages installed |
| GPU access | Restricted commands cannot see `/dev/kfd`; an approved host probe and the vLLM container both enumerated `gfx1151`, 40 compute units |
| Camera | Host devices `/dev/video0` to `/dev/video3`; devices 0 and 2 returned frames, with device 0 selected for preliminary tests |
| Containers | Docker 29.6.1; approved host access previously verified the model runtime image and ran a local probe |
| Runtime ports | SceneChat `3700`; ModelDeck management `3600`; ModelDeck gateway `8600`; ModelDeck workers `8610–8699` |

The restricted workspace still cannot access the hardware devices or Docker socket directly. The results below were gathered through explicit host-level probes and are recorded separately from the remaining long-duration acceptance work.

## Verified current Gemma 4 identifiers and modalities

Official current instruction-tuned model identifiers include:

- `google/gemma-4-E2B-it` — image, text, and audio; 5.1B total parameters including embeddings
- `google/gemma-4-E4B-it` — image, text, and audio; 8B total parameters including embeddings
- `google/gemma-4-12B-it` — unified image, text, audio, and video model
- `google/gemma-4-26B-A4B-it` — image and text MoE model
- `google/gemma-4-31B-it` — image and text dense model

Sources: [Hugging Face Gemma 4 release and checkpoint table](https://huggingface.co/blog/gemma4), [Google Gemma 4 12B model card](https://huggingface.co/google/gemma-4-12B), and [official vLLM Gemma 4 recipe](https://github.com/vllm-project/recipes/blob/main/Google/Gemma4.md).

All listed variants accept images. The selected compatibility candidate is **exactly `google/gemma-4-E2B-it`** because it minimises the initial resource risk. No other model has been silently substituted. Production selection remains pending hardware results.

## ModelDeck-managed worker findings

The previously tested worker runtime supports Gemma 4 multimodal OpenAI-compatible requests. Current upstream AMD recipes list Instinct GPUs rather than Strix Halo, so model fit in system memory does not establish kernel compatibility. ModelDeck now owns worker selection, launch, and ports. SceneChat uses only the ModelDeck gateway and has no direct worker URL. Sources: [vLLM releases](https://github.com/vllm-project/vllm/releases) and [Gemma 4 recipe](https://github.com/vllm-project/recipes/blob/main/Google/Gemma4.md).

Approximate BF16 weights alone are about 10.2 GB for E2B and 16 GB for E4B, derived from their documented total parameter counts. Runtime memory is higher because of vision/audio encoders, KV cache, activations, allocator overhead, and the detector. This estimate is not a measured requirement.

## Required ModelDeck gateway probe

Use the separate ModelDeck operating procedure to prepare the approved model, then record exact values here after running:

```powershell
Invoke-RestMethod http://127.0.0.1:8600/v1/models
$Env:MODEL_PROVIDER = 'modeldeck'
$Env:MODELDECK_URL = 'http://127.0.0.1:8600'
$Env:MODELDECK_MODEL = 'google/gemma-4-E2B-it'
& .venv/bin/python scripts/test_modeldeck_image.py path/to/approved-test-image.jpg
```

| Result | Value |
|---|---|
| Historical worker version/image digest | 0.24.0; digest recorded in the 11 July acceptance notes |
| ModelDeck version/configuration | not run |
| Gateway model listing and image request | not run |
| ROCm visible inside container | passed preliminary probe; `gfx1151`, 40 compute units, GPU device type |
| Model revision/hash | `google/gemma-4-E2B-it` revision `9dbdf8a839e4e9e0eb56ed80cc8886661d3817cf`; 9.54 GiB checkpoint reported by vLLM |
| Historical direct-runtime image request | passed with a generated, non-visitor PNG; structured response passed the SceneChat parser |
| Historical cold load memory | worker reported 9.79 GiB for model loading; idle container RSS was approximately 7.44 GiB after start-up |
| Historical peak single-request memory | not sampled continuously; post-request container RSS was approximately 7.85 GiB |
| Historical median/p95 latency across 10 requests | 6006.2 ms median; 6057.4 ms p95; 5970.1 ms mean; 0 failures |
| Detector-only FPS | preliminary live-camera inference only: YOLO11n 153.36 mean FPS, 7.5 ms p95; YOLO11s 135.20 mean FPS, 8.1 ms p95 |
| Combined detector FPS | same preliminary results were collected while Gemma was loaded and idle; not yet measured during concurrent Gemma generation on the required booth video |
| Two-hour stability | not run |

## Preliminary hardware record — 10 July 2026

- Camera device 0 sustained 1769 frames over 60.01 seconds at 1280×720, or 29.48 effective FPS, with no read failures. One Gemma request ran during this capture with 6039.4 ms latency. This is a short combined-load smoke test, not the required 60-minute camera run or two-hour burn-in.
- Ten camera close/reopen cycles each opened successfully and returned a frame. A physical USB disconnect/reconnect drill is still required.
- Detector comparison used live camera frames because no approved 300+ frame booth video was available. Both models used PyTorch 2.9.1 ROCm 7.2.1 and Ultralytics 8.4.90 on GPU device 0. Installed package metadata declares the Ultralytics licence as AGPL-3.0; suitability for public deployment still requires an explicit licence decision.
- YOLO11n weight SHA-256: `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`.
- YOLO11s weight SHA-256: `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5`.
- System memory after the short combined detector/model work reported about 47.4 GiB available of 125.1 GiB. This single observation is not a peak measurement and does not establish long-run stability.

## Historical direct-runtime application record — 11 July 2026

This record predates the ModelDeck routing policy. It remains useful hardware evidence, but it does not validate the current SceneChat → ModelDeck gateway path and must not be used as an operating procedure.

- Scope was narrowed to live camera plus Gemma 4 E2B with `DETECTOR_BACKEND=none`. The earlier detector comparison remains historical preliminary data and is not gating this scope.
- The full camera → SceneChat API → earlier direct-runtime adapter → structured parser → state path passed with a live, non-persisted camera frame. The first end-to-end request took 12,595.2 ms; later observed requests were 8,296.4–10,752.6 ms.
- A concurrent second request returned HTTP 409 while the first completed normally, confirming the one-request limit.
- Reset during a live request incremented the generation, cleared visitor-facing text, and caused the completed response to return `applied=false`; it did not reappear in state.
- With privacy active, both `/api/frame` and `/api/analyse` returned HTTP 423. No test frame was written to disk.
- Automatic analysis produced valid model results and remained serialised. Disabling the schedule allowed the already-running request to finish and then settled idle.
- Making the earlier runtime unavailable during a request returned a sanitised HTTP 503, marked the provider unavailable, left the camera running, kept `/api/frame` available, and changed the public mode to **Live camera only**.
- The live no-detector state and UI now use Gemma/camera wording and expose no prepared detection boxes. Replay mode continues to expose its prepared labels.

## Decision

Gemma 4 E2B image inference and a superseded direct-runtime application flow are **preliminarily verified** on this Strix Halo/Fedora stack. The current ModelDeck gateway path is not yet hardware-verified. The Open Day gate remains **not passed** until ModelDeck artefacts are frozen, the gateway and outage probes pass, the physical camera drill passes, and the 60-minute camera and two-hour camera-plus-model runs complete without instability. Until then, keep replay and live-camera-only fallbacks ready. Never fail over automatically to another live provider.
