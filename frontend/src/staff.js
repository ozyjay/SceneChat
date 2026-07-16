const $ = (id) => document.getElementById(id);
let currentState = null;

function showToast(message) {
  const toast = $('toast'); toast.textContent = message; toast.classList.add('show');
  window.setTimeout(() => toast.classList.remove('show'), 3500);
}
async function request(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'The request could not be completed.');
  return payload;
}
async function post(path, body) { return request(path, {method: 'POST', body: body === undefined ? undefined : JSON.stringify(body)}); }

function render(state) {
  currentState = state;
  $('modeValue').textContent = state.internal_mode;
  $('cameraValue').textContent = state.camera_running ? `Running on device ${state.camera_device}` : 'Stopped';
  $('fpsValue').textContent = state.camera_running ? `${state.detector_fps.toFixed(1)} FPS` : '—';
  $('providerValue').textContent = `${state.provider} · ${state.provider_available ? 'available' : 'unavailable'}`;
  $('latencyValue').textContent = state.last_model_latency_ms === null ? '—' : `${state.last_model_latency_ms.toFixed(0)} ms`;
  $('analysisValue').textContent = state.analysis_in_progress ? 'Running' : 'Idle';
  $('autoEnabled').checked = state.auto_analyse;
  $('autoInterval').value = state.auto_analyse_interval_seconds;
  $('cameraDevice').value = state.camera_device;
  $('staffError').hidden = !state.staff_error;
  $('staffError').textContent = state.staff_error || '';
}

async function act(action, success) {
  try { const result = await action(); if (result?.revision !== undefined) render(result); if (success) showToast(success); }
  catch (error) { showToast(error.message); }
}

async function initialise() {
  const [config, initial, health] = await Promise.all([request('/api/config'), request('/api/state'), request('/api/health')]);
  for (const mode of config.modes) $('modeSelect').add(new Option(mode, mode));
  for (const provider of config.providers) $('providerSelect').add(new Option(provider, provider));
  for (const scenario of config.scenarios) $('scenarioSelect').add(new Option(scenario.title, scenario.id));
  for (const question of config.questions) $('questionSelect').add(new Option(question, question));
  const cameras = config.camera_devices || [{
    device: initial.camera_device,
    label: `Camera ${initial.camera_device}`,
  }];
  for (const camera of cameras) $('cameraDevice').add(new Option(camera.label, camera.device));
  $('modeSelect').value = initial.internal_mode; $('providerSelect').value = initial.provider; $('scenarioSelect').value = initial.replay_scenario;
  render(initial); $('healthValue').textContent = health.status;
  const events = new EventSource('/api/events'); events.onmessage = (event) => render(JSON.parse(event.data));

  $('privacyOn').onclick = () => act(() => post('/api/privacy', {enabled: true}), 'Privacy screen activated.');
  $('privacyOff').onclick = () => act(() => post('/api/privacy', {enabled: false}), 'Public camera view restored.');
  $('resetSession').onclick = () => act(() => post('/api/reset'), 'Session reset and generated text cleared.');
  $('detectorOnly').onclick = () => act(() => post('/api/mode', {mode: 'detector-only'}), 'Scene analysis disabled; camera fallback active.');
  $('applyMode').onclick = () => act(async () => {
    await post('/api/replay', {scenario: $('scenarioSelect').value});
    await post('/api/mode', {mode: $('modeSelect').value});
    return post('/api/provider', {provider: $('providerSelect').value});
  }, 'Mode and provider updated.');
  $('startCamera').onclick = () => act(() => post('/api/camera/start', {device: Number($('cameraDevice').value)}), 'Camera start requested.');
  $('stopCamera').onclick = () => act(() => post('/api/camera/stop'), 'Camera stopped.');
  $('triggerAnalysis').onclick = () => act(() => post('/api/analyse', {question: $('questionSelect').value}), 'Scene description updated.');
  $('clearAnalysis').onclick = () => act(() => post('/api/analysis/clear'), 'Scene description cleared.');
  $('applyAuto').onclick = () => act(() => post('/api/auto-analyse', {enabled: $('autoEnabled').checked, interval_seconds: Number($('autoInterval').value)}), 'Automatic schedule updated.');
  async function updateHealth() {
    try {
      const [result, memory] = await Promise.all([request('/api/health'), request('/api/diagnostics')]);
      $('healthValue').textContent = result.status;
      $('processMemoryValue').textContent = `${memory.process_max_rss_mb.toFixed(1)} MiB`;
      $('systemMemoryValue').textContent = memory.system_available_mb === null ? '—' : `${memory.system_available_mb.toFixed(0)} MiB`;
    } catch { $('healthValue').textContent = 'Unavailable'; }
  }
  await updateHealth();
  window.setInterval(updateHealth, 5000);
}
initialise().catch((error) => showToast(error.message));
