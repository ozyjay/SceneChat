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
- Detector inference has an independent maximum rate and reuses the latest valid boxes between passes, preventing camera FPS from driving continuous CPU-heavy preprocessing.
- Runtime detector switching is restricted to model paths allowlisted by the operator at start-up. Model loading runs off the asynchronous event loop, and an active camera is paused and restarted around the change.
- The YOLOE and YOLO-World adapters apply locally encoded text prompts under the same lock used for inference. Operator choices form a protected baseline restricted to a configured allowlist. Optional session learning admits only structured object labels that pass the shared conservative label-and-description filter; summaries and other free-form text are never used as prompts.
- `vision/` isolates deterministic offline providers and the ModelDeck gateway behind one provider protocol. The live adapter checks the published `scenechat-vision` route for `image_input` and `structured_output`, accepts only JPEG/PNG input, and adds trusted operational metadata only after strict output validation. ModelDeck may schedule its own Workers on private ports; SceneChat never addresses them directly.
- `services/analysis.py` limits analysis to one request, applies a timeout, validates output, and rejects stale successes and failures by comparing state generations and provider selection.
- `services/state.py` is the shared, concurrency-safe state boundary. Detector prompt changes also use one application-level lock so manual selection, session learning, reset restoration, and detector switching cannot interleave. Freshness is checked atomically before learned state is committed. The browser receives state through Server-Sent Events.
- The unified visitor/operator screen is dependency-free HTML, CSS, and JavaScript served by FastAPI. Its operator panel shares the same state stream as the visitor view, avoiding duplicate connections and a second build tool or process.

## Failure isolation

Provider failure leaves the previous valid description in place, exposes a sanitised staff error, and degrades a ModelDeck session to detector-only mode without changing the selected provider. Readiness distinguishes an unreachable gateway, an unpublished route, a Worker that is not ready, and missing capabilities. Repeated camera read failures terminate capture, clear the in-memory frame and detections, and prompt the operator to reconnect and restart; replay remains available. The privacy flag hides the `/api/frame` response and public visual immediately and invalidates an in-flight result. Reset never waits for model completion.

## Runtime ownership

SceneChat serves its unified visitor/operator interface, API, session state, privacy controls, reset flow, replay assets, and demo health information from `127.0.0.1:3700`. ModelDeck owns management on `127.0.0.1:3600`, its gateway on `127.0.0.1:8600`, and all Worker lifecycle and private routing. There is no SceneChat model adapter process, Worker credential or extra port.

## Data handling

Frames exist only in camera and request memory. They are not written to disk, included in logs, or cached by browsers. Learned detector vocabulary is session memory only; rejected raw labels are neither retained nor exposed, and only aggregate safe reason categories are counted. The committed replay asset is synthetic. Curated questions eliminate public arbitrary-prompt input.
