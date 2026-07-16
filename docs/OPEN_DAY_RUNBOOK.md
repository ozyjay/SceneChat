# Open Day runbook

## Cold start

1. Confirm signs are visible and the camera points only into the demonstration area.
2. Run `pwsh -NoProfile -File scripts/check_environment.ps1` and `pwsh -NoProfile -File scripts/check_ports.ps1`.
3. If using a live model, confirm ModelDeck management at `http://127.0.0.1:3600` and its gateway at `http://127.0.0.1:8600`. ModelDeck, not SceneChat, owns worker start-up.
4. Start `pwsh -NoProfile -File scripts/run_modeldeck.ps1` for the live path, or `pwsh -NoProfile -File scripts/run_replay.ps1` for the guaranteed offline demonstration.
5. Open `http://127.0.0.1:3700/staff`; confirm health, mode, camera, provider and latency. Open `http://127.0.0.1:3700/` full-screen.

## Camera and live mode

Select the device number in `/staff`, start the camera, and confirm the live image and camera processing rate. Select **live** and `modeldeck`. The no-detector configuration must show no object boxes or detector claims. Do not troubleshoot in front of a visitor for more than 30 seconds; explicitly switch to fallback instead.

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
3. Run `pwsh -NoProfile -File scripts/stop.ps1` or stop the service gracefully from its terminal.
4. Confirm the camera indicator is off and no visitor media exists on disk.
5. Leave ModelDeck worker shutdown to the separate ModelDeck operating procedure.
