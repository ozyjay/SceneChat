# Architecture

```text
camera thread -> one latest JPEG -> detector adapter -> normalised boxes
                         |
                         +-> frame sampler -> VisionLanguageProvider (one request at a time)

validated state store -> SSE updates -> public screen
                                +-----> staff controls
```

## Boundaries

- `services/camera.py` owns camera resources on a background thread and retains only one encoded frame in memory. A newer frame replaces the older one.
- `detection/` contains a no-op adapter and an optional local YOLO adapter. Replay annotations use the same normalised `Detection` schema.
- `vision/` isolates mock, replay, and vLLM response formats behind one provider protocol.
- `services/analysis.py` limits analysis to one request, applies a timeout, validates output, and rejects a result after reset by comparing state generations.
- `services/state.py` is the shared, concurrency-safe state boundary. The browser receives state through Server-Sent Events.
- The public and staff screens are dependency-free HTML, CSS, and JavaScript served by FastAPI. This avoids a second build tool and process for the initial deployment.

## Failure isolation

Provider failure leaves the previous valid description in place, exposes a concise staff error, and degrades a vLLM session to detector-only mode. Camera failure does not affect replay. The privacy flag hides the `/api/frame` response and public visual immediately. Reset never waits for model completion.

## Data handling

Frames exist only in camera and request memory. They are not written to disk, included in logs, or cached by browsers. The committed replay asset is synthetic. Curated questions eliminate public arbitrary-prompt input.

