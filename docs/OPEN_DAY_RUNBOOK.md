# Open Day runbook

## Cold start

1. Confirm signs are visible and the camera points only into the demonstration area.
2. Confirm ModelDeck management at `http://127.0.0.1:3600` and its gateway at `http://127.0.0.1:8600` when using the live provider. ModelDeck, not SceneChat, owns worker start-up.
3. Run `pwsh -NoProfile -File scripts/run.ps1`. It starts the demo in the background and exits; runtime mode, provider, detectors, and fallback are controlled only by `.env`.
4. Open `http://127.0.0.1:3700/`, expand **Operator controls**, and confirm health, mode, camera, provider and latency. Collapse the panel and use the same page full-screen for visitors.

## Camera and live mode

In **Operator controls**, select the named camera and, when configured, the allowlisted object detector model. Start the camera and confirm the live image and camera processing rate. Select **live** and `modeldeck`. The no-detector configuration must show no object boxes or detector claims. Detector switching briefly pauses and restarts the camera. Do not troubleshoot in front of a visitor for more than 30 seconds; explicitly switch to fallback instead.

For YOLOE or YOLO-World, select a small approved prompt set before opening. Enable automatic prompt updates only after confirming that Gemma's structured object labels remain suitable. The base prompts are restored whenever a new scene analysis does not return additional approved labels; reset continues to clear visitor-facing generated text but does not change the operator's detector configuration.

## Between visitors

Select **Reset session**. Confirm the public description is cleared. Reset must complete within five seconds and no prior generated text should return.

## Fallbacks

- **ModelDeck unavailable:** choose **Disable scene analysis** for camera-only operation, or explicitly select `fallback`/`replay` and replay mode.
- **Camera unavailable:** stop the camera, choose **replay** mode, **replay** provider, and the prepared scenario.
- **Both unavailable/offline:** use replay; it needs neither service.
- **Privacy request or unsafe framing:** select **Hide camera now** immediately. Restore only after the issue is resolved and consent/signage conditions are satisfied.

## Recovery checks

For a model failure, verify ModelDeck management and `http://127.0.0.1:8600/v1/models` outside the public view, then manually reselect `modeldeck`. Never enter or call a worker port (`8610–8699`) from SceneChat. There is no cloud or live-provider failover. For camera failure, stop it before reconnecting, verify the device, then start it again. Replay stays available throughout.

## Shutdown

1. Activate the privacy screen.
2. Reset the session and confirm temporary visitor-facing text is cleared.
3. Run `pwsh -NoProfile -File scripts/stop.ps1`.
4. Confirm the camera indicator is off and no visitor media exists on disk.
5. Leave ModelDeck worker shutdown to the separate ModelDeck operating procedure.
