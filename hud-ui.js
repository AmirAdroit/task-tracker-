(function () {
  'use strict';
  var U = window.QUI, Q = window.QC, E = Q.esc, $ = function (id) { return document.getElementById(id); };
  var lenses = ['Focus', 'Today', 'Backlog', 'Sessions', 'Done'], lens = 1, cat = null, filterOpen = false;
  function render(background) {
    if (U.editor.deferRender()) return;
    var s = U.state, now = Date.now(); if (!s) return;
    U.text($('lvl'), s.level); U.text($('gold'), s.gold.toLocaleString()); U.text($('xpval'), s.xp + ' / ' + s.xpMax); $('xpfill').style.width = Math.min(100, s.xp / s.xpMax * 100) + '%';
    U.text($('s-done'), s.completed.length); U.text($('s-time'), Q.fmtDur(Q.totalEffort(s, now)));
    var pending = Q.pendingReviews(s, now); $('pendingReview').hidden = !pending.length; U.text($('pendingReview'), pending.length + ' day(s) waiting for check-in ↗');
    $('panel').classList.toggle('solid', s.ui.translucent === false); $('solidToggle').classList.toggle('on', s.ui.translucent === false);
    if (!background) { $('opacity').value = Math.round((s.ui.opacity || 1) * 100); $('scale').value = Math.round((s.ui.hudScale || 1) * 100); }
    $('opval').textContent = Math.round((s.ui.opacity || 1) * 100) + '%'; $('scaleval').textContent = Math.round((s.ui.hudScale || 1) * 100) + '%';
    U.store.setOpacity(s.ui.opacity || 1); U.store.setZoom(s.ui.hudScale || 1);
    $('lensName').textContent = lenses[lens]; U.html($('lensDots'), lenses.map(function (v, i) { return '<span class="' + (i === lens ? 'on' : '') + '"></span>'; }).join(''));
    $('catFilter').classList.toggle('open', filterOpen); $('filterBtn').classList.toggle('on', cat != null);
    U.html($('catFilter'), '<button class="catchip" data-cat="">All</button>' + s.categories.map(function (c) { return '<button class="catchip' + (cat === c.id ? ' on' : '') + '" data-cat="' + c.id + '">' + E(c.name) + '</button>'; }).join(''));
    if (document.querySelector('dialog[open]')) return;
    var key = lenses[lens], day = Q.trackingDay(s), ids = Q.expected(s, day).map(function (q) { return q.id; });
    if (key === 'Sessions') { $('lensCount').textContent = s.sessions.filter(function (x) { return x.kind === 'timer' && x.status !== 'finished'; }).length; U.html($('questList'), U.sessionsHTML()); }
    else if (key === 'Done') {
      var done = s.completed.filter(function (c) { return cat == null || c.cat === cat; }).sort(function(a,b){return b.at-a.at;}); $('lensCount').textContent = done.length;
      U.html($('questList'), done.slice(0,40).map(function (c) { return '<div class="logitem"><span class="chk">✓</span><span class="lt" dir="auto">' + E(c.title) + '</span><span class="ld">' + (c.timeReview === 'pending' ? 'Review time' : Q.fmtDur(c.ms)) + '</span></div>'; }).join('') || '<p class="empty">No completed quests.</p>');
    } else {
      var list = s.quests.filter(function (q) { return !q.archived && q.status !== 'done' && (cat == null || q.cat === cat) && (key === 'Backlog' ? q.status === 'backlog' : key === 'Today' ? ids.indexOf(q.id) >= 0 || q.pinned || (q.due != null && Q.dueDaysLeft(q.due) <= 0) : q.status !== 'backlog' && (!q.occurrenceDay || q.occurrenceDay === day)); }).sort(Q.byHeat(now));
      $('lensCount').textContent = list.length;
      U.html($('questList'), list.map(function (q) {
        var sessions = s.sessions.filter(function (x) { return x.taskId === q.id && x.kind === 'timer' && x.status !== 'finished'; });
        return '<article class="quest" style="--u:' + Q.urgencyColor(q) + '"><div class="q-top"><b class="q-title" dir="auto">' + E(q.title) + '</b>' + (q.due ? '<small>' + E(Q.fmtDue(q.due)) + '</small>' : '') + '</div>' + (q.obj ? '<p class="q-obj" dir="auto">' + E(q.obj) + '</p>' : '') + '<div class="q-meta"><span>' + Q.fmtDur(Q.taskEffort(s, q.id, now)) + (q.estimateMinutes ? ' / ' + q.estimateMinutes + 'm est.' : '') + '</span><span>' + E(q.status) + '</span></div><div class="q-meta">' + U.button('start', 'Start', q.id, 'class="qbtn start"') + U.button('log', 'Log', q.id, 'class="qbtn"') + U.button('complete', 'Done', q.id, 'class="qbtn done"') + U.button('edit', '⋯', q.id, 'class="more" aria-label="Edit quest"') + '</div>' + sessions.map(function (x) { return '<div class="q-meta"><span class="timer" data-session-clock="' + x.id + '">' + Q.fmtDur(Q.elapsed(x, now)) + '</span><span>' + E(x.status) + ' / ' + Q.fmtDur(x.limitMs) + '</span>' + (x.status === 'running' ? U.button('session.pause', 'Pause', x.id, 'class="chipbtn"') : U.button('extend', 'Extend', x.id, 'class="chipbtn"')) + U.button('session.finish', 'Finish', x.id, 'class="chipbtn"') + '</div>'; }).join('') + '</article>';
      }).join('') || '<p class="empty">Nothing here. Plan a task in the control panel.</p>');
    }
    U.html($('achList'), Q.ACHS.map(function (a) { return '<span class="badge' + (s.ach[a.key] ? ' on' : '') + '" title="' + E(a.name) + '">' + a.icon + '</span>'; }).join(''));
  }
  $('prevLens').onclick = function () { lens = (lens + lenses.length - 1) % lenses.length; render(); };
  $('nextLens').onclick = function () { lens = (lens + 1) % lenses.length; render(); };
  $('filterBtn').onclick = function () { filterOpen = !filterOpen; render(); };
  $('catFilter').onclick = function (e) { var b = e.target.closest('[data-cat]'); if (b) { cat = b.dataset.cat ? Number(b.dataset.cat) : null; render(); } };
  $('gearBtn').onclick = function () { $('settings').classList.toggle('open'); };
  $('collapseBtn').onclick = function () { var collapsed = $('panel').classList.toggle('collapsed'); this.textContent = collapsed ? '▸' : '▾'; this.setAttribute('aria-expanded', String(!collapsed)); if(U.store.setCollapsed) U.store.setCollapsed(collapsed); };
  $('openPanelBtn').onclick = function () { U.store.openPanel('today'); };
  $('pendingReview').onclick = function () { U.store.openPanel('review:' + (Q.pendingReviews(U.state, Date.now()).slice(-1)[0] || Q.trackingDay(U.state))); };
  $('solidToggle').onclick = function () { U.dispatch('ui.save', {translucent: U.state.ui.translucent === false}); };
  $('opacity').oninput = function () { U.store.setOpacity(Number(this.value) / 100); $('opval').textContent = this.value + '%'; };
  $('opacity').onchange = function () { U.dispatch('ui.save', {opacity: Number(this.value) / 100}); };
  $('scale').oninput = function () { U.store.setZoom(Number(this.value) / 100); $('scaleval').textContent = this.value + '%'; };
  $('scale').onchange = function () { U.dispatch('ui.save', {hudScale: Number(this.value) / 100}); };
  function add() { var title = $('addInput').value.trim(); if (!title) return; U.dispatch('task.add', {title: title, status: lenses[lens] === 'Backlog' ? 'backlog' : 'active', cat: cat}, function (s) { $('addInput').value = ''; if (lenses[lens] === 'Today') { var q = s.quests[s.quests.length - 1]; U.dispatch('allocation.save', {taskId: q.id, day: Q.trackingDay(s), minutes: s.settings.sessionMinutes}); } }); }
  $('addBtn').onclick = add; $('addInput').onkeydown = function (e) { if (e.key === 'Enter') add(); };
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-action]'); if (!b || !U.state || U.handleSession(b)) return;
    var id = Number(b.dataset.id), q = Q.find(U.state, 'quests', id);
    if (b.dataset.action === 'log') U.log(id);
    else if (b.dataset.action === 'complete') U.dispatch('task.complete', {id: id});
    else if (b.dataset.action === 'edit') U.dialog('Quest details', U.select('cat', 'Category', U.state.categories, q.cat, 'Uncategorized') + U.field('due', 'Deadline', q.due ? Q.dayKey(q.due) : '', 'date') + U.field('estimateMinutes', 'Total effort estimate (minutes)', q.estimateMinutes, 'number', 'min="1"') + U.check('pinned', 'Pin as urgent', q.pinned), function (f, form, d) { U.dispatch('task.edit', {id: id, fields: {cat: U.num(f.cat), due: f.due ? new Date(f.due + 'T12:00:00').getTime() : null, estimateMinutes: U.num(f.estimateMinutes), pinned: !!f.pinned}}, function () { d.close(); }); });
  });
  U.boot(render);
})();
