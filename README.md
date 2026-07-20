# SceneChat

SceneChat is a local-first Open Day demonstration that keeps fast object detection separate from periodic multimodal scene description. It owns the visitor and kiosk experience, scene/session state, privacy controls, reset behaviour, replay operation, and demo-specific health information. Live model requests go through ModelDeck; replay and deterministic mock operation need no model service.

The detector finds objects quickly. The multimodal model generates a likely interpretation of the scene. Both can make mistakes.

## Supported modes and providers

Application modes are `development`, `live`, `detector-only`, `mock`, and `replay`. Live camera operation can run without an object detector by setting `DETECTOR_BACKEND=none`; replay retains prepared object labels for the offline demonstration.

`MODEL_PROVIDER` is always explicit:

- `modeldeck` sends live requests only through the ModelDeck gateway;
- `replay` and `fallback` run without a live model;
- `mock` is retained for deterministic development and tests.

SceneChat never switches providers automatically. A ModelDeck failure keeps ModelDeck selected, retains the previous valid description, and degrades the app to camera/detector-only operation until staff explicitly recover or select an offline provider.

## Quick start

Python 3.12 or newer and PowerShell 7 (`pwsh`) are required. SceneChat has four commands: setup, download, run, and stop.

```powershell
pwsh -NoProfile -File scripts/setup.ps1
pwsh -NoProfile -File scripts/download.ps1
pwsh -NoProfile -File scripts/run.ps1
```

Setup creates `.env` from `.env.example` when needed and installs the camera, test, YOLOE, and YOLO-World dependencies. Download fetches the two configured detector checkpoints and their text encoders with pinned SHA-256 verification. Run treats `.env` as authoritative, starts the demo in the background, writes `.scenechat.pid`, stores process output under `logs/`, and exits so the terminal is immediately available.

Run starts the demo in the background. Stop it with:

```powershell
pwsh -NoProfile -File scripts/stop.ps1
```

Open:

- unified visitor and operator screen: `http://127.0.0.1:3700/`
- health: `http://127.0.0.1:3700/api/health`
- API reference: `http://127.0.0.1:3700/api/docs`

Use **Operator controls** on the main screen to configure the camera, mode and provider or view diagnostics. The former `/staff` URL redirects to this panel for compatibility.

The scene panel clearly reports when analysis is ready, actively thinking, displaying a completed result, disabled, or unavailable. A previous valid description remains labelled while a new request is running.

## Port ownership

| Owner | Purpose | Port |
|---|---|---:|
| SceneChat | Application, unified visitor/operator UX, API, health | `3700` |
| ModelDeck | Management | `3600` |
| ModelDeck | Model gateway used by SceneChat | `8600` |
| ModelDeck | Managed private Workers | ModelDeck-assigned; never configured in SceneChat |

SceneChat binds only to `3700`. It sends model requests only to the dedicated `http://127.0.0.1:8600/v1/vision/analyse` gateway route using the `scenechat-vision` alias and `scene-analysis-v1` contract. Readiness requires `image_input` and `structured_output`. SceneChat never calls ModelDeck management or Worker ports and cannot create, start, stop or replace Workers.

The prepared Worker uses `google/gemma-4-E2B-it`, the SceneChat Gemma 4 trusted runtime, BF16, an 8,192-token context, a 512-token maximum output and an on-demand lifecycle. ModelDeck owns its model discovery, credentials, lifecycle and private routing. SceneChat has no Worker credential and performs no live model download.

## Configuration

The operational environment shape is:

```env
SCENECHAT_HOST=127.0.0.1
SCENECHAT_PORT=3700

MODEL_PROVIDER=modeldeck
MODELDECK_URL=http://127.0.0.1:8600
MODELDECK_MODEL=scenechat-vision
VISION_REQUEST_TIMEOUT_SECONDS=20
VISION_ANALYSIS_MAX_EDGE=0
VISION_MAX_TOKENS=512
```

Invalid application ports and ModelDeck management, legacy direct-model, non-loopback, or Worker URLs are rejected at start-up. No ModelDeck secret is configured in SceneChat. Storage of frames or video is also rejected by configuration.

`VISION_MAX_TOKENS` limits the complete structured scene-description response. The default is 512, matching the prepared Worker's maximum; lower values down to 128 remain valid for deliberate latency experiments, but can truncate the JSON response.

`VISION_ANALYSIS_MAX_EDGE` is an optional transport and experimentation control for only the in-memory image copy sent to ModelDeck. The default `0` disables manual resizing; experimental limits from 256 to 1280 pixels are accepted. A value of 512 converts a 1280×720 frame to 512×288 and a 720×1280 frame to 288×512 without cropping, padding, stretching or upscaling. SceneChat uses OpenCV `INTER_AREA` interpolation when shrinking and re-encodes the request copy as JPEG at quality 82. The original camera frame remains unchanged for browser display and object detection, and neither copy is written to disk.

Image dimensions, encoded byte counts, resize duration, total provider latency and the request outcome are logged for successful and timed-out ModelDeck analysis requests. These diagnostics never include image or base64 data, prompts, or visitor-derived descriptions. Pixel resizing primarily changes transport size and does not imply an inference-latency improvement: ModelDeck's trusted Worker owns Gemma 4's native processor configuration and currently uses `max_soft_tokens=280`, `patch_size=16` and `pooling_kernel_size=3`. SceneChat sends no visual-token setting. A separate ModelDeck experiment may compare allowlisted native budgets of 70, 140, 280, 560 or 1120; 140 and 280 are the recommended starting comparison.

SceneChat uses promptable YOLOE and YOLO-World checkpoints so both detector choices share the same approved object vocabulary. Set `DETECTOR_MODEL` to a local default and configure an explicit server-side allowlist for switching; the browser receives identifiers rather than paths:

```env
DETECTOR_BACKEND=auto
DETECTOR_MODEL=/path/to/models/yolov8s-worldv2.pt
DETECTOR_MODEL_OPTIONS={"yoloe-26s":"/path/to/models/yoloe-26s-seg.pt","yoloworld-s":"/path/to/models/yolov8s-worldv2.pt"}
DETECTOR_MAX_FPS=5
DETECTOR_TEXT_ENCODER=/path/to/models/mobileclip2_b.ts
DETECTOR_YOLOWORLD_CLIP=/path/to/models/ViT-B-32.pt
```

The **Object detector model** selector pauses and restarts an active camera while the selected model loads. SceneChat never accepts an arbitrary model path from the browser and never downloads detector weights at public-demo start-up.

`DETECTOR_MAX_FPS` limits expensive detector inference independently of camera capture. The default of 5 reuses the latest boxes between inference passes, substantially reducing CPU preprocessing without reducing the camera refresh rate.

Download or re-verify the detector artefacts at any time with:

```powershell
pwsh -NoProfile -File scripts/download.ps1
```

The script uses temporary partial files and refuses to replace an unrecognised existing file. SceneChat validates local files and never downloads weights during `run.ps1`.

Operators can select active prompts from the approved vocabulary for either detector family. When automatic prompt updates are enabled, a completed scene description adds only exact object labels returned in Gemma's structured `objects` list that also appear in that vocabulary. Free-form model text never becomes a detector prompt.

Do not promote a model backend to Open Day use until the hardware checks in [MODEL_COMPATIBILITY.md](docs/MODEL_COMPATIBILITY.md) pass.

## Fallback operation

- Open **Operator controls** and use **Disable scene analysis** if ModelDeck is unavailable; the live camera remains available.
- Explicitly choose the `fallback` or `replay` provider and replay mode when a live model is not wanted.
- Use replay if the camera or ModelDeck is unavailable; it needs neither service.
- Use **Hide camera now** for an immediate privacy holding screen.
- Use **Reset session** between visitors; it clears generated text and makes in-flight responses stale.

## ModelDeck and SceneChat start-up

1. In the ModelDeck repository, run its port and environment checks, then start it in Open Day mode with its PowerShell scripts.
2. Open `http://127.0.0.1:3600`, start the prepared SceneChat Gemma 4 Worker, and wait for **ready**.
3. From this repository, run `pwsh -NoProfile -File scripts/check_modeldeck.ps1`.
4. Run `pwsh -NoProfile -File scripts/run.ps1`, open `http://127.0.0.1:3700/`, and use **Check provider readiness**.
5. Start the camera, then apply `live` mode with `modeldeck`. If readiness fails, remain in camera-only mode or explicitly select replay/fallback.

SceneChat start-up is deliberately non-fatal when ModelDeck is absent so offline operation remains available.

## Tests

```powershell
& .venv/bin/python -m pytest -m "not hardware"
```

No ordinary automated test needs a physical camera, detector weights, network access, ModelDeck, or a large model. With the prepared Worker and SceneChat already running, `pwsh -NoProfile -File benchmarks/run.ps1` performs the opt-in prepared-image acceptance checks.
