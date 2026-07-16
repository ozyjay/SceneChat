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

Python 3.12 or newer and PowerShell 7 (`pwsh`) are required. Copy the example environment, set up the local virtual environment, and start the deterministic development mode:

```powershell
cp .env.example .env
pwsh -NoProfile -File scripts/setup.ps1
pwsh -NoProfile -File scripts/run_dev.ps1
```

Open:

- unified visitor and operator screen: `http://127.0.0.1:3700/`
- health: `http://127.0.0.1:3700/api/health`
- API reference: `http://127.0.0.1:3700/api/docs`

Use **Operator controls** on the main screen to configure the camera, mode and provider or view diagnostics. The former `/staff` URL redirects to this panel for compatibility.

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
```

Invalid application ports and ModelDeck management, legacy direct-model, non-loopback, or worker URLs are rejected at start-up. Storage of frames or video is also rejected by configuration.

For live camera support:

```powershell
& .venv/bin/python -m pip install -e '.[camera]'
```

With ModelDeck already running and the approved multimodal model available through its gateway, start the live no-detector path with:

```powershell
pwsh -NoProfile -File scripts/run_modeldeck.ps1
```

For the optional YOLO adapter and benchmark:

```powershell
& .venv/bin/python -m pip install -e '.[yolo]'
```

Set `DETECTOR_MODEL` to the default local model path. To permit operator switching, configure an explicit server-side allowlist; the browser receives identifiers rather than paths:

```env
DETECTOR_BACKEND=yolo
DETECTOR_MODEL=/path/to/yolo11s.pt
DETECTOR_MODEL_OPTIONS={"yolo11n":"/path/to/yolo11n.pt","yolo11s":"/path/to/yolo11s.pt"}
```

The **Object detector model** selector pauses and restarts an active camera while the selected model loads. SceneChat never accepts an arbitrary model path from the browser and never downloads detector weights at public-demo start-up.

### Promptable YOLOE detector

Download one official YOLOE checkpoint and its MobileCLIP2 text encoder explicitly:

```powershell
pwsh -NoProfile -File scripts/download_yoloe.ps1 -Variant s
& .venv/bin/python -m pip install -e '.[yoloe]'
```

Use `-Variant m`, `-Variant l`, or `-Variant all` when those larger local variants are required. The script verifies pinned SHA-256 checksums and refuses to replace an unrecognised existing file.

Configure the promptable detector with local paths only:

```env
DETECTOR_BACKEND=yoloe
DETECTOR_MODEL=/path/to/models/yoloe-26s-seg.pt
DETECTOR_MODEL_OPTIONS={"yoloe-26s":"/path/to/models/yoloe-26s-seg.pt"}
DETECTOR_TEXT_ENCODER=/path/to/models/mobileclip2_b.ts
DETECTOR_PROMPTS=["person","computer mouse","keyboard","laptop","monitor"]
DETECTOR_PROMPT_ALLOWLIST=["person","computer mouse","keyboard","laptop","monitor","mobile phone","camera","microphone","bottle","cup","chair","table","book","backpack","cabinet"]
DETECTOR_PROMPT_AUTO_UPDATE=false
```

Start the combined live camera and detector application with `scripts/run_live.ps1`. Do not use `scripts/run_modeldeck.ps1` for this workflow because that provider-only launcher deliberately disables SceneChat object detection.

Operators can select active prompts from the approved vocabulary. When automatic prompt updates are enabled, a completed scene description adds only exact object labels returned in Gemma's structured `objects` list that also appear in that vocabulary. Free-form model text never becomes a detector prompt.

To probe one approved non-visitor image through ModelDeck:

```powershell
& .venv/bin/python scripts/test_modeldeck_image.py path/to/approved-test-image.jpg
```

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
pwsh -NoProfile -File scripts/check_environment.ps1
pwsh -NoProfile -File scripts/check_ports.ps1
pwsh -NoProfile -File scripts/smoke_test.ps1 # while SceneChat is running
```

No default automated test needs a physical camera, detector weights, network access, ModelDeck, or a large model.
