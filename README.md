# SceneChat

SceneChat is a local-first Open Day demonstration that keeps fast object detection separate from periodic multimodal scene description. It includes large-screen public and local staff interfaces, deterministic mock and replay providers, detector-only degradation, an immediate privacy screen, and a reset that invalidates in-flight analysis.

The detector finds objects quickly. The multimodal model generates a likely interpretation of the scene. Both can make mistakes.

## Supported modes

- `development`: prepared detections with the deterministic mock provider
- `live`: camera plus configured detector and scene provider
- `detector-only`: camera and boxes without a model dependency
- `mock`: deterministic development responses
- `replay`: synthetic image, prepared boxes, and prepared responses; no camera or model needed

The current hardware-validation scope is Gemma-focused. Live camera operation can run without an object detector by setting `DETECTOR_BACKEND=none`; replay retains prepared object labels for the offline demonstration.

## Quick start

Python 3.12 or newer is required. Python 3.12 is preferred for the current ROCm/vLLM tooling even though the application itself also runs on newer Python versions.

```powershell
cp .env.example .env
pwsh -NoProfile -File scripts/setup.ps1
pwsh -NoProfile -File scripts/run_dev.ps1
```

All operational scripts use PowerShell 7 (`pwsh`) for a consistent Fedora and VS Code workflow.

Open:

- public screen: `http://127.0.0.1:8900/`
- staff controls: `http://127.0.0.1:8900/staff`
- health: `http://127.0.0.1:8900/api/health`
- API reference: `http://127.0.0.1:8900/api/docs`

Port `3900` is reserved for a separately hosted public frontend if one is needed later. The current smaller deployment serves both interfaces from `8900`. Port `8000` belongs to the external local vLLM service.

## Configuration

Copy `.env.example`. Storage of frames or video is rejected by configuration. A non-loopback vLLM URL is also rejected unless `ALLOW_EXTERNAL_VISION_PROVIDER=true` is deliberately set after privacy approval and signage.

For live camera support:

```powershell
& .venv/bin/python -m pip install -e '.[camera]'
```

With an already-tested local vLLM service running, start the Gemma-only live path with:

```powershell
pwsh -NoProfile -File scripts/run_gemma.ps1
```

For the optional YOLO adapter and benchmark:

```powershell
& .venv/bin/python -m pip install -e '.[yolo]'
```

Set `DETECTOR_MODEL` to a local model path. SceneChat never downloads a detector model at public-demo start-up.

## Gemma 4 through vLLM

The configured candidate is exactly `google/gemma-4-E2B-it`; it has not been substituted. Start a compatible local vLLM OpenAI server on port `8000`, set `VISION_PROVIDER=vllm`, then use:

```powershell
& .venv/bin/python scripts/test_vllm_image.py path/to/local-test-image.jpg
```

Do not promote this backend to Open Day use until the hardware checks in [MODEL_COMPATIBILITY.md](docs/MODEL_COMPATIBILITY.md) pass. If it does not pass, use mock, replay, or detector-only mode rather than an automatic cloud service.

## Fallback operation

- In the Gemma-only configuration, use **Disable scene analysis** in `/staff` if the model is unavailable; the live camera remains available.
- In a detector-enabled configuration, use **Detector only** if the model is unavailable.
- Use **replay** plus the **replay** provider if the camera or model is unavailable.
- Use **Hide camera now** for an immediate privacy holding screen.
- Use **Reset session** between visitors; it clears generated text and makes in-flight responses stale.

## Tests

```powershell
& .venv/bin/python -m pytest
pwsh -NoProfile -File scripts/check_environment.ps1
pwsh -NoProfile -File scripts/check_ports.ps1
pwsh -NoProfile -File scripts/smoke_test.ps1 # while the application is running
```

No default automated test needs a physical camera, detector weights, network access, or a large model.
