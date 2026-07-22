const state = {
  questions: [],
  current: null,
  detectorEnabled: true,
  cameraLabels: new Map(),
  toastTimer: null,
};
const detectorPromptPresets = {
  essentials: ['person', 'laptop', 'monitor', 'microphone', 'camera'],
  technology: ['computer mouse', 'keyboard', 'laptop', 'monitor', 'mobile phone', 'headphones'],
  room: ['person', 'chair', 'table', 'book', 'backpack', 'bottle', 'cup', 'potted plant'],
};
const promptLearningReasonLabels = {
  invalid_shape: 'malformed labels',
  human_or_identity: 'human or identity descriptions',
  sensitive_trait: 'sensitive traits',
  medical_or_assistive: 'medical or assistive items',
  religious_or_political: 'religious or political items',
  intimate: 'intimate items',
  weapon_or_drug: 'weapons or regulated substances',
  model_safety_note: 'model safety notes',
};
const $ = (id) => document.getElementById(id);

function showToast(message) {
  const operatorToast = $('operatorToast');
  const publicToast = $('toast');
  const toast = $('operator-controls').open ? operatorToast : publicToast;
  const otherToast = toast === operatorToast ? publicToast : operatorToast;
  otherToast.classList.remove('show');
  toast.textContent = message;
  toast.classList.add('show');
  window.clearTimeout(state.toastTimer);
  state.toastTimer = window.setTimeout(() => toast.classList.remove('show'), 5500);
}

function formatErrorDetail(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map(item => item?.msg || String(item)).join(' ');
  }
  return detail?.message || 'The request could not be completed.';
}

async function request(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(formatErrorDetail(payload.detail));
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
    $('detectorLegend').hidden = true;
    const panel = $('objectCounts');
    panel.replaceChildren();
    const empty = document.createElement('span');
    empty.className = 'muted';
    empty.textContent = 'Object detection is not enabled';
    panel.append(empty);
    return;
  }
  $('detectorLegend').hidden = state.current?.privacy_screen;
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

function renderAnalysisObjects(analysis) {
  const panel = $('analysisObjects');
  panel.replaceChildren();
  for (const object of analysis?.objects || []) {
    const chip = document.createElement('span');
    chip.className = 'scene-model-object';
    chip.textContent = object.label;
    chip.title = `${object.description} Location: ${object.approximate_location}`;
    panel.append(chip);
  }
  if (!analysis?.objects?.length) {
    const empty = document.createElement('span');
    empty.className = 'muted';
    empty.textContent = analysis
      ? 'The scene model did not return any structured objects'
      : 'No scene description yet';
    panel.append(empty);
  }
}

function selectedDetectorPrompts() {
  return Array.from(
    document.querySelectorAll('input[name="detectorPrompt"]:checked'),
    input => input.value,
  );
}

function updateDetectorPromptToggle() {
  const inputs = Array.from(document.querySelectorAll('input[name="detectorPrompt"]'));
  const selectedCount = inputs.filter(input => input.checked).length;
  $('detectorPromptSelectionCount').textContent = `${selectedCount} of ${inputs.length} selected`;
  $('selectAllDetectorPrompts').disabled = inputs.length === 0 || selectedCount === inputs.length;
  $('clearAllDetectorPrompts').disabled = selectedCount === 0;
}

function detectorPromptSelectionChanged() {
  updatePromptPending();
  updateDetectorPromptToggle();
}

function setAllDetectorPrompts(checked) {
  const inputs = Array.from(document.querySelectorAll('input[name="detectorPrompt"]'));
  for (const input of inputs) input.checked = checked;
  detectorPromptSelectionChanged();
}

function applyDetectorPromptPreset(presetName) {
  const prompts = new Set(detectorPromptPresets[presetName] || []);
  for (const input of document.querySelectorAll('input[name="detectorPrompt"]')) {
    input.checked = prompts.has(input.value);
  }
  detectorPromptSelectionChanged();
}

function selectedAutoQuestions() {
  return Array.from(
    document.querySelectorAll('input[name="autoQuestion"]:checked'),
    input => input.value,
  );
}

function updateAutoQuestionControls() {
  const inputs = Array.from(document.querySelectorAll('input[name="autoQuestion"]'));
  const selectedCount = inputs.filter(input => input.checked).length;
  $('autoQuestionSelectionCount').textContent = `${selectedCount} of ${inputs.length} selected`;
  $('selectAllAutoQuestions').disabled = inputs.length === 0 || selectedCount === inputs.length;
  $('clearAllAutoQuestions').disabled = selectedCount === 0;
}

function updateAutoSchedulePending() {
  const selected = selectedAutoQuestions();
  const active = new Set(state.current?.auto_analyse_questions || []);
  const questionsChanged = selected.length !== active.size
    || selected.some(question => !active.has(question));
  const changed = $('autoEnabled').checked !== state.current?.auto_analyse
    || Number($('autoInterval').value) !== state.current?.auto_analyse_interval_seconds
    || questionsChanged;
  const pending = $('autoSchedulePending');
  pending.hidden = !changed;
  pending.textContent = selected.length
    ? 'Schedule changed — apply it to activate these settings.'
    : 'Choose at least one automatic question before applying.';
  $('applyAuto').disabled = selected.length === 0;
}

function autoScheduleSelectionChanged() {
  updateAutoQuestionControls();
  updateAutoSchedulePending();
}

function setAllAutoQuestions(checked) {
  for (const input of document.querySelectorAll('input[name="autoQuestion"]')) {
    input.checked = checked;
  }
  autoScheduleSelectionChanged();
}

function renderActivePrompts(prompts) {
  const panel = $('activePromptChips');
  panel.replaceChildren();
  for (const prompt of prompts) {
    const chip = document.createElement('span');
    chip.className = 'active-prompt-chip';
    chip.textContent = prompt;
    panel.append(chip);
  }
  if (!prompts.length) {
    const empty = document.createElement('span');
    empty.className = 'muted';
    empty.textContent = 'No active prompts';
    panel.append(empty);
  }
}

function renderLearnedPrompts(next) {
  const panel = $('learnedPromptChips');
  panel.replaceChildren();
  for (const prompt of next.detector_learned_prompts || []) {
    const chip = document.createElement('span');
    chip.className = 'learned-prompt-chip';
    chip.textContent = prompt;
    panel.append(chip);
  }
  if (!next.detector_learned_prompts?.length) {
    const empty = document.createElement('span');
    empty.className = 'muted';
    empty.textContent = 'No objects learned this session';
    panel.append(empty);
  }
  $('clearLearnedPrompts').disabled = !next.detector_learned_prompts?.length;
  const status = [
    `${next.detector_learned_prompts?.length || 0} learned`,
    `${next.detector_prompt_safety_rejections || 0} blocked by safety policy`,
  ];
  if (next.detector_prompt_capacity_skips) {
    status.push(`${next.detector_prompt_capacity_skips} skipped at capacity`);
  }
  const reasons = Object.entries(next.detector_prompt_rejection_reasons || {})
    .filter(([, count]) => count)
    .map(([reason, count]) => `${promptLearningReasonLabels[reason] || 'other safety checks'}: ${count}`);
  if (reasons.length) status.push(`Blocked categories — ${reasons.join(', ')}`);
  $('promptLearningStatus').textContent = status.join(' · ');
}

function updatePromptPending() {
  const active = new Set(state.current?.detector_prompt_baseline || []);
  const selected = selectedDetectorPrompts();
  const changed = selected.length !== active.size
    || selected.some(prompt => !active.has(prompt))
    || $('detectorPromptAutoUpdate').checked !== state.current?.detector_prompt_auto_update;
  const pending = $('detectorPromptPending');
  pending.hidden = !changed;
  pending.textContent = selected.length
    ? 'Selection changed — apply prompts to activate it.'
    : 'Choose at least one object before applying prompts.';
  $('applyDetectorPrompts').disabled = selected.length === 0;
}

function renderOperator(next) {
  $('modeValue').textContent = next.internal_mode;
  if (document.activeElement !== $('modeSelect')) $('modeSelect').value = next.internal_mode;
  if (document.activeElement !== $('providerSelect')) $('providerSelect').value = next.provider;
  if (document.activeElement !== $('scenarioSelect')) $('scenarioSelect').value = next.replay_scenario;
  const cameraLabel = state.cameraLabels.get(String(next.camera_device)) || `Camera ${next.camera_device}`;
  $('cameraValue').textContent = next.camera_running ? `Running · ${cameraLabel}` : 'Stopped';
  $('fpsValue').textContent = next.camera_running ? `${next.detector_fps.toFixed(1)} FPS` : '—';
  $('detectorValue').textContent = next.detector_model || next.detector_backend;
  if (next.detector_model && document.activeElement !== $('detectorModelSelect')) {
    $('detectorModelSelect').value = next.detector_model;
  }
  const baselinePrompts = next.detector_prompt_baseline || [];
  renderActivePrompts(baselinePrompts);
  renderLearnedPrompts(next);
  const editingDetectorPrompts = document.activeElement?.name === 'detectorPrompt'
    || document.activeElement === $('selectAllDetectorPrompts')
    || document.activeElement === $('clearAllDetectorPrompts');
  if (!editingDetectorPrompts) {
    const activeSet = new Set(baselinePrompts);
    for (const input of document.querySelectorAll('input[name="detectorPrompt"]')) {
      input.checked = activeSet.has(input.value);
    }
  }
  updatePromptPending();
  updateDetectorPromptToggle();
  if (document.activeElement !== $('detectorPromptAutoUpdate')) {
    $('detectorPromptAutoUpdate').checked = next.detector_prompt_auto_update;
  }
  const editingAutoSchedule = document.activeElement === $('autoEnabled')
    || document.activeElement === $('autoInterval')
    || document.activeElement?.name === 'autoQuestion'
    || document.activeElement === $('selectAllAutoQuestions')
    || document.activeElement === $('clearAllAutoQuestions');
  if (!editingAutoSchedule) {
    $('autoEnabled').checked = next.auto_analyse;
    $('autoInterval').value = next.auto_analyse_interval_seconds;
    const activeQuestions = new Set(next.auto_analyse_questions || []);
    for (const input of document.querySelectorAll('input[name="autoQuestion"]')) {
      input.checked = activeQuestions.has(input.value);
    }
  }
  const questionCount = next.auto_analyse_questions?.length || 0;
  if (next.auto_analyse && !next.camera_running) {
    $('autoScheduleStatus').textContent = `Automatic analysis paused · start the camera to resume the ${next.auto_analyse_interval_seconds}-second schedule`;
  } else {
    $('autoScheduleStatus').textContent = next.auto_analyse
      ? `Automatic analysis on · every ${next.auto_analyse_interval_seconds} seconds · ${questionCount} questions in rotation`
      : 'Automatic analysis is off';
  }
  updateAutoQuestionControls();
  updateAutoSchedulePending();
  const providerName = next.provider === 'modeldeck' ? 'ModelDeck · scenechat-vision' : next.provider;
  $('providerValue').textContent = `${providerName} · ${next.provider_available ? 'available' : 'unavailable'}`;
  $('providerGuidance').textContent = next.provider === 'modeldeck'
    ? next.provider_status_message
    : `${providerName} is an explicit offline provider.`;
  $('latencyValue').textContent = next.last_model_latency_ms === null ? '—' : `${next.last_model_latency_ms.toFixed(0)} ms`;
  $('analysisValue').textContent = next.analysis_in_progress ? 'Running' : 'Idle';
  if (next.camera_running) {
    const activeCamera = document.querySelector(`input[name="cameraDevice"][value="${next.camera_device}"]`);
    if (activeCamera) activeCamera.checked = true;
  }
  $('privacyOn').disabled = next.privacy_screen;
  $('privacyOff').disabled = !next.privacy_screen;
  $('headerPrivacy').disabled = next.privacy_screen;
  $('staffError').hidden = !next.staff_error;
  $('staffError').textContent = next.staff_error || '';
}

function renderAnalysisStatus(next, analysis) {
  const status = $('analysisStatus');
  const title = $('analysisStatusTitle');
  const detail = $('analysisStatusDetail');
  const card = $('interpretationCard');
  card.setAttribute('aria-busy', String(next.analysis_in_progress));

  if (next.analysis_in_progress) {
    status.className = 'analysis-status thinking';
    title.textContent = 'Analysing the scene…';
    detail.textContent = analysis
      ? `Question: ${next.selected_question} The previous description remains visible below.`
      : `Question: ${next.selected_question}`;
    return;
  }
  if (next.internal_mode === 'detector-only') {
    const unavailable = !next.provider_available;
    status.className = `analysis-status ${unavailable ? 'unavailable' : 'disabled'}`;
    title.textContent = unavailable ? 'Scene model unavailable' : 'Scene analysis disabled';
    detail.textContent = unavailable
      ? 'The camera and object detector can continue without scene descriptions.'
      : 'Choose another operating mode to generate a description.';
    return;
  }
  if (analysis) {
    const generated = new Date(analysis.generated_at).toLocaleTimeString([], {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
    const latency = analysis.latency_ms === null ? '' : ` · ${analysis.latency_ms.toFixed(0)} ms`;
    status.className = 'analysis-status displayed';
    title.textContent = 'Scene description displayed';
    detail.textContent = `${analysis.provider}${latency} · updated ${generated}`;
    return;
  }
  status.className = 'analysis-status ready';
  title.textContent = 'Ready for a question';
  detail.textContent = 'Choose a question below to analyse the scene.';
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
  renderAnalysisStatus(next, analysis);
  renderAnalysisObjects(analysis);
  $('sceneSummary').textContent = analysis?.summary
    || (next.analysis_in_progress ? 'Analysing the scene…' : 'Choose a question to generate a scene description.');
  $('analysisTime').textContent = analysis
    ? `Description updated ${new Date(analysis.generated_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'})}`
    : (next.analysis_in_progress ? 'Scene analysis in progress' : 'No scene description yet');
  const uncertaintyPanel = $('uncertaintyPanel');
  const list = $('uncertainties');
  list.replaceChildren();
  uncertaintyPanel.hidden = !analysis?.uncertainties?.length;
  for (const uncertainty of analysis?.uncertainties || []) {
    const item = document.createElement('li'); item.textContent = uncertainty; list.append(item);
  }
  document.querySelectorAll('.question-grid button').forEach((button) => {
    button.disabled = next.analysis_in_progress || next.internal_mode === 'detector-only' || next.privacy_screen;
    button.classList.toggle('active', button.dataset.question === next.selected_question);
  });
  $('questionButtons').hidden = next.auto_analyse;
  if (next.auto_analyse && !next.camera_running) {
    $('questionsTitle').textContent = 'Automatic questions are paused';
    $('questionModeHint').textContent = 'Start the camera to restart the automatic analysis countdown.';
  } else {
    $('questionsTitle').textContent = next.auto_analyse ? 'Automatic questions are running' : 'Choose a question';
    $('questionModeHint').textContent = next.auto_analyse
      ? `SceneChat randomly rotates through ${next.auto_analyse_questions.length} curated questions every ${next.auto_analyse_interval_seconds} seconds.`
      : 'Select a prepared question to analyse the current scene.';
  }
  $('triggerAnalysis').disabled = next.analysis_in_progress
    || next.internal_mode === 'detector-only'
    || next.privacy_screen;
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
    if (success) showToast(typeof success === 'function' ? success(result) : success);
  } catch (error) {
    showToast(error.message);
  }
}

function populateOperatorControls(config, initial) {
  for (const mode of config.modes) $('modeSelect').add(new Option(mode, mode));
  for (const provider of config.providers) {
    const label = provider === 'modeldeck' ? 'ModelDeck · scenechat-vision' : provider;
    $('providerSelect').add(new Option(label, provider));
  }
  for (const scenario of config.scenarios) $('scenarioSelect').add(new Option(scenario.title, scenario.id));
  for (const question of config.questions) {
    $('questionSelect').add(new Option(question, question));
    const label = document.createElement('label');
    label.className = 'auto-question-choice';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.name = 'autoQuestion';
    input.value = question;
    input.checked = (initial.auto_analyse_questions || config.questions).includes(question);
    input.onchange = autoScheduleSelectionChanged;
    const text = document.createElement('span');
    text.textContent = question;
    label.append(input, text);
    $('autoQuestionChoices').append(label);
  }
  const detectorModels = config.detector_models || [];
  $('detectorModelControls').hidden = detectorModels.length === 0;
  for (const model of detectorModels) {
    $('detectorModelSelect').add(new Option(model.label, model.id));
  }
  $('detectorModelSelect').value = initial.detector_model || '';
  $('applyDetectorModel').disabled = detectorModels.length < 2;
  const detectorPrompts = config.detector_prompt_allowlist || [];
  $('detectorPromptControls').hidden = !config.detector_prompting;
  for (const prompt of detectorPrompts) {
    const label = document.createElement('label');
    label.className = 'prompt-choice';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.name = 'detectorPrompt';
    input.value = prompt;
    input.checked = (initial.detector_prompts || []).includes(prompt);
    input.onchange = detectorPromptSelectionChanged;
    const name = document.createElement('span');
    name.textContent = prompt;
    label.append(input, name);
    $('detectorPromptChoices').append(label);
  }
  renderActivePrompts(initial.detector_prompts || []);
  updatePromptPending();
  updateDetectorPromptToggle();
  $('selectAllDetectorPrompts').onclick = () => setAllDetectorPrompts(true);
  $('clearAllDetectorPrompts').onclick = () => setAllDetectorPrompts(false);
  document.querySelectorAll('[data-prompt-preset]').forEach((button) => {
    button.onclick = () => applyDetectorPromptPreset(button.dataset.promptPreset);
  });
  $('detectorPromptAutoUpdate').checked = initial.detector_prompt_auto_update;
  $('detectorPromptAutoUpdate').onchange = updatePromptPending;
  $('selectAllAutoQuestions').onclick = () => setAllAutoQuestions(true);
  $('clearAllAutoQuestions').onclick = () => setAllAutoQuestions(false);
  $('autoEnabled').onchange = updateAutoSchedulePending;
  $('autoInterval').oninput = updateAutoSchedulePending;
  updateAutoQuestionControls();
  updateAutoSchedulePending();

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

  $('privacyOn').onclick = () => act(
    () => post('/api/privacy', {enabled: true}),
    'Privacy screen activated. The camera feed is hidden, new analyses are blocked, and any in-flight result was invalidated.',
  );
  $('privacyOff').onclick = () => act(
    () => post('/api/privacy', {enabled: false}),
    'Camera view restored. Live frames and scene analysis are available again.',
  );
  $('resetSession').onclick = () => act(
    () => post('/api/reset'),
    'Session reset. Generated visitor text and learned detector objects were cleared; the operator-selected detector baseline was restored.',
  );
  $('headerPrivacy').onclick = $('privacyOn').onclick;
  $('headerReset').onclick = $('resetSession').onclick;
  $('detectorOnly').onclick = () => act(
    () => post('/api/mode', {mode: 'detector-only'}),
    'Camera-only mode activated. The live camera and fast object detector remain available; scene descriptions are disabled.',
  );
  $('applyMode').onclick = () => act(async () => {
    await post('/api/replay', {scenario: $('scenarioSelect').value});
    await post('/api/provider', {provider: $('providerSelect').value});
    return post('/api/mode', {mode: $('modeSelect').value});
  }, result => `Run configuration applied. Mode: ${result.internal_mode}; provider: ${result.provider}; replay scenario: ${result.replay_scenario}.`);
  $('checkProvider').onclick = () => act(
    () => post('/api/provider/check'),
    result => `Provider check complete. ${result.provider} is ${result.provider_available ? 'available' : 'unavailable'}. ${result.provider_status_message}`,
  );
  $('startCamera').onclick = () => act(() => {
    const selected = document.querySelector('input[name="cameraDevice"]:checked');
    if (!selected) throw new Error('Choose a camera first.');
    return post('/api/camera/start', {device: Number(selected.value)});
  }, result => {
    const label = state.cameraLabels.get(String(result.camera_device)) || `Camera ${result.camera_device}`;
    const automatic = result.auto_analyse
      ? ` Automatic scene analysis resumed; the next run is scheduled in ${result.auto_analyse_interval_seconds} seconds.`
      : '';
    return `${label} started. Fast object detection is using ${result.detector_model || result.detector_backend}.${automatic}`;
  });
  $('stopCamera').onclick = () => act(
    () => post('/api/camera/stop'),
    result => `Camera stopped. Live frames and continuous object detection are no longer running.${result.auto_analyse ? ' Automatic scene analysis is paused until the camera starts again.' : ''} Replay remains available.`,
  );
  $('applyDetectorModel').onclick = () => act(
    () => post('/api/detector/model', {model: $('detectorModelSelect').value}),
    result => `Object detector switched to ${result.detector_model}. The active prompt selection was reapplied.`,
  );
  $('applyDetectorPrompts').onclick = () => act(() => {
    const prompts = selectedDetectorPrompts();
    if (!prompts.length) throw new Error('Choose at least one object prompt.');
    return post('/api/detector/prompts', {
      prompts,
      auto_update: $('detectorPromptAutoUpdate').checked,
    });
  }, result => `Object detection updated. ${result.detector_prompt_baseline.length} operator prompts form the baseline and learned prompts were cleared. Safe session learning is ${result.detector_prompt_auto_update ? 'enabled' : 'disabled'}.`);
  $('clearLearnedPrompts').onclick = () => act(
    () => post('/api/detector/learned/clear'),
    result => `Learned detector objects cleared. The ${result.detector_prompt_baseline.length}-prompt operator baseline is active; scene text was preserved.`,
  );
  $('triggerAnalysis').onclick = () => act(
    () => post('/api/analyse', {question: $('questionSelect').value}),
    result => {
      const learning = result.prompt_learning;
      const details = [];
      if (learning.added.length) details.push(`Learned: ${learning.added.join(', ')}.`);
      if (learning.evicted.length) details.push(`Replaced older learned prompts: ${learning.evicted.join(', ')}.`);
      if (learning.rejected_count) {
        const reasons = Object.entries(learning.rejection_reasons || {})
          .map(([reason, count]) => `${promptLearningReasonLabels[reason] || 'other safety checks'}: ${count}`)
          .join(', ');
        details.push(`${learning.rejected_count} suggestions were blocked by the safety policy (${reasons}).`);
      }
      if (learning.capacity_skipped_count) details.push(`${learning.capacity_skipped_count} suggestions were skipped because the protected baseline filled the detector.`);
      const learningDetail = details.length ? ` ${details.join(' ')}` : ' No detector prompts changed.';
      return `Scene analysis completed for “${$('questionSelect').value}”. The ${result.analysis.provider} result was ${result.applied ? 'displayed' : 'discarded because the session changed'}.${learningDetail}`;
    },
  );
  $('clearAnalysis').onclick = () => act(
    () => post('/api/analysis/clear'),
    'Scene description cleared. The current camera frame and detector boxes remain visible.',
  );
  $('applyAuto').onclick = () => act(() => post('/api/auto-analyse', {
    enabled: $('autoEnabled').checked,
    interval_seconds: Number($('autoInterval').value),
    questions: selectedAutoQuestions(),
  }), result => {
    if (!result.auto_analyse) {
      return 'Automatic scene analysis disabled. Curated questions remain available for manual runs.';
    }
    if (!result.camera_running) {
      return `Automatic scene analysis configured for every ${result.auto_analyse_interval_seconds} seconds, but paused because the camera is stopped. It will resume after the camera starts.`;
    }
    return `Automatic scene analysis enabled. ${result.auto_analyse_questions.length} curated questions will rotate every ${result.auto_analyse_interval_seconds} seconds.`;
  });
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

function openOperatorControls() {
  const controls = $('operator-controls');
  if (!controls.open) controls.showModal();
}

function revealOperatorControls() {
  if (window.location.hash === '#operator-controls') openOperatorControls();
}

async function initialise() {
  const [config, initial] = await Promise.all([request('/api/config'), request('/api/state')]);
  state.questions = config.questions;
  state.detectorEnabled = config.detector_enabled;
  state.current = initial;
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
    try {
      render(await request('/api/reset', {method: 'POST'}));
      showToast('SceneChat is ready for the next visitor. Generated text was cleared and any in-flight analysis was invalidated.');
    }
    catch (error) { showToast(error.message); }
  });
  window.setInterval(() => {
    if (state.current?.camera_running && !state.current?.privacy_screen) {
      $('sceneImage').src = `/api/frame?t=${Date.now()}`;
    }
  }, 180);
  await updateHealth();
  window.setInterval(updateHealth, 5000);
  $('operatorControlsLink').addEventListener('click', openOperatorControls);
  $('closeOperatorControls').addEventListener('click', () => {
    $('operator-controls').close();
  });
  $('operator-controls').addEventListener('click', (event) => {
    if (event.target === $('operator-controls')) $('operator-controls').close();
  });
  $('operator-controls').addEventListener('close', () => {
    if (window.location.hash === '#operator-controls') {
      window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
    }
  });
  revealOperatorControls();
  window.addEventListener('hashchange', revealOperatorControls);
}

initialise().catch((error) => showToast(error.message));
