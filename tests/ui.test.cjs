'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function ui() {
  const context = vm.createContext({window: {QC: {}}, document: {querySelector: () => null}, setInterval: () => 0, clearInterval, setTimeout, clearTimeout});
  for (const file of ['editor-controller.js', 'ui-common.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  const u = context.window.QUI, replies = [];
  u.store = {dispatch(command, callback) { replies.push({command, callback}); }};
  u.notice = () => {};
  u.render = () => {};
  return {u, replies};
}

function form() {
  const controls = [{disabled: false}, {disabled: true}], error = {textContent: 'Old error'};
  return {dataset: {}, controls, error, setAttribute() {}, removeAttribute() {},
    querySelectorAll() { return controls; }, querySelector() { return error; }};
}

test('unchanged text and generated markup leave existing DOM nodes untouched', () => {
  const {u} = ui();
  let replacements = 0, textWrites = 0, text = '10';
  const el = {set innerHTML(value) { replacements++; }, get textContent() { return text; },
    set textContent(value) { textWrites++; text = value; }};
  u.html(el, '<b>Level 1</b>');
  for (let i = 0; i < 100; i++) { u.html(el, '<b>Level 1</b>'); u.text(el, 10); }
  assert.equal(replacements, 1); assert.equal(textWrites, 0);
  u.html(el, '<b>Level 2</b>'); u.text(el, 11);
  assert.equal(replacements, 2); assert.equal(textWrites, 1);
});

test('duplicate and stale load notifications do not redraw the accepted snapshot', () => {
  let snapshot = {revision: 4}, onChange, renders = 0;
  const store = {kind: 'bridge', load(callback) { callback(JSON.stringify(snapshot)); }, onChange(callback) { onChange = callback; }};
  // Supply only the model/store surface used during boot.
  const context = vm.createContext({window: {QC: {normalize: value => value, makeStore: callback => callback(store)}},
    document: {querySelector: () => null}, setInterval: () => 0, setTimeout, clearTimeout});
  for (const file of ['editor-controller.js', 'ui-common.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  context.window.QUI.boot(() => { renders++; });
  assert.equal(renders, 1);
  onChange(); assert.equal(renders, 1);
  snapshot = {revision: 3}; onChange(); assert.equal(renders, 1);
  snapshot = {revision: 5}; onChange(); assert.equal(renders, 2);
});

test('repair restores styles and stale frame callbacks cannot finish a newer repair', () => {
  const frames = [], timers = [];
  let opacity = '0.8', priority = 'important';
  const style = {getPropertyValue: () => opacity, getPropertyPriority: () => priority,
    setProperty(name, value, importance) { opacity = value; priority = importance; },
    removeProperty() { opacity = ''; priority = ''; }};
  const context = vm.createContext({window: {QC: {}}, document: {documentElement: {style}},
    requestAnimationFrame: callback => frames.push(callback), setTimeout: callback => timers.push(callback), clearTimeout() {}});
  for (const file of ['editor-controller.js', 'ui-common.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  const u = context.window.QUI;
  u.repaint(); u.repaint(); assert.equal(frames.length, 1);
  timers[0](); assert.equal(opacity, '0.8'); assert.equal(priority, 'important');
  u.repaint(); assert.equal(u.repaintPending, true);
  frames.shift()(); // Old outer frame queues its obsolete restore callback.
  frames.shift()(); // Current outer frame queues its own restore callback.
  frames.shift()(); assert.equal(u.repaintPending, true);
  frames.shift()(); assert.equal(u.repaintPending, false);
  assert.equal(opacity, '0.8'); assert.equal(priority, 'important');
});

test('an older successful command reply cannot hide newer panel data', () => {
  const {u, replies} = ui();
  u.state = {revision: 5, quests: ['old']};
  let seen;
  u.dispatch('task.add', {title: 'A'}, state => { seen = state; });
  u.acceptState({revision: 7, quests: ['A', 'B']});
  replies[0].callback({ok: true, state: {revision: 6, quests: ['A']}});
  assert.equal(u.state.revision, 7);
  assert.deepEqual(seen.quests, ['A', 'B']);
});

test('an older load or rejected command reply cannot regress the snapshot', () => {
  const {u, replies} = ui();
  u.acceptState({revision: 10}); u.acceptState({revision: 9});
  u.dispatch('task.edit', {});
  replies[0].callback({ok: false, error: 'Rejected', state: {revision: 8}});
  assert.equal(u.state.revision, 10);
});

test('pending form submissions are sent once and retain disabled conditional fields', () => {
  const {u, replies} = ui(), f = form();
  u.commandForm = f;
  u.dispatch('entity.save', {group: 'goals'});
  u.dispatch('entity.save', {group: 'goals'});
  assert.equal(replies.length, 1);
  assert.equal(f.controls[0].disabled, true);
  replies[0].callback({ok: true, state: {revision: 1}});
  assert.equal(f.controls[0].disabled, false);
  assert.equal(f.controls[1].disabled, true);
  assert.equal(f.dataset.pending, undefined);
});

test('a failed reply belongs to its original form and unlocks retry', () => {
  const {u, replies} = ui(), oldForm = form(), newForm = form();
  u.commandForm = oldForm; u.dispatch('task.add', {});
  u.commandForm = newForm;
  replies[0].callback({ok: false, error: 'Enter a title'});
  assert.equal(oldForm.error.textContent, 'Enter a title');
  assert.equal(newForm.error.textContent, 'Old error');
  assert.equal(oldForm.controls[0].disabled, false);
  u.commandForm = oldForm; u.dispatch('task.add', {title: 'Retry'});
  assert.equal(replies.length, 2);
});

test('a transport exception unlocks the form instead of leaving it stuck', () => {
  const {u} = ui(), f = form();
  u.commandForm = f;
  u.store.dispatch = () => { throw new Error('Disconnected'); };
  assert.throws(() => u.dispatch('task.add', {}), /Disconnected/);
  assert.equal(f.dataset.pending, undefined);
  assert.equal(f.controls[0].disabled, false);
});
