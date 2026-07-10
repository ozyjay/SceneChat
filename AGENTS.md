# SceneChat contributor instructions

## Purpose

SceneChat is a local-first public Open Day demonstration. It combines a fast object detector with a separately scheduled multimodal scene-description provider. Reliability, clear public wording, privacy, quick reset, and offline fallback operation take priority over feature count.

## Architecture constraints

- Keep camera capture and continuous detection separate from scene analysis.
- Keep camera work off the asynchronous event loop and use bounded, latest-frame queues.
- Permit no more than one scene-analysis request at a time. Ignore results made stale by reset or a newer request.
- Access multimodal models only through the `VisionLanguageProvider` interface.
- Keep detector-only, deterministic mock, replay, and privacy-holding modes operational without a model server.
- Do not add an automatic cloud fallback. External providers require explicit configuration, approval, and signage.
- Prefer small, incremental changes and avoid unnecessary dependencies.

## Privacy and safety

- Do not store visitor images, video, or audio by default.
- Do not log raw frames or identifying visitor text.
- Do not implement face recognition, person identification, persistent tracking, age or emotion estimation, or inference of ethnicity, religion, health, disability, sexuality, criminality, or other sensitive attributes.
- Use generic terms such as “a person”. Treat model output as untrusted and validate it before display.
- The privacy screen must hide the feed immediately. Reset must clear generated visitor-facing text and invalidate in-flight analysis.

## Implementation and tests

- Preserve fallback behaviour in every phase.
- Add or update tests for changed behaviour, especially configuration, prompt safeguards, response parsing, stale-result rejection, reset, and failure degradation.
- Run the focused unit tests and the offline test suite before reporting completion.
- Hardware and large-model tests must remain explicitly optional.

