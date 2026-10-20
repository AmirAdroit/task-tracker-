'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function ui() {
  const context = vm.createContext({window: {QC: {}}, document: {}, setInterval, clearInterval, setTimeout, clearTimeout});
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
