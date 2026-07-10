# Open Day runbook

## Cold start

1. Confirm signs are visible and the camera points only into the demonstration area.
2. Run `./scripts/check_environment.sh` and `./scripts/check_ports.sh`.
3. Start the already-tested local model service only if Gemma 4 passed the compatibility gate.
4. Start `./scripts/run_live.sh`, or `./scripts/run_replay.sh` for the guaranteed offline demonstration.
5. Open `/staff`; confirm health, mode, camera, provider and latency. Open `/` full-screen.

## Camera and live mode

Select the device number in `/staff`, start the camera, and confirm the live image and detector FPS. Select **live** and the approved provider. Do not troubleshoot in front of a visitor for more than 30 seconds; switch fallback instead.

## Between visitors

Select **Reset session**. Confirm the public description is cleared. Reset must complete within five seconds and no prior generated text should return.

## Fallbacks

- **Model unavailable:** choose **Detector only**. The live boxes continue without scene descriptions.
- **Camera unavailable:** stop the camera, choose **replay** mode, **replay** provider, and the prepared scenario.
- **Both unavailable/offline:** use replay; it needs neither service.
- **Privacy request or unsafe framing:** select **Hide camera now** immediately. Restore only after the issue is resolved and consent/signage conditions are satisfied.

## Recovery checks

For a model failure, verify the local vLLM `/v1/models` endpoint, check the model service outside the public view, then manually reselect `vllm`. There is no cloud failover. For camera failure, stop it before reconnecting, verify the device, then start it again. Replay stays available throughout.

## Shutdown

1. Activate the privacy screen.
2. Reset the session and confirm temporary visitor-facing text is cleared.
3. Run `./scripts/stop.sh` or stop the service gracefully from its terminal.
4. Stop the vLLM container.
5. Confirm the camera indicator is off and no visitor media exists on disk.

