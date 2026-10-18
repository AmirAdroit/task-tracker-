/* Shared UI helpers. Pages dispatch commands; only the native service saves state. */
(function () {
  'use strict';
  var U = window.QUI = {}, Q = window.QC;
  U.esc = Q.esc;
  U.field = function (name, label, value, type, extra) { return '<label>' + Q.esc(label) + '<input name="' + name + '" type="' + (type || 'text') + '" value="' + Q.esc(value == null ? '' : value) + '" ' + (extra || '') + '></label>'; };
  U.area = function (name, label, value) { return '<label>' + Q.esc(label) + '<textarea name="' + name + '" dir="auto">' + Q.esc(value || '') + '</textarea></label>'; };
  U.select = function (name, label, items, selected, empty) { return '<label>' + Q.esc(label) + '<select name="' + name + '">' + (empty == null ? '' : '<option value="">' + Q.esc(empty) + '</option>') + items.map(function (x) { var id = x.id == null ? x.value : x.id; return '<option value="' + Q.esc(id) + '"' + (String(id) === String(selected) ? ' selected' : '') + '>' + Q.esc(x.title || x.name || x.label) + '</option>'; }).join('') + '</select></label>'; };
  U.check = function (name, label, checked) { return '<label class="check"><input name="' + name + '" type="checkbox"' + (checked ? ' checked' : '') + '>' + Q.esc(label) + '</label>'; };
  U.values = function (form) { var out = {}; new FormData(form).forEach(function (v, k) { out[k] = v; }); return out; };
  U.num = function (v) { return v === '' || v == null ? null : Number(v); };
  U.dateTime = function (ts) { if (!ts) return ''; var d = new Date(ts); return Q.dayKey(ts) + 'T' + ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2); };
  U.button = function (action, label, id, extra) { return '<button type="button" data-action="' + action + '"' + (id == null ? '' : ' data-id="' + id + '"') + ' ' + (extra || '') + '>' + Q.esc(label) + '</button>'; };
  U.notice = function (message, error) { var n = document.getElementById('notice'); if (!n) { n = document.createElement('div'); n.id = 'notice'; document.body.appendChild(n); } n.textContent = message; n.className = error ? 'error' : ''; n.hidden = false; clearTimeout(U.noticeTimer); U.noticeTimer = setTimeout(function () { n.hidden = true; }, error ? 12000 : 3500); };
  U.dialog = function (title, body, save, submitLabel) {
    var d = document.getElementById('editor');
    if (!d) { d = document.createElement('dialog'); d.id = 'editor'; document.body.appendChild(d); }
    if (d.open) d.close();
    if (!d.dataset.refreshHook) { d.dataset.refreshHook = '1'; d.addEventListener('close', function () { if(U.render) U.render(true); }); }
    d.innerHTML = '<form id="edit-form"><header><h2>' + Q.esc(title) + '</h2><button type="button" data-cancel aria-label="Close">×</button></header><div class="form-grid">' + body + '</div><p id="form-error" role="alert"></p><footer><button type="button" data-cancel>Cancel</button><button class="primary" type="submit">' + Q.esc(submitLabel || 'Save') + '</button></footer></form>';
    d.querySelectorAll('[data-cancel]').forEach(function (b) { b.onclick = function () { d.close(); }; });
    d.querySelector('form').onsubmit = function (e) { e.preventDefault(); try { save(U.values(e.target), e.target, d); } catch (err) { d.querySelector('#form-error').textContent = err.message; } };
    d.showModal(); return d;
  };
  U.dispatch = function (type, payload, done) {
    U.store.dispatch({type: type, payload: payload || {}}, function (result) {
      if (result.state) U.state = result.state;
      if (!result.ok) { var error = document.getElementById('form-error'); if (error) error.textContent = result.error; U.notice(result.error, true); return; }
      if (done) done(result.state); if (U.render) U.render(type === 'review.save');
    });
  };
  U.start = function (taskId) {
    var q = Q.find(U.state, 'quests', taskId);
    var d = U.dialog('Start a session', '<p class="wide" dir="auto">' + Q.esc(q.title) + '</p><div class="row wide">' + [25, 60, 90, 180].map(function (m) { return '<button type="button" data-preset="' + m + '">' + m + ' min</button>'; }).join('') + '</div>' + U.field('minutes', 'Session limit (minutes)', q.sessionMinutes || U.state.settings.sessionMinutes, 'number', 'min="1" max="1440" required') + '<p class="hint wide">The timer pauses at the limit. Your task remains open. Other timers can run alongside it.</p>', function (f, form, dialog) { U.dispatch('session.start', {taskId: taskId, minutes: Number(f.minutes)}, function () { dialog.close(); }); }, 'Start session');
    d.querySelectorAll('[data-preset]').forEach(function (b) { b.onclick = function () { d.querySelector('[name=minutes]').value = b.dataset.preset; }; });
  };
  U.extend = function (id) { U.dialog('Extend session', U.field('minutes', 'Additional minutes, starting now', 30, 'number', 'min="1" max="1440" required'), function (f, form, d) { U.dispatch('session.extend', {id: id, minutes: Number(f.minutes)}, function () { d.close(); }); }, 'Extend and resume'); };
  U.log = function (taskId, day, existing) {
    var x = existing || {};
    var d = U.dialog(existing ? 'Edit time entry' : 'Log work manually', U.select('taskId', 'Task', U.state.quests, x.taskId || taskId, 'Choose a task') + U.field('day', 'Tracking day', x.day || day || Q.trackingDay(U.state), 'date', 'required') + U.field('minutes', 'Duration (minutes)', x.durationMs ? x.durationMs / 60000 : '', 'number', 'min="0.1" max="1440" step="any" required') + U.field('start', 'Start (optional)', x.segments && x.segments.length ? U.dateTime(x.segments[0].start) : '', 'datetime-local') + U.field('end', 'End (optional)', x.segments && x.segments.length ? U.dateTime(x.segments[x.segments.length - 1].end) : '', 'datetime-local') + U.area('note', 'What did you work on?', x.note) + '<p class="hint wide">Start/end times calculate duration. Without them, effort is recorded without guessing overlaps.</p>', function (f, form, dialog) {
      var p = {taskId: Number(f.taskId), day: f.day, minutes: Number(f.minutes), note: f.note}; if (existing) p.id = existing.id;
      if (f.start || f.end) { p.start = new Date(f.start).getTime(); p.end = new Date(f.end).getTime(); }
      U.dispatch('log.save', p, function () { dialog.close(); });
    });
    function syncDuration() { var a = d.querySelector('[name=start]').value, b = d.querySelector('[name=end]').value; if (a && b) d.querySelector('[name=minutes]').value = (new Date(b) - new Date(a)) / 60000; }
    d.querySelector('[name=start]').onchange = syncDuration; d.querySelector('[name=end]').onchange = syncDuration;
  };
  U.sessionsHTML = function () {
    var now = Date.now(), xs = U.state.sessions.filter(function (x) { return x.kind === 'timer' && x.status !== 'finished'; });
    if (!xs.length) return '<p class="hint">No active sessions. Start a timer or log time manually.</p>';
    var running = xs.filter(function (x) { return x.status === 'running'; }).length;
    return (running > 1 ? '<p class="warning">' + running + ' timers running together. Summed effort includes overlaps.</p>' : '') + xs.map(function (x) {
      return '<article class="session' + (x.needsAttention ? ' attention' : '') + '"><div><b dir="auto">' + Q.esc(x.title) + '</b><span class="pill">' + Q.esc(x.status) + '</span><p><span data-session-clock="' + x.id + '">' + Q.fmtDur(Q.elapsed(x, now)) + '</span> / ' + Q.fmtDur(x.limitMs) + (x.status === 'running' ? ' · <span data-session-remaining="' + x.id + '"></span> left' : '') + '</p>' + (x.status === 'recovery' ? '<p class="warning">Recovered after shutdown. Check this time before continuing.</p>' : '') + '</div><div class="actions">' + (x.status === 'running' ? U.button('session.pause', 'Pause', x.id) : (Q.elapsed(x, now) < x.limitMs ? U.button('session.resume', 'Resume', x.id) : '')) + U.button('extend', 'Extend', x.id) + U.button('session.finish', 'Finish session', x.id) + '</div></article>';
    }).join('');
  };
  U.handleSession = function (b) { var a = b.dataset.action, id = Number(b.dataset.id); if (a === 'start') U.start(id); else if (a === 'extend') U.extend(id); else if (/^session\./.test(a)) U.dispatch(a, {id: id}); else return false; return true; };
  U.boot = function (render) {
    U.render = render;
    Q.makeStore(function (store) {
      U.store = store;
      function load() { store.load(function (text) { try { U.state = Q.normalize(JSON.parse(text)); render(true); } catch (e) { U.notice('Could not read saved data: ' + e.message, true); } }); }
      load(); store.onChange(load); if (store.onNavigate) store.onNavigate(function (route) { if (U.navigate) U.navigate(route); });
    });
    setInterval(function () {
      if (!U.state) return;
      document.querySelectorAll('[data-session-clock]').forEach(function (el) { var x = Q.find(U.state, 'sessions', Number(el.dataset.sessionClock)); if (x) el.textContent = Q.fmtDur(Q.elapsed(x, Date.now())); });
      document.querySelectorAll('[data-session-remaining]').forEach(function (el) { var x = Q.find(U.state, 'sessions', Number(el.dataset.sessionRemaining)); if (x) el.textContent = Q.fmtDur(Math.max(0, x.limitMs - Q.elapsed(x, Date.now()))); });
      if (U.onClock) U.onClock();
      if (U.store.kind === 'local') U.store.dispatch({type: 'tick'});
    }, 1000);
  };
})();
