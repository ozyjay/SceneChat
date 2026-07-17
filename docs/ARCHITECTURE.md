# Architecture

```text
camera thread -> one latest JPEG -> detector adapter -> normalised boxes
                         |
                         +-> frame sampler -> VisionLanguageProvider (one request at a time)
                                                   |
                                                   +-> ModelDeck gateway :8600

validated state store -> SSE updates -> unified visitor/operator screen
```

## Boundaries

- `services/camera.py` owns camera resources on a background thread and retains only one encoded frame in memory. A newer frame replaces the older one.
- `detection/` contains no-op, local YOLOE, and local YOLO-World adapters. Standard YOLO checkpoints are not accepted. Replay annotations use the same normalised `Detection` schema.
- Runtime detector switching is restricted to model paths allowlisted by the operator at start-up. Model loading runs off the asynchronous event loop, and an active camera is paused and restarted around the change.
- The YOLOE and YOLO-World adapters apply locally encoded text prompts under the same lock used for inference. Operator choices and structured Gemma object labels are restricted to a configured, generic-object allowlist; summaries and other free-form text are never used as prompts.
- `vision/` isolates deterministic offline providers and the ModelDeck gateway behind one provider protocol. ModelDeck may schedule its own workers on ports `8610–8699`; SceneChat never addresses those workers directly.
- `services/analysis.py` limits analysis to one request, applies a timeout, validates output, and rejects a result after reset by comparing state generations.
- `services/state.py` is the shared, concurrency-safe state boundary. The browser receives state through Server-Sent Events.
- The unified visitor/operator screen is dependency-free HTML, CSS, and JavaScript served by FastAPI. Its operator panel shares the same state stream as the visitor view, avoiding duplicate connections and a second build tool or process.

## Failure isolation

Provider failure leaves the previous valid description in place, exposes a concise staff error, and degrades a ModelDeck session to detector-only mode without changing the selected provider. Repeated camera read failures terminate capture, clear the in-memory frame and detections, and prompt the operator to reconnect and restart; replay remains available. The privacy flag hides the `/api/frame` response and public visual immediately. Reset never waits for model completion.

## Runtime ownership

SceneChat serves its unified visitor/operator interface, API, session state, privacy controls, reset flow, replay assets, and demo health information from `127.0.0.1:3700`. ModelDeck owns management on `127.0.0.1:3600`, its gateway on `127.0.0.1:8600`, and workers on `8610–8699`. There is no SceneChat model adapter process or extra port.

## Data handling

Frames exist only in camera and request memory. They are not written to disk, included in logs, or cached by browsers. The committed replay asset is synthetic. Curated questions eliminate public arbitrary-prompt input.
