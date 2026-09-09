# ModelDeck configuration qualification

Use ModelDeck's frozen SceneChat corpus and isolated evaluation route. Physical checks
require an approved maintenance window and non-visitor images. Keep the provider interface,
seven curated questions and output validator unchanged.

Scene analysis now carries an opaque `analysis_request_id` and `application_elapsed_ms`.
The latter measures application orchestration through sanitisation, before state publication;
it is not a display measurement. For manual public question buttons, the browser emits
`scenechat-analysis-displayed` after two animation frames, with only the request ID,
duration and measurement label. The duration includes the request, state refresh and display.
Reset, privacy holding and superseded results prevent the event. No event is uploaded or
persisted by the application. Automatic-analysis and operator-panel display timings remain
unavailable until independently instrumented; do not substitute backend latency for them.

Run the offline suite using PowerShell and `.venv/bin/python -m pytest -m "not hardware"`.
Use the existing `benchmarks/run.ps1` hardware acceptance checks for schema, latency,
reset and privacy. During combined-load qualification additionally record detector FPS
before and during load, timeout/disconnect/cancellation recovery, offline restart and unload.
Cancellation must release Worker occupancy within two seconds or leave it unavailable
until recovery. These physical observations must be supplied to the qualification receipt;
passing offline tests does not establish them.
