const state = {
  questions: [],
  current: null,
  detectorEnabled: true,
  cameraLabels: new Map(),
};
const $ = (id) => document.getElementById(id);

function showToast(message) {
  const toast = $('toast');
  toast.textContent = message;
  toast.classList.add('show');
  window.setTimeout(() => toast.classList.remove('show'), 3200);
}

async function request(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || 'The request could not be completed.');
  }
  return response.json();
}

async function post(path, body) {
  return request(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

function renderDetections(detections) {
  const layer = $('detectionLayer');
  layer.replaceChildren();
  for (const detection of detections) {
    const box = document.createElement('div');
    box.className = 'detection-box';
    box.style.left = `${detection.x * 100}%`;
    box.style.top = `${detection.y * 100}%`;
    box.style.width = `${detection.width * 100}%`;
    box.style.height = `${detection.height * 100}%`;
    const label = document.createElement('span');
    label.textContent = `${detection.label} · about ${Math.round(detection.confidence * 100)}%`;
    box.append(label);
    layer.append(box);
  }
}

function renderCounts(detections) {
  if (!state.detectorEnabled) {
    $('detectionSummary').textContent = 'Live camera · object detection off';
    const panel = $('objectCounts');
    panel.replaceChildren();
    const empty = document.createElement('span');
    empty.className = 'muted';
    empty.textContent = 'Object detection is not enabled';
    panel.append(empty);
    return;
  }
  const counts = detections.reduce((result, item) => {
    result[item.label] = (result[item.label] || 0) + 1;
    return result;
  }, {});
  $('objectTotal').textContent = detections.length;
  $('detectionSummary').replaceChildren();
  const total = document.createElement('strong');
  total.id = 'objectTotal';
  total.textContent = detections.length;
  $('detectionSummary').append(total, ' objects currently highlighted');
  const panel = $('objectCounts');
  panel.replaceChildren();
  for (const [label, count] of Object.entries(counts)) {
    const chip = document.createElement('span');
    chip.className = 'count-chip';
    chip.textContent = `${label} ${count}`;
    panel.append(chip);
  }
  if (!detections.length) {
    const empty = document.createElement('span');
    empty.className = 'muted';
    empty.textContent = 'No current detections';
    panel.append(empty);
  }
}

function renderOperator(next) {
  $('modeValue').textContent = next.internal_mode;
  const cameraLabel = state.cameraLabels.get(String(next.camera_device)) || `Camera ${next.camera_device}`;
  $('cameraValue').textContent = next.camera_running ? `Running · ${cameraLabel}` : 'Stopped';
  $('fpsValue').textContent = next.camera_running ? `${next.detector_fps.toFixed(1)} FPS` : '—';
  $('detectorValue').textContent = next.detector_model || next.detector_backend;
  if (next.detector_model && document.activeElement !== $('detectorModelSelect')) {
    $('detectorModelSelect').value = next.detector_model;
  }
  $('providerValue').textContent = `${next.provider} · ${next.provider_available ? 'available' : 'unavailable'}`;
  $('latencyValue').textContent = next.last_model_latency_ms === null ? '—' : `${next.last_model_latency_ms.toFixed(0)} ms`;
  $('analysisValue').textContent = next.analysis_in_progress ? 'Running' : 'Idle';
  if (document.activeElement !== $('autoEnabled')) $('autoEnabled').checked = next.auto_analyse;
  if (document.activeElement !== $('autoInterval')) $('autoInterval').value = next.auto_analyse_interval_seconds;
  if (next.camera_running) {
    const activeCamera = document.querySelector(`input[name="cameraDevice"][value="${next.camera_device}"]`);
    if (activeCamera) activeCamera.checked = true;
  }
  $('privacyOn').disabled = next.privacy_screen;
  $('privacyOff').disabled = !next.privacy_screen;
  $('staffError').hidden = !next.staff_error;
  $('staffError').textContent = next.staff_error || '';
}

function render(next) {
  state.current = next;
  $('modeBadge').textContent = next.mode;
  $('privacyHolding').hidden = !next.privacy_screen;
  $('sceneImage').hidden = next.privacy_screen;
  $('detectionLayer').hidden = next.privacy_screen;
  renderDetections(next.privacy_screen ? [] : next.detections);
  renderCounts(next.privacy_screen ? [] : next.detections);
  const analysis = next.scene_analysis;
  $('sceneSummary').textContent = analysis?.summary || 'Choose a question to generate a scene description.';
  $('analysisTime').textContent = analysis
    ? `Description updated ${new Date(analysis.generated_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'})}`
    : 'No scene description yet';
  const uncertaintyPanel = $('uncertaintyPanel');
  const list = $('uncertainties');
  list.replaceChildren();
  uncertaintyPanel.hidden = !analysis?.uncertainties?.length;
  for (const uncertainty of analysis?.uncertainties || []) {
    const item = document.createElement('li'); item.textContent = uncertainty; list.append(item);
  }
  document.querySelectorAll('.question-grid button').forEach((button) => {
    button.disabled = next.analysis_in_progress || next.internal_mode === 'detector-only';
    button.classList.toggle('active', button.dataset.question === next.selected_question);
  });
  renderOperator(next);
}

async function analyse(question) {
  try {
    await request('/api/analyse', {method: 'POST', body: JSON.stringify({question})});
  } catch (error) { showToast(error.message); }
}

async function act(action, success) {
  try {
    const result = await action();
    if (result?.revision !== undefined) render(result);
    if (success) showToast(success);
  } catch (error) {
    showToast(error.message);
  }
}

function populateOperatorControls(config, initial) {
  for (const mode of config.modes) $('modeSelect').add(new Option(mode, mode));
  for (const provider of config.providers) $('providerSelect').add(new Option(provider, provider));
  for (const scenario of config.scenarios) $('scenarioSelect').add(new Option(scenario.title, scenario.id));
  for (const question of config.questions) $('questionSelect').add(new Option(question, question));
  const detectorModels = config.detector_models || [];
  $('detectorModelControls').hidden = detectorModels.length === 0;
  for (const model of detectorModels) {
    $('detectorModelSelect').add(new Option(model.label, model.id));
  }
  $('detectorModelSelect').value = initial.detector_model || '';
  $('applyDetectorModel').disabled = detectorModels.length < 2;

  const cameras = config.camera_devices || [{
    device: initial.camera_device,
    label: `Camera ${initial.camera_device}`,
  }];
  for (const camera of cameras) {
    state.cameraLabels.set(String(camera.device), camera.label);
    const label = document.createElement('label');
    label.className = 'camera-choice';
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = 'cameraDevice';
    input.value = camera.device;
    input.checked = camera.device === initial.camera_device;
    const name = document.createElement('span');
    name.textContent = camera.label;
    label.append(input, name);
    $('cameraChoices').append(label);
  }

  $('modeSelect').value = initial.internal_mode;
  $('providerSelect').value = initial.provider;
  $('scenarioSelect').value = initial.replay_scenario;

  $('privacyOn').onclick = () => act(() => post('/api/privacy', {enabled: true}), 'Privacy screen activated.');
  $('privacyOff').onclick = () => act(() => post('/api/privacy', {enabled: false}), 'Public camera view restored.');
  $('resetSession').onclick = () => act(() => post('/api/reset'), 'Session reset and generated text cleared.');
  $('detectorOnly').onclick = () => act(() => post('/api/mode', {mode: 'detector-only'}), 'Scene analysis disabled; camera fallback active.');
  $('applyMode').onclick = () => act(async () => {
    await post('/api/replay', {scenario: $('scenarioSelect').value});
    await post('/api/mode', {mode: $('modeSelect').value});
    return post('/api/provider', {provider: $('providerSelect').value});
  }, 'Mode and provider updated.');
  $('startCamera').onclick = () => act(() => {
    const selected = document.querySelector('input[name="cameraDevice"]:checked');
    if (!selected) throw new Error('Choose a camera first.');
    return post('/api/camera/start', {device: Number(selected.value)});
  }, 'Camera start requested.');
  $('stopCamera').onclick = () => act(() => post('/api/camera/stop'), 'Camera stopped.');
  $('applyDetectorModel').onclick = () => act(
    () => post('/api/detector/model', {model: $('detectorModelSelect').value}),
    'Object detector model switched.',
  );
  $('triggerAnalysis').onclick = () => act(() => post('/api/analyse', {question: $('questionSelect').value}), 'Scene description updated.');
  $('clearAnalysis').onclick = () => act(() => post('/api/analysis/clear'), 'Scene description cleared.');
  $('applyAuto').onclick = () => act(() => post('/api/auto-analyse', {
    enabled: $('autoEnabled').checked,
    interval_seconds: Number($('autoInterval').value),
  }), 'Automatic schedule updated.');
}

async function updateHealth() {
  try {
    const [health, memory] = await Promise.all([request('/api/health'), request('/api/diagnostics')]);
    $('healthValue').textContent = health.status;
    $('processMemoryValue').textContent = `${memory.process_max_rss_mb.toFixed(1)} MiB`;
    $('systemMemoryValue').textContent = memory.system_available_mb === null ? '—' : `${memory.system_available_mb.toFixed(0)} MiB`;
  } catch {
    $('healthValue').textContent = 'Unavailable';
  }
}

function revealOperatorControls() {
  if (window.location.hash !== '#operator-controls') return;
  const controls = $('operator-controls');
  controls.open = true;
  controls.scrollIntoView({block: 'start'});
}

async function initialise() {
  const [config, initial] = await Promise.all([request('/api/config'), request('/api/state')]);
  state.questions = config.questions;
  state.detectorEnabled = config.detector_enabled;
  const buttons = $('questionButtons');
  for (const question of config.questions) {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = question; button.dataset.question = question;
    button.addEventListener('click', () => analyse(question));
    buttons.append(button);
  }
  populateOperatorControls(config, initial);
  render(initial);
  const events = new EventSource('/api/events');
  events.onmessage = (event) => render(JSON.parse(event.data));
  $('resetButton').addEventListener('click', async () => {
    try { render(await request('/api/reset', {method: 'POST'})); showToast('SceneChat is ready for the next visitor.'); }
    catch (error) { showToast(error.message); }
  });
  window.setInterval(() => {
    if (state.current?.camera_running && !state.current?.privacy_screen) {
      $('sceneImage').src = `/api/frame?t=${Date.now()}`;
    }
  }, 180);
  await updateHealth();
  window.setInterval(updateHealth, 5000);
  $('operatorControlsLink').addEventListener('click', () => {
    $('operator-controls').open = true;
  });
  revealOperatorControls();
  window.addEventListener('hashchange', revealOperatorControls);
}

initialise().catch((error) => showToast(error.message));
