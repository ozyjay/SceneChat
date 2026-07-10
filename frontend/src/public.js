const state = { questions: [], current: null, detectorEnabled: true };
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
}

async function analyse(question) {
  try {
    await request('/api/analyse', {method: 'POST', body: JSON.stringify({question})});
  } catch (error) { showToast(error.message); }
}

async function initialise() {
  const config = await request('/api/config');
  state.questions = config.questions;
  state.detectorEnabled = config.detector_enabled;
  const buttons = $('questionButtons');
  for (const question of config.questions) {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = question; button.dataset.question = question;
    button.addEventListener('click', () => analyse(question));
    buttons.append(button);
  }
  render(await request('/api/state'));
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
}

initialise().catch((error) => showToast(error.message));
