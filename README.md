# SceneChat

SceneChat is a local-first Open Day demonstration that keeps fast object detection separate from periodic multimodal scene description. It owns the visitor and kiosk experience, scene/session state, privacy controls, reset behaviour, replay operation, and demo-specific health information. Live model requests go through ModelDeck; replay and deterministic mock operation need no model service.

The detector finds objects quickly. The multimodal model generates a likely interpretation of the scene. Both can make mistakes.

## Supported modes and providers

Application modes are `development`, `live`, `detector-only`, `mock`, and `replay`. Live camera operation can run without an object detector by setting `DETECTOR_BACKEND=none`; replay retains prepared object labels for the offline demonstration.

`MODEL_PROVIDER` is always explicit:

- `modeldeck` sends live requests only through the ModelDeck gateway;
- `replay` and `fallback` run without a live model (`MODEL_FALLBACK_MODE=replay`);
- `mock` is retained for deterministic development and tests.

SceneChat never switches to another live provider automatically. A ModelDeck failure keeps the selected provider visible and degrades the app to camera/detector-only operation until staff explicitly choose a recovery or fallback.

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
| ModelDeck | Managed model workers | `8610–8699` |

SceneChat binds only to `3700`. It sends model requests only to the dedicated `http://127.0.0.1:8600/v1/vision/analyse` gateway route using the `scenechat-vision` alias, and never calls or binds ModelDeck management or worker ports. SceneChat does not start or stop ModelDeck workers.

## Configuration

The operational environment shape is:

```env
SCENECHAT_HOST=127.0.0.1
SCENECHAT_PORT=3700

MODEL_PROVIDER=modeldeck
MODELDECK_URL=http://127.0.0.1:8600
MODEL_FALLBACK_MODE=replay
VISION_MAX_TOKENS=350
```

Invalid application ports and ModelDeck management, legacy direct-model, non-loopback, or worker URLs are rejected at start-up. Storage of frames or video is also rejected by configuration.

`VISION_MAX_TOKENS` limits the scene-description response, including its structured JSON. The default of 350 is intended to keep public-demo responses concise; values from 128 to 512 are accepted so model quality and latency can be compared deliberately.

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

## Tests

```powershell
& .venv/bin/python -m pytest
```

No default automated test needs a physical camera, detector weights, network access, ModelDeck, or a large model.
