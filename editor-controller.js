/* Shared editor lifecycle. Native controls keep their keys; saving is explicit. */
(function (root) {
  'use strict';
  root.createQuestEditor = function (U) {
    var current = null, closing = null, trigger = null;
    function visible(el) { return el && el.isConnected && !el.disabled && el.getClientRects().length && !el.closest('[hidden]'); }
    function controls(form) { return Array.from(form.querySelectorAll('input:not([type=hidden]),textarea,select')).filter(visible); }
    function remember(el) {
      if (!el || el === document.body) return null;
      var selector = el.id ? '[id=' + JSON.stringify(el.id) + ']' : '';
      if (!selector) ['data-action','data-view','data-id','data-group','data-day','data-project','data-check-task','data-check-index','name'].forEach(function (attr) {
        if (el.hasAttribute(attr)) selector += '[' + attr + '=' + JSON.stringify(el.getAttribute(attr)) + ']';
      });
      return {element:el, selector:selector, start:el.selectionStart, end:el.selectionEnd};
    }
    function focus(el, selection) {
      if (!visible(el)) return false;
      el.focus({preventScroll:true});
      if (selection && typeof selection.start === 'number' && el.setSelectionRange) el.setSelectionRange(selection.start, selection.end);
      return true;
    }
    function restore(saved, fallback) {
      if (document.querySelector('dialog[open]')) return;
      var el = saved && (visible(saved.element) ? saved.element : saved.selector && document.querySelector(saved.selector));
      if (focus(el, saved)) return;
      if (fallback) {
        var heading = document.querySelector('main h1,h1,#addInput');
        if (heading) { if (!heading.matches('input')) heading.tabIndex = -1; focus(heading); }
      }
    }
    if (document.addEventListener) document.addEventListener('click', function (e) {
      trigger = e.target.closest('button,[data-action],[data-view]');
      queueMicrotask(function () { trigger = null; });
    }, true);

    function ownsFocus(record) {
      return record.form.isConnected && (record.dialog ? current === record && record.dialog.open : !document.querySelector('dialog[open]'));
    }
    function bind(form, record) {
      if (form.questEditor) return form.questEditor;
      record = record || {form:form, dialog:null};
      record.form = form; record.permitted = false; record.composing = false;
      form.questEditor = record;
      function track(e) { if (e.target.matches('input,textarea,select')) record.lastField = remember(e.target); }
      form.addEventListener('focusin', track);
      form.addEventListener('input', track);
      form.addEventListener('keyup', track);
      form.addEventListener('compositionstart', function () { record.composing = true; });
      form.addEventListener('compositionend', function () {
        // An IME can emit its confirming Enter immediately after compositionend.
        record.justComposed = true; record.composing = false;
        setTimeout(function () { record.justComposed = false; }, 0);
      });
      function submit() {
        if (form.dataset.pending || !ownsFocus(record)) return;
        record.permitted = true;
        try { form.requestSubmit(form.querySelector('[type=submit]')); }
        finally { record.permitted = false; }
      }
      form.addEventListener('keydown', function (e) {
        if (e.key === 'Tab' && record.dialog && !record.composing) {
          var stops = Array.from(form.querySelectorAll('button,input:not([type=hidden]),textarea,select,[tabindex]')).filter(function (el) { return visible(el) && el.tabIndex >= 0; });
          var index = stops.indexOf(document.activeElement);
          if (stops.length && (index < 0 || (e.shiftKey ? index === 0 : index === stops.length - 1))) {
            e.preventDefault(); focus(e.shiftKey ? stops[stops.length - 1] : stops[0]);
          }
        }
        if (e.key !== 'Enter' || e.isComposing || e.keyCode === 229 || record.composing || record.justComposed) return;
        if (e.ctrlKey && !e.altKey && !e.metaKey) { e.preventDefault(); if (!e.repeat) submit(); }
      });
      form.addEventListener('click', function (e) {
        var button = e.target.closest('button[type=submit],input[type=submit]');
        if (!button || !form.contains(button)) return;
        // Implicit Enter in a field synthesizes a click on the default button.
        // Pointer clicks, keyboard activation ON Save, and explicit .click() are allowed.
        record.permitted = !e.isTrusted || e.detail > 0 || document.activeElement === button;
        if (!record.permitted) e.preventDefault(); // Do not trigger validation/focus changes either.
        // A native click checkpoints microtasks before its default submit action.
        // Clear unconsumed permission after that action (e.g. failed validation).
        setTimeout(function () { record.permitted = false; }, 0);
      }, true);
      form.addEventListener('submit', function (e) {
        if (!record.permitted || form.dataset.pending) { e.preventDefault(); e.stopImmediatePropagation(); }
        record.permitted = false;
      }, true);
      record.rejected = function () {
        if (!ownsFocus(record)) return;
        var invalid = controls(form).find(function (el) { return !el.validity.valid; });
        var saved = record.lastField, el = invalid || (saved && saved.element) || controls(form)[0];
        focus(el, invalid ? null : saved);
      };
      return record;
    }
    function closed(record) {
      if (current !== record) return;
      current = null; closing = record;
      queueMicrotask(function () {
        if (closing !== record || current) return;
        closing = null;
        // Chromium can leave a closed dialog's input focused. It is no longer
        // an unsaved page field and must not suppress the deferred refresh.
        if (record.dialog.contains(document.activeElement)) document.activeElement.blur();
        if (U.render) U.render(true);
        restore(record.opener, true);
      });
    }
    function open(title, body, save, submitLabel) {
      var opener = remember(trigger || document.activeElement);
      if (current && (!opener || current.dialog.contains(opener.element))) opener = current.opener;
      var previous = document.getElementById('editor');
      if (previous) { if (previous.open) previous.close(); previous.remove(); }
      var d = document.createElement('dialog'); d.id = 'editor'; document.body.appendChild(d);
      var record = {dialog:d, opener:opener}; current = record; closing = null;
      d.innerHTML = '<form id="edit-form"><header><h2>' + U.esc(title) + '</h2><button type="button" data-cancel aria-label="Close">×</button></header><div class="form-grid">' + body + '</div><p id="form-error" role="alert"></p><footer><button type="button" data-cancel>Cancel</button><button class="primary" type="submit">' + U.esc(submitLabel || 'Save') + ' <kbd>Ctrl+Enter</kbd></button></footer></form>';
      var form = d.querySelector('form'); bind(form, record);
      d.addEventListener('close', function () { closed(record); });
      d.addEventListener('cancel', function (e) { if (record.composing || record.justComposed) e.preventDefault(); });
      d.querySelectorAll('[data-cancel]').forEach(function (b) { b.onclick = function () { d.close(); }; });
      form.onsubmit = function (e) {
        e.preventDefault();
        var previousForm = U.commandForm; U.commandForm = form;
        try { save(U.values(form), form, d); }
        catch (err) { form.querySelector('#form-error').textContent = err.message; record.rejected(); }
        finally { U.commandForm = previousForm; }
      };
      // Set autofocus BEFORE showModal: there must be no frame with Close focused.
      var first = Array.from(form.querySelectorAll('.form-grid input:not([type=hidden]),.form-grid textarea,.form-grid select')).find(function (el) { return !el.disabled && !el.closest('[hidden]'); });
      if (first) first.autofocus = true;
      d.showModal();
      first = controls(form).find(function (el) { return el.closest('.form-grid'); });
      if (first) { focus(first); if (typeof first.selectionStart === 'number') first.setSelectionRange(first.value.length, first.value.length); }
      return d;
    }
    return {open:open, bind:bind, captureFocus:function () { return remember(document.activeElement); }, restoreFocus:restore,
      deferRender:function () { return !!closing || !!(current && !current.dialog.open); }};
  };
})(window);
