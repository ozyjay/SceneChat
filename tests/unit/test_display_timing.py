"""Exercise the real public-question handler with a deterministic browser clock."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_display_receipt_rejects_reset_privacy_and_stale_refresh():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the browser handler test")
    source = Path(__file__).resolve().parents[2] / "frontend/src/public.js"
    script = r'''const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[1], 'utf8');
const handler = source.slice(source.indexOf('async function analyse('), source.indexOf('async function act('));
async function run(mode) {
  const events = [], paints = [], renders = [];
  const initial = {generation: 1, revision: 1, privacy_screen: false};
  const current = {...initial, revision: 2, scene_analysis: {analysis_request_id: 'opaque'}};
  const state = {current: initial};
  const context = {state, performance: {now: () => 50},
    request: async path => {
      if (path === '/api/analyse') return {applied: true, analysis: {analysis_request_id: 'opaque'}};
      if (mode === 'reset') state.current = {...initial, generation: 2, revision: 3};
      if (mode === 'stale') state.current = {...current, revision: 3};
      return current;
    }, render: value => { renders.push(value); state.current = value; },
    requestAnimationFrame: callback => paints.push(callback),
    window: {dispatchEvent: event => events.push(event)},
    CustomEvent: class { constructor(name, options) { this.name = name; this.detail = options.detail; } },
    showToast: error => { throw new Error(error); },
  };
  vm.createContext(context);
  await vm.runInContext(handler + '; analyse("Describe the scene.")', context);
  if (mode === 'privacy') state.current = {...current, privacy_screen: true};
  while (paints.length) paints.shift()();
  if (mode === 'success') {
    assert.equal(events.length, 1);
    assert.equal(events[0].detail.request_id, 'opaque');
    assert.deepEqual(Object.keys(events[0].detail).sort(), ['duration_ms', 'measurement', 'request_id']);
  } else {
    assert.equal(events.length, 0);
    if (mode !== 'privacy') assert.equal(renders.length, 0);
  }
}
(async () => { for (const mode of ['success', 'reset', 'stale', 'privacy']) await run(mode); })()
  .catch(error => { console.error(error); process.exitCode = 1; });
'''
    subprocess.run([node, "-e", script, str(source)], check=True, timeout=10)
