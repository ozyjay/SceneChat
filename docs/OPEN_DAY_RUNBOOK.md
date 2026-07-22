# Open Day runbook

## Cold start

1. Confirm signs are visible and the camera points only into the demonstration area.
2. In the ModelDeck repository, run `pwsh -NoProfile -File scripts/check_ports.ps1` and `pwsh -NoProfile -File scripts/check_environment.ps1`.
3. In that repository, run `pwsh -NoProfile -File scripts/run.ps1 -OpenDay`, then open `http://127.0.0.1:3600`.
4. Start the prepared Qwen3.5 0.8B mock Worker. Confirm its 280-visual-token budget, then wait for **ready**. ModelDeck owns discovery, credentials, Worker lifecycle and routing.
5. Return to this repository and run `pwsh -NoProfile -File scripts/check_modeldeck.ps1`. It checks only the gateway on port `8600`, the `scenechat-vision` route, `image_input`, `structured_output`, readiness and disabled cloud fallback.
6. Run `pwsh -NoProfile -File scripts/run.ps1`. It starts SceneChat in the background and exits. A failed ModelDeck preflight produces a warning but does not block camera-only, replay or mock operation.
7. Open `http://127.0.0.1:3700/`, expand **Operator controls**, select **Check provider readiness**, and confirm health, mode, camera, provider and latency. Collapse the panel and use the same page full-screen for visitors.

SceneChat has no ModelDeck Worker credential. Never copy `MODELDECK_SCENECHAT_API_KEY` or any other ModelDeck secret into SceneChat.

## Camera and live mode

In **Operator controls**, select the named camera and, when configured, the allowlisted object detector model. Start the camera and confirm the live image and camera processing rate. Select `modeldeck`, confirm **ModelDeck · scenechat-vision · available**, then select **live**. The no-detector configuration must show no object boxes or detector claims. Detector switching briefly pauses and restarts the camera. Do not troubleshoot in front of a visitor for more than 30 seconds; explicitly switch to fallback instead.

For YOLOE or YOLO-World, choose an object preset or a small approved prompt set before opening. This becomes the protected operator baseline. If **Learn safe objects from scene analysis this session** is enabled, structured object labels may be appended automatically after conservative filtering, including labels outside the manual allowlist. Review the separate operator-selected and scene-learned lists and their aggregate blocked/capacity counts. Use **Clear learned objects** to retain the scene description while restoring the baseline. **Reset session** also clears learned objects and counters while preserving the latest operator baseline.

When enabling automatic scene analysis, choose its curated question pool and an interval of at least 20 seconds. Confirm that successive requests rotate randomly through that pool. The scheduler avoids an immediate repeat when multiple questions are available and pauses while the camera is stopped or the privacy screen is active. Starting the camera resumes the schedule with a fresh interval countdown.

## Between visitors

Select **Reset session**. Confirm the public description and scene-learned detector objects are cleared and the operator baseline is active. Reset must complete within five seconds and no prior generated text or stale learned object should return.

## Fallbacks

- **ModelDeck unavailable or Worker not ready:** start/recover the Worker only in ModelDeck. In SceneChat, choose **Disable scene analysis** for camera-only operation, or explicitly select `fallback`/`replay` and replay mode.
- **Camera unavailable:** stop the camera, choose **replay** mode, **replay** provider, and the prepared scenario.
- **Both unavailable/offline:** use replay; it needs neither service.
- **Privacy request or unsafe framing:** select **Hide camera now** immediately. Restore only after the issue is resolved and consent/signage conditions are satisfied.

## Recovery checks

For a model failure, inspect ModelDeck outside public view, start or recover the prepared Worker there, wait for ready, run `scripts/check_modeldeck.ps1`, then select **Check provider readiness** in SceneChat. Reapply `live` mode only after readiness succeeds. Never enter or call a Worker port from SceneChat. There is no cloud or provider failover. For camera failure, stop it before reconnecting, verify the device, then start it again. Replay stays available throughout.

## Shutdown

1. Activate the privacy screen.
2. Reset the session and confirm temporary visitor-facing text is cleared.
3. Run `pwsh -NoProfile -File scripts/stop.ps1`.
4. Confirm the camera indicator is off and no visitor media exists on disk.
5. Leave Worker and ModelDeck shutdown to the separate ModelDeck operating procedure. SceneChat never stops them.
