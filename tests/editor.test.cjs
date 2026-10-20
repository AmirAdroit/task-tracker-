'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Policy tests complement native Qt input tests; this small event fixture does
// not claim to reproduce browser focus, native pickers, or physical keyboard IMEs.
function editor() {
  const document = {body: {}, activeElement: null, modal: null, querySelector() { return this.modal; }};
  const context = vm.createContext({window: {}, document, queueMicrotask, setTimeout});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'editor-controller.js'), 'utf8'), context);
  const controller = context.window.createQuestEditor({});
  const field = {isConnected: true, disabled: false, validity: {valid: true},
    getClientRects: () => [1], closest: () => null,
    focus() { document.activeElement = this; }};
  const button = {closest: () => button};
  const listeners = {}, form = {isConnected: true, dataset: {}, commits: 0, attempts: 0,
    addEventListener(type, callback, capture) { (listeners[type] ||= []).push({callback, capture}); },
    querySelector: () => button, querySelectorAll: () => [field], contains: () => true,
    emit(type, properties = {}) {
      const event = {target: field, preventDefault() { this.prevented = true; },
        stopImmediatePropagation() { this.stopped = true; }, ...properties};
      for (const {callback} of [...(listeners[type] || [])].sort((a, b) => !!b.capture - !!a.capture)) {
        callback(event); if (event.stopped) break;
      }
      return event;
    },
    requestSubmit() {
      this.attempts++;
      if (!field.validity.valid) { field.focus(); return; }
      if (!this.emit('submit').prevented) this.commits++;
    },
  };
  controller.bind(form);
  document.activeElement = field;
  return {form, document, field, button};
}

test('implicit Enter clicks cannot commit; explicit Save clicks and Ctrl+Enter can', () => {
  const {form, button, document} = editor();
  form.emit('keydown', {key: 'Enter'});
  assert.equal(form.emit('click', {target: button, isTrusted: true, detail: 0}).prevented, true);
  form.requestSubmit();
  assert.equal(form.commits, 0);
  form.emit('keydown', {key: 'Enter', ctrlKey: true});
  assert.equal(form.commits, 1);
  form.emit('click', {target: button, isTrusted: true, detail: 1});
  form.requestSubmit();
  assert.equal(form.commits, 2);
  document.activeElement = button;
  form.emit('click', {target: button, isTrusted: true, detail: 0});
  form.requestSubmit();
  assert.equal(form.commits, 3);
});

test('Enter retains native behavior and pending or repeated shortcuts cannot submit', () => {
  const {form} = editor();
  assert.equal(form.emit('keydown', {key: 'Enter'}).prevented, undefined);
  form.dataset.pending = '1';
  form.emit('keydown', {key: 'Enter', ctrlKey: true});
  delete form.dataset.pending;
  form.emit('keydown', {key: 'Enter', ctrlKey: true, repeat: true});
  assert.equal(form.attempts, 0);
});

test('pointer permission survives the native event microtask checkpoint and expires if unused', async () => {
  const {form, button} = editor();
  form.emit('click', {target: button, isTrusted: true, detail: 1});
  await Promise.resolve(); // Real native default actions run after this checkpoint.
  form.requestSubmit();
  assert.equal(form.commits, 1);
  form.emit('click', {target: button, isTrusted: true, detail: 1});
  await new Promise(resolve => setTimeout(resolve, 5));
  form.requestSubmit();
  assert.equal(form.commits, 1);
});

test('IME Enter before and immediately after confirmation cannot commit', async () => {
  const {form} = editor();
  for (const properties of [{isComposing: true}, {keyCode: 229}]) {
    form.emit('keydown', {key: 'Enter', ctrlKey: true, ...properties});
  }
  form.emit('compositionstart');
  form.emit('keydown', {key: 'Enter', ctrlKey: true});
  form.emit('compositionend');
  form.emit('keydown', {key: 'Enter', ctrlKey: true});
  assert.equal(form.commits, 0);
  await new Promise(resolve => setTimeout(resolve, 5));
  form.emit('keydown', {key: 'Enter', ctrlKey: true});
  assert.equal(form.commits, 1);
});

test('failed native validation cannot leave implicit Enter armed to save', () => {
  const {form, field} = editor();
  field.validity.valid = false;
  form.emit('keydown', {key: 'Enter', ctrlKey: true});
  field.validity.valid = true;
  form.requestSubmit();
  assert.equal(form.commits, 0);
  form.emit('keydown', {key: 'Enter', ctrlKey: true});
  assert.equal(form.commits, 1);
});

test('late rejection cannot steal focus from another modal editor', () => {
  const {form, document, field} = editor();
  const newerField = {};
  document.activeElement = newerField; document.modal = {};
  form.questEditor.rejected();
  assert.equal(document.activeElement, newerField);
  document.modal = null; field.validity.valid = false;
  form.questEditor.rejected();
  assert.equal(document.activeElement, field);
});
