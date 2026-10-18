/* QuestHUD v4 domain model. No DOM, filesystem, or timers: all changes go through apply(). */
(function (root) {
  'use strict';
  var Q = root.QC, oldDefault = Q.defaultState, oldNormalize = Q.normalize;
  var MIN = 60000, HOUR = 60 * MIN;
  var collections = ['quests', 'recurring', 'completed', 'periods', 'goals', 'projects', 'milestones', 'allocations', 'sessions', 'daysOff'];
  function copy(x) { return JSON.parse(JSON.stringify(x)); }
  function assert(ok, message) { if (!ok) throw new Error(message); }
  function number(x, min, max, label) { x = Number(x); assert(isFinite(x) && x >= min && x <= max, label + ' is out of range'); return x; }
  function date(d) { assert(/^\d{4}-\d{2}-\d{2}$/.test(d || '') && Q.dayKey(new Date(d + 'T12:00:00').getTime()) === d, 'Choose a valid date'); return d; }
  function shift(day, n) { var d = new Date(day + 'T12:00:00'); d.setDate(d.getDate() + n); return Q.dayKey(d.getTime()); }
  function boundary(day, hour) { var d = new Date(day + 'T00:00:00'); d.setHours(hour, 0, 0, 0); return d.getTime(); }
  function trackingDay(s, now) { var d = new Date(now == null ? Date.now() : now); if (d.getHours() < s.settings.dayBoundary) d.setDate(d.getDate() - 1); return Q.dayKey(d.getTime()); }
  function find(s, group, id) { return s[group].find(function (x) { return x.id === id; }); }
  function requireItem(s, group, id) { var x = find(s, group, id); assert(x, 'This item no longer exists'); return x; }
  function create(s, group, fields) { var x = copy(fields); x.id = Q.newId(s); x.uid = s.origin + ':' + group + ':' + x.id; s[group].push(x); return x; }
  function off(s, day) { return s.daysOff.find(function (x) { return x.start <= day && x.end >= day; }); }
  function boardReminder(input, now, previous) {
    var b = Object.assign({enabled: false, mode: 'daily', time: '', intervalMinutes: null, days: [0, 1, 2, 3, 4, 5, 6], windowStart: '', windowEnd: '', anchor: 0}, input || {});
    var timePattern = /^([01]\d|2[0-3]):[0-5]\d$/;
    assert(typeof b.enabled === 'boolean' && ['daily', 'interval'].indexOf(b.mode) >= 0, 'Choose a board reminder mode');
    assert(Array.isArray(b.days) && b.days.every(function (d) { return Number.isInteger(d) && d >= 0 && d <= 6; }), 'Choose valid reminder weekdays');
    b.days = b.days.filter(function (d, i, a) { return a.indexOf(d) === i; }).sort();
    if (b.enabled) {
      assert(b.days.length, 'Choose at least one reminder weekday');
      if (b.mode === 'daily') assert(timePattern.test(b.time), 'Choose a board reminder time');
      else {
        b.intervalMinutes = number(b.intervalMinutes, 15, 1440, 'Board reminder interval');
        assert(Number.isInteger(b.intervalMinutes), 'Use a whole number of minutes for reminders');
        assert((!b.windowStart && !b.windowEnd) || (timePattern.test(b.windowStart) && timePattern.test(b.windowEnd) && b.windowStart !== b.windowEnd), 'Choose different start/end times, or leave both blank');
      }
    }
    var fields = ['enabled', 'mode', 'time', 'intervalMinutes', 'days', 'windowStart', 'windowEnd'];
    var changed = previous && fields.some(function (k) { return JSON.stringify(b[k]) !== JSON.stringify(previous[k]); });
    b.anchor = b.enabled ? (changed ? now : Number(b.anchor) || now) : 0;
    var result = {}; fields.concat(['anchor']).forEach(function (k) { result[k] = b[k]; }); return result;
  }
  function normalize(input, now) {
    now = now == null ? Date.now() : now;
    var legacy = !input || Number(input.version || 0) < 4;
    var s = oldNormalize(input || oldDefault());
    collections.forEach(function (k) { if (!Array.isArray(s[k])) s[k] = []; });
    s.origin = s.origin || 'qh-' + now.toString(36) + '-' + Math.random().toString(36).slice(2, 10);
    var maxId = s.nextId || 1;
    collections.forEach(function (k) { s[k].forEach(function (x) { if (typeof x.id === 'number') maxId = Math.max(maxId, x.id + 1); }); });
    s.nextId = maxId;
    collections.forEach(function (k) { s[k].forEach(function (x) { if (x.id == null) x.id = Q.newId(s); x.uid = x.uid || s.origin + ':' + k + ':' + x.id; }); });
    var defaults = {dayBoundary: 4, reviewTime: '23:00', reviewEvery: 30, reviewEnabled: true, sessionMinutes: 60, startup: true, weekStart: 1, availability: [null, null, null, null, null, null, null]};
    s.settings = s.settings || {};
    Object.keys(defaults).forEach(function (k) { if (!(k in s.settings)) s.settings[k] = copy(defaults[k]); });
    s.settings.boardReminder = boardReminder(s.settings.boardReminder, now);
    if (typeof s.settings.dayBoundary !== 'number') s.settings.dayBoundary = 4;
    s.settings.trackingStart = s.settings.trackingStart || trackingDay(s, now);
    s.reviews = s.reviews || {};
    s.requestIds = s.requestIds || [];
    s.revision = s.revision || 0;
    ['level', 'xp', 'xpMax', 'gold', 'goldEarned'].forEach(function (k) { assert(typeof s[k] === 'number' && isFinite(s[k]) && s[k] >= (k === 'level' || k === 'xpMax' ? 1 : 0), 'Invalid save: ' + k); });
    assert(Number.isInteger(s.settings.dayBoundary) && s.settings.dayBoundary >= 0 && s.settings.dayBoundary <= 12, 'Invalid save: day boundary');
    assert(/^([01]\d|2[0-3]):[0-5]\d$/.test(s.settings.reviewTime), 'Invalid save: review time');
    assert(s.settings.reviewEvery > 0 && isFinite(s.settings.reviewEvery), 'Invalid save: reminder interval');
    assert(Array.isArray(s.requestIds), 'Invalid save: request identities');
    s.sessions.forEach(function (x) {
      assert(x && ['manual', 'timer'].indexOf(x.kind) >= 0 && Array.isArray(x.segments), 'Invalid save: time entry');
      x.segments.forEach(function (r) { assert(isFinite(r.start) && isFinite(r.end) && r.end >= r.start, 'Invalid save: time range'); });
      if (x.kind === 'timer') assert(isFinite(x.limitMs) && x.limitMs > 0 && ['running', 'paused', 'expired', 'recovery', 'finished'].indexOf(x.status) >= 0 && (x.status !== 'running' || isFinite(x.runStart)), 'Invalid save: timer');
      if (x.kind === 'manual') assert(isFinite(x.durationMs) && x.durationMs >= 0, 'Invalid save: manual effort');
    });
    s.quests.forEach(function (q) {
      q.status = q.workflow || (q.status === 'backlog' ? 'backlog' : 'active');
      q.workflow = q.status;
      q.checklist = q.checklist || [];
      if (legacy && q.started) { q.legacyStarted = q.started; q.legacyTimerNeedsReview = true; }
      q.started = null;
      if (legacy && q.fromRecurring) q.legacyOccurrence = true;
    });
    s.recurring.forEach(function (t) { t.createdDay = t.createdDay || s.settings.trackingStart; t.state = t.state || 'active'; });
    s.completed.forEach(function (c) {
      assert(typeof c.ms === 'number' && isFinite(c.ms) && c.ms >= 0 && isFinite(c.at), 'Invalid save: completion time');
      if (legacy && c.originalMs == null) {
        c.originalMs = c.ms || 0; c.legacy = true; c.timeReview = c.ms > 12 * HOUR ? 'pending' : 'accepted';
      }
    });
    s.version = 4;
    return s;
  }
  function defaults(now) { return normalize(oldDefault(), now); }
  function snapshot(q) { return {taskId: q.id, taskUid: q.uid, title: q.title, cat: q.cat == null ? null : q.cat, projectId: q.projectId || null, fromRecurring: q.fromRecurring || null, occurrenceDay: q.occurrenceDay || null}; }
  function baseMs(x) { return (x.segments || []).reduce(function (sum, r) { return sum + Math.max(0, r.end - r.start); }, 0); }
  function elapsed(x, now) { var b = baseMs(x); return x.kind === 'manual' && !x.segments.length ? x.durationMs : b + (x.status === 'running' ? Math.max(0, Math.min(now - x.runStart, x.limitMs - b)) : 0); }
  function settle(x, now) {
    if (x.status !== 'running') return;
    var end = x.runStart + Math.max(0, Math.min(now - x.runStart, x.limitMs - baseMs(x)));
    if (end > x.runStart) x.segments.push({start: x.runStart, end: end});
    x.runStart = null;
  }
  function expire(s, now) {
    var changed = false;
    s.sessions.forEach(function (x) {
      if (x.status === 'running' && elapsed(x, now) >= x.limitMs) { settle(x, now); x.status = 'expired'; x.needsAttention = true; changed = true; }
    });
    return changed;
  }
  function taskEffort(s, taskId, now) {
    return s.sessions.filter(function (x) { return x.taskId === taskId; }).reduce(function (sum, x) { return sum + elapsed(x, now); }, 0);
  }
  function complete(s, q, now, day) {
    if (q.status === 'done') return;
    s.sessions.filter(function (x) { return x.taskId === q.id && x.status !== 'finished'; }).forEach(function (x) { settle(x, now); x.status = 'finished'; x.needsAttention = false; });
    var r = Q.reward(q), c = snapshot(q); c.at = now; c.day = day || (q.manualOccurrence ? q.occurrenceDay : trackingDay(s, now)); c.ms = taskEffort(s, q.id, now); c.gold = r.gold; c.xp = r.xp; c.sessionBacked = true;
    create(s, 'completed', c); q.status = q.workflow = 'done'; q.completedAt = now;
    s.gold += r.gold; s.goldEarned += r.gold; Q.addXp(s, r.xp); Q.checkAch(s);
  }
  function routineDue(t, day) {
    if (t.state !== 'active' || day < t.createdDay || (t.start && day < t.start) || (t.end && day > t.end)) return false;
    var dow = new Date(day + 'T12:00:00').getDay();
    if (t.repeat === 'daily') return true;
    if (t.repeat === 'weekdays') return dow >= 1 && dow <= 5;
    if (t.repeat === 'selected') return (t.days || []).indexOf(dow) >= 0;
    if (t.repeat === 'weekly') return dow === Number(t.weekday);
    if (t.repeat === 'interval') {
      var a = (t.start || t.createdDay).split('-').map(Number), b = day.split('-').map(Number);
      return Math.round((Date.UTC(b[0], b[1] - 1, b[2]) - Date.UTC(a[0], a[1] - 1, a[2])) / 86400000) % t.every === 0;
    }
    return false;
  }
  function occurrence(s, t, day, manual) {
    var q = s.quests.find(function (x) { return x.fromRecurring === t.id && x.occurrenceDay === day; });
    if (!q) q = create(s, 'quests', {title: t.title, obj: t.obj || '', diff: t.diff || 'normal', cat: t.cat || null, projectId: t.projectId || null, status: 'active', workflow: 'active', started: null, pinned: false, due: typeof t.dueOffset === 'number' ? boundary(shift(day, t.dueOffset), 0) : null, checklist: [], fromRecurring: t.id, occurrenceDay: day, scheduledDay: day, estimateMinutes: t.estimateMinutes || null, sessionMinutes: t.sessionMinutes || null});
    if (manual || q.suppressedByOff) { q.archived = false; delete q.suppressedByOff; }
    if (manual) q.manualOccurrence = true;
    if (!q.archived && !s.allocations.some(function (a) { return a.taskId === q.id && a.day === day; })) create(s, 'allocations', {taskId: q.id, day: day, minutes: t.estimateMinutes || t.sessionMinutes || s.settings.sessionMinutes, routine: true});
    return q;
  }
  function restoreOff(s, start, end, now) {
    var today = trackingDay(s, now);
    s.recurring.filter(function (t) { return t.state === 'active'; }).forEach(function (t) {
      var first = start > t.createdDay ? start : t.createdDay;
      for (var day = first; day <= end && day <= today; day = shift(day, 1)) {
        if (off(s, day)) continue;
        var q = s.quests.find(function (x) { return x.fromRecurring === t.id && x.occurrenceDay === day; });
        if ((q && q.suppressedByOff) || routineDue(t, day)) occurrence(s, t, day, false);
      }
    });
  }
  function rollover(s, now) {
    var today = trackingDay(s, now), changed = false;
    s.recurring.forEach(function (t) {
      for (var day = t.materializedThrough ? shift(t.materializedThrough, 1) : t.createdDay; day <= today; day = shift(day, 1)) {
        if (!off(s, day) && routineDue(t, day) && !s.quests.some(function (q) { return q.fromRecurring === t.id && q.occurrenceDay === day; })) {
          occurrence(s, t, day, false);
        }
        t.materializedThrough = day; changed = true;
      }
    });
    return changed;
  }
  function expected(s, day) {
    var ids = {};
    s.allocations.filter(function (a) { return a.day === day; }).forEach(function (a) { ids[a.taskId] = true; });
    return s.quests.filter(function (q) { return !q.archived && (ids[q.id] || q.occurrenceDay === day); });
  }
  function projectedRoutines(s, day) {
    if (off(s, day)) return [];
    return s.recurring.filter(function (t) { return routineDue(t, day) && !s.quests.some(function (q) { return q.fromRecurring === t.id && q.occurrenceDay === day; }); });
  }
  function reviewAt(s, day) {
    var p = s.settings.reviewTime.split(':').map(Number), h = p[0];
    return boundary(h < s.settings.dayBoundary ? shift(day, 1) : day, h) + p[1] * MIN;
  }
  function pendingReviews(s, now) {
    if (!s.settings.reviewEnabled || off(s, trackingDay(s, now))) return [];
    var list = [], today = trackingDay(s, now);
    for (var day = s.settings.trackingStart; day <= today; day = shift(day, 1)) {
      var r = s.reviews[day];
      if (!off(s, day) && reviewAt(s, day) <= now && (!r || ['submitted', 'skipped'].indexOf(r.status) < 0)) list.push(day);
    }
    return list;
  }
  function sliceRange(s, start, end) {
    var out = [];
    while (start < end) {
      var day = trackingDay(s, start), next = boundary(shift(day, 1), s.settings.dayBoundary), stop = Math.min(end, next);
      out.push({day: day, start: start, end: stop, ms: stop - start}); start = stop;
    }
    return out;
  }
  function entries(s, day, now) {
    var out = [];
    s.sessions.forEach(function (x) {
      var ranges = (x.segments || []).slice();
      if (x.status === 'running') { var end = x.runStart + Math.max(0, Math.min(now - x.runStart, x.limitMs - baseMs(x))); if (end > x.runStart) ranges.push({start: x.runStart, end: end}); }
      if (!ranges.length && x.kind === 'manual' && x.day === day) out.push({record: x, ms: x.durationMs, untimed: true});
      ranges.forEach(function (r) { sliceRange(s, r.start, r.end).forEach(function (part) { if (part.day === day) out.push({record: x, ms: part.ms, start: part.start, end: part.end}); }); });
    });
    return out;
  }
  function unionMs(ranges) {
    ranges.sort(function (a, b) { return a.start - b.start; });
    var total = 0, end = -Infinity;
    ranges.forEach(function (r) { total += Math.max(0, r.end - Math.max(r.start, end)); end = Math.max(end, r.end); }); return total;
  }
  function daySummary(s, day, now) {
    var logs = entries(s, day, now), ranged = logs.filter(function (r) { return !r.untimed; });
    var legacy = s.completed.filter(function (c) { return c.legacy && c.timeReview !== 'pending' && trackingDay(s, c.at) === day; }).reduce(function (a, c) { return a + c.ms; }, 0);
    var summed = logs.reduce(function (a, x) { return a + x.ms; }, 0), known = ranged.reduce(function (a, x) { return a + x.ms; }, 0), unique = unionMs(ranged);
    var planned = s.allocations.filter(function (a) { return a.day === day; }).reduce(function (a, x) { return a + x.minutes; }, 0);
    planned += projectedRoutines(s, day).reduce(function (a, t) { return a + (t.estimateMinutes || t.sessionMinutes || s.settings.sessionMinutes); }, 0);
    var capacity = off(s, day) ? null : s.settings.availability[new Date(day + 'T12:00:00').getDay()];
    return {day: day, entries: logs, summedMs: summed + legacy, uniqueMs: unique, untimedMs: summed - known, legacyMs: legacy, overlapMs: known - unique, plannedMinutes: planned, capacityHours: capacity, overCapacity: capacity != null && planned > capacity * 60, completed: s.completed.filter(function (c) { return (c.day || trackingDay(s, c.at)) === day; }), off: off(s, day) || null, review: s.reviews[day] || null};
  }
  function projectSummary(s, id, now) {
    var tasks = s.quests.filter(function (q) { return q.projectId === id; }), estimate = 0, actual = 0, remaining = 0;
    tasks.forEach(function (q) { var ms = taskEffort(s, q.id, now); actual += ms; estimate += (q.estimateMinutes || 0) * MIN; if (q.status !== 'done') remaining += Math.max(0, (q.estimateMinutes || 0) * MIN - ms); });
    return {estimateMs: estimate, actualMs: actual, remainingMs: remaining, overrunMs: Math.max(0, actual - estimate), done: tasks.filter(function (q) { return q.status === 'done'; }).length, total: tasks.length};
  }
  function totalEffort(s, now) { return s.sessions.reduce(function (a, x) { return a + elapsed(x, now); }, 0) + s.completed.filter(function (c) { return c.legacy && c.timeReview !== 'pending'; }).reduce(function (a, c) { return a + c.ms; }, 0); }
  function validateFields(s, group, f) {
    var x = copy(f);
    if ('title' in x) { x.title = String(x.title).trim(); assert(x.title, 'Enter a title'); }
    ['estimateMinutes', 'sessionMinutes'].forEach(function (k) { if (k in x) x[k] = x[k] === '' || x[k] == null ? null : number(x[k], 1, 1000000, k); });
    if (x.sessionMinutes != null) number(x.sessionMinutes, 1, 1440, 'Session length');
    ['start', 'end', 'targetDay', 'scheduledDay'].forEach(function (k) { if (x[k]) date(x[k]); });
    if (x.start && x.end) assert(x.start <= x.end, 'End date must follow start date');
    [['projectId', 'projects'], ['goalId', 'goals'], ['periodId', 'periods'], ['milestoneId', 'milestones'], ['cat', 'categories']].forEach(function (pair) { if (x[pair[0]] != null && x[pair[0]] !== '') requireItem(s, pair[1], x[pair[0]]); else if (pair[0] in x) x[pair[0]] = null; });
    if (x.milestoneId) { var m = find(s, 'milestones', x.milestoneId); assert(x.projectId && m.projectId === x.projectId, 'Choose a milestone from this project'); }
    if (group === 'recurring') {
      assert(['daily', 'weekdays', 'selected', 'weekly', 'interval'].indexOf(x.repeat) >= 0, 'Choose a recurrence');
      if (x.repeat === 'selected') assert(Array.isArray(x.days) && x.days.length && x.days.every(function (d) { return Number.isInteger(d) && d >= 0 && d <= 6; }), 'Choose at least one weekday');
      if (x.repeat === 'interval') { x.every = number(x.every, 1, 365, 'Repeat interval'); assert(Number.isInteger(x.every), 'Choose a whole number of days'); }
      if (x.repeat === 'weekly') { x.weekday = number(x.weekday, 0, 6, 'Weekday'); assert(Number.isInteger(x.weekday), 'Choose a weekday'); }
    }
    if (x.status) assert(['active', 'backlog', 'doing', 'waiting', 'done'].indexOf(x.status) >= 0, 'Invalid task status');
    if ('diff' in x) assert(Q.DIFF[x.diff], 'Choose a valid difficulty');
    ['gold', 'xp'].forEach(function (k) { if (k in x && x[k] != null) x[k] = number(x[k], 0, 1000000, 'Custom ' + k); });
    return x;
  }
  function merge(s, incoming, now) {
    var source = copy(incoming), hash = 2166136261, serialized = JSON.stringify(source);
    for (var h = 0; h < serialized.length; h++) hash = Math.imul(hash ^ serialized.charCodeAt(h), 16777619);
    if (!source.origin) source.origin = 'legacy-import-' + (hash >>> 0).toString(36);
    var inc = normalize(source, now), maps = {};
    ['categories'].concat(collections).forEach(function (k) {
      maps[k] = {};
      inc[k].forEach(function (x) {
        var existing = s[k].find(function (z) { return z.uid === x.uid || (k === 'categories' && z.name === x.name) || (k === 'completed' && z.at === x.at && z.title === x.title); });
        if (existing) { maps[k][x.id] = existing.id; return; }
        maps[k][x.id] = Q.newId(s);
      });
    });
    ['categories'].concat(collections).forEach(function (k) {
      inc[k].forEach(function (original) {
        var id = maps[k][original.id]; if (s[k].some(function (z) { return z.id === id; })) return;
        var x = copy(original); x.id = id;
        [['taskId', 'quests'], ['fromRecurring', 'recurring'], ['projectId', 'projects'], ['milestoneId', 'milestones'], ['goalId', 'goals'], ['periodId', 'periods'], ['cat', 'categories']].forEach(function (p) { if (x[p[0]] != null) x[p[0]] = maps[p[1]][x[p[0]]] || null; });
        if (k === 'sessions' && x.status === 'running') { settle(x, now); x.status = 'recovery'; x.needsAttention = true; }
        if (k === 'completed') { s.gold += x.gold || 0; s.goldEarned += x.gold || 0; Q.addXp(s, x.xp || 0); }
        s[k].push(x);
      });
    });
    Object.keys(inc.reviews).forEach(function (day) {
      if (s.reviews[day]) return;
      var r = copy(inc.reviews[day]), outcomes = {};
      Object.keys(r.outcomes || {}).forEach(function (id) { if (maps.quests[id]) outcomes[maps.quests[id]] = r.outcomes[id]; });
      r.outcomes = outcomes; s.reviews[day] = r;
    });
    Q.checkAch(s);
  }
  function reduce(s, cmd, now) {
    var p = cmd.payload || {}, x, q, f, group = p.group;
    switch (cmd.type) {
    case 'task.add':
      f = validateFields(s, 'quests', p); x = create(s, 'quests', Object.assign({title: 'Untitled quest', obj: '', diff: 'normal', cat: null, projectId: null, due: null, pinned: false, started: null, status: 'active', checklist: []}, f)); x.workflow = x.status; if (x.status === 'done') { x.status = 'active'; complete(s, x, now); } break;
    case 'task.check': q = requireItem(s, 'quests', p.id); assert(q.checklist[p.index], 'Checklist item no longer exists'); q.checklist[p.index].done = !!p.done; break;
    case 'task.edit':
      q = requireItem(s, 'quests', p.id); f = validateFields(s, 'quests', Object.assign({}, q, p.fields)); delete f.id; delete f.uid;
      if (f.status === 'done' && q.status !== 'done') complete(s, q, now);
      assert(!(q.status === 'done' && f.status !== 'done'), 'Completed tasks retain their completion history; create a new task to repeat the work');
      Object.assign(q, f); q.workflow = q.status; break;
    case 'task.complete':
      q = requireItem(s, 'quests', p.id);
      if (p.day) { date(p.day); assert(q.fromRecurring && q.occurrenceDay === p.day, 'Routine completion must use its occurrence date'); }
      complete(s, q, now, p.day); break;
    case 'task.archive': q = requireItem(s, 'quests', p.id); q.archived = true; break;
    case 'task.reorder':
      var i = s.quests.findIndex(function (t) { return t.id === p.id; }), j = i + p.direction;
      if (i >= 0 && j >= 0 && j < s.quests.length) { x = s.quests[i]; s.quests[i] = s.quests[j]; s.quests[j] = x; } break;
    case 'session.start':
      q = requireItem(s, 'quests', p.taskId); assert(q.status !== 'done' && !q.archived, 'Choose an open task');
      var minutes = number(p.minutes, 1, 1440, 'Session minutes'); q.sessionMinutes = minutes; q.status = q.workflow = 'doing';
      x = snapshot(q); Object.assign(x, {kind: 'timer', status: 'running', limitMs: minutes * MIN, segments: [], runStart: now, createdAt: now, needsAttention: false}); create(s, 'sessions', x); break;
    case 'session.pause': case 'session.finish': case 'session.resume': case 'session.extend':
      x = requireItem(s, 'sessions', p.id); assert(x.kind === 'timer', 'Choose a timer session');
      if (cmd.type === 'session.resume') { assert(['paused', 'recovery'].indexOf(x.status) >= 0 && baseMs(x) < x.limitMs, 'Extend the session or finish it'); x.runStart = now; x.status = 'running'; x.needsAttention = false; }
      else if (cmd.type === 'session.extend') { assert(x.status !== 'finished', 'Start a new session'); settle(x, now); x.limitMs += number(p.minutes, 1, 1440, 'Extension minutes') * MIN; x.runStart = now; x.status = 'running'; x.needsAttention = false; }
      else { settle(x, now); x.status = cmd.type === 'session.pause' ? 'paused' : 'finished'; x.needsAttention = false; }
      break;
    case 'sessions.recover': s.sessions.forEach(function (r) { if (r.status === 'running') { settle(r, now); r.status = 'recovery'; r.needsAttention = true; } }); break;
    case 'sessions.pauseAll': case 'sessions.finishAll': s.sessions.forEach(function (r) { if (r.status === 'running' || r.needsAttention) { settle(r, now); r.status = cmd.type === 'sessions.pauseAll' ? 'paused' : 'finished'; r.needsAttention = false; } }); break;
    case 'log.save':
      q = requireItem(s, 'quests', p.taskId); date(p.day);
      var duration = number(p.minutes, 1 / 60, 1440, 'Logged minutes') * MIN, segments = [];
      if (p.start != null || p.end != null) { assert(isFinite(p.start) && isFinite(p.end) && p.end > p.start && p.end - p.start <= 24 * HOUR, 'Choose a valid start/end range up to 24 hours'); assert(trackingDay(s, p.start) === p.day, 'Start time must belong to the selected tracking day'); segments = [{start: p.start, end: p.end}]; duration = p.end - p.start; }
      if (p.id) { x = requireItem(s, 'sessions', p.id); assert(x.kind === 'manual', 'Timer records cannot be replaced with manual entries'); }
      else x = create(s, 'sessions', Object.assign(snapshot(q), {kind: 'manual', status: 'finished', createdAt: now}));
      Object.assign(x, snapshot(q), {day: p.day, durationMs: duration, segments: segments, note: p.note || ''}); break;
    case 'log.delete': x = requireItem(s, 'sessions', p.id); assert(x.status !== 'running', 'Pause this session first'); s.sessions = s.sessions.filter(function (r) { return r.id !== p.id; }); break;
    case 'session.correct':
      x = requireItem(s, 'sessions', p.id); assert(x.kind === 'timer' && x.status === 'finished', 'Finish the session before correcting it'); date(p.day);
      x.originalSession = copy(x); x.kind = 'manual'; x.day = p.day; x.durationMs = number(p.minutes, 0, 1440, 'Corrected minutes') * MIN; x.segments = []; x.note = p.note || ''; break;
    case 'allocation.save':
      q = requireItem(s, 'quests', p.taskId); date(p.day); var amount = number(p.minutes, 1, 1440, 'Planned minutes');
      x = p.id ? requireItem(s, 'allocations', p.id) : s.allocations.find(function (a) { return a.taskId === q.id && a.day === p.day; });
      if (x && x.routine) assert(x.day === p.day && x.taskId === q.id, 'Routine occurrences keep their scheduled day; edit the routine schedule instead');
      if (!x) x = create(s, 'allocations', {taskId: q.id, day: p.day});
      s.allocations = s.allocations.filter(function (a) { return a.id === x.id || a.taskId !== q.id || a.day !== p.day; });
      x.taskId = q.id; x.day = p.day; x.minutes = amount; break;
    case 'allocation.delete': s.allocations = s.allocations.filter(function (a) { return a.id !== p.id; }); break;
    case 'routine.save':
      f = validateFields(s, 'recurring', p.fields);
      if (p.id) { x = requireItem(s, 'recurring', p.id); Object.assign(x, f); x.materializedThrough = shift(trackingDay(s, now), -1); }
      else create(s, 'recurring', Object.assign({state: 'active', createdDay: trackingDay(s, now), obj: '', diff: 'normal'}, f));
      rollover(s, now); break;
    case 'routine.addOccurrence':
      x = requireItem(s, 'recurring', p.routineId); date(p.day);
      assert(x.state !== 'archived', 'Choose an active or paused routine');
      occurrence(s, x, p.day, true); break;
    case 'routine.state':
      x = requireItem(s, 'recurring', p.id); assert(['active', 'paused', 'archived'].indexOf(p.state) >= 0, 'Invalid routine state'); x.state = p.state; x.materializedThrough = trackingDay(s, now);
      if (p.state !== 'active') {
        var today = trackingDay(s, now);
        s.quests.forEach(function (t) { if (t.fromRecurring === x.id && t.occurrenceDay >= today && t.status !== 'done' && !s.sessions.some(function (r) { return r.taskId === t.id; })) t.archived = true; });
        s.allocations = s.allocations.filter(function (a) { var t = find(s, 'quests', a.taskId); return !(t && t.archived && t.fromRecurring === x.id && a.day >= today); });
      } else { x.materializedThrough = shift(trackingDay(s, now), -1); s.quests.forEach(function (t) { if (t.fromRecurring === x.id && t.occurrenceDay === trackingDay(s, now)) t.archived = false; }); rollover(s, now); }
      break;
    case 'dayOff.save':
      date(p.start); date(p.end); assert(p.start <= p.end, 'End date must follow start date'); x = create(s, 'daysOff', {start: p.start, end: p.end, label: p.label || 'Day off'});
      s.quests.forEach(function (t) { if (t.occurrenceDay >= p.start && t.occurrenceDay <= p.end && !t.manualOccurrence && t.status !== 'done' && !t.archived && !s.sessions.some(function (r) { return r.taskId === t.id; })) { t.archived = true; t.suppressedByOff = true; } });
      s.allocations = s.allocations.filter(function (a) { var t = find(s, 'quests', a.taskId); return !(a.routine && t && t.archived && off(s, a.day)); }); break;
    case 'dayOff.delete':
      x = find(s, 'daysOff', p.id); if (!x) break;
      s.daysOff = s.daysOff.filter(function (d) { return d.id !== p.id; });
      restoreOff(s, x.start, x.end, now); break;
    case 'dayOff.clear':
      date(p.start); date(p.end); assert(p.start <= p.end, 'End date must follow start date');
      var periods = s.daysOff.filter(function (d) { return d.end >= p.start && d.start <= p.end; });
      if (!periods.length) break;
      periods.forEach(function (d) {
        if (d.end < p.start || d.start > p.end) return;
        var end = d.end;
        if (d.start < p.start) {
          d.end = shift(p.start, -1);
          if (end > p.end) create(s, 'daysOff', {start: shift(p.end, 1), end: end, label: d.label});
        } else if (end > p.end) d.start = shift(p.end, 1);
        else s.daysOff = s.daysOff.filter(function (other) { return other.id !== d.id; });
      });
      restoreOff(s, p.start, p.end, now); break;
    case 'review.save': case 'review.submit': case 'review.skip': case 'review.snooze': case 'review.prompt':
      date(p.day); x = s.reviews[p.day] || {day: p.day, outcomes: {}, status: 'draft'};
      if (cmd.type === 'review.prompt') x.nextPrompt = now + s.settings.reviewEvery * MIN;
      else if (cmd.type === 'review.snooze') x.nextPrompt = now + number(p.minutes, 1, 1440, 'Snooze minutes') * MIN;
      else if (cmd.type === 'review.skip') { x.status = 'skipped'; x.submittedAt = now; }
      else {
        Object.keys(p.outcomes || {}).forEach(function (id) { assert(['done', 'partial', 'notDone', 'skipped'].indexOf(p.outcomes[id]) >= 0, 'Choose a valid outcome'); requireItem(s, 'quests', Number(id)); });
        x.outcomes = p.outcomes || x.outcomes; if ('note' in p) x.note = p.note;
        if (cmd.type === 'review.submit') {
          assert(expected(s, p.day).every(function (t) { return t.status === 'done' || !!x.outcomes[t.id]; }), 'Choose an outcome for each scheduled task or routine');
          Object.keys(x.outcomes).forEach(function (id) { if (x.outcomes[id] === 'done') complete(s, requireItem(s, 'quests', Number(id)), now, p.day); });
          x.status = 'submitted'; x.submittedAt = now;
        }
      }
      s.reviews[p.day] = x; break;
    case 'entity.save':
      assert(['periods', 'goals', 'projects', 'milestones', 'categories'].indexOf(group) >= 0, 'Invalid entity type'); f = validateFields(s, group, p.fields);
      if (group === 'periods') { date(f.start); date(f.end); assert(f.start <= f.end, 'End date must follow start date'); }
      if (group === 'milestones') assert(f.projectId, 'A milestone needs a project');
      if (p.id) Object.assign(requireItem(s, group, p.id), f); else create(s, group, f); break;
    case 'entity.archive': assert(['periods', 'goals', 'projects', 'milestones', 'categories'].indexOf(group) >= 0, 'Invalid entity type'); requireItem(s, group, p.id).archived = true; break;
    case 'legacy.correct':
      x = requireItem(s, 'completed', p.id); assert(x.legacy, 'Choose a legacy record');
      if (p.accept) x.ms = x.originalMs; else x.ms = number(p.minutes, 0, 1000000, 'Corrected minutes') * MIN;
      x.timeReview = p.accept ? 'accepted' : 'corrected'; break;
    case 'settings.save':
      f = p.fields || {};
      if ('dayBoundary' in f) { number(f.dayBoundary, 0, 12, 'Day boundary'); assert(Number.isInteger(f.dayBoundary), 'Choose a whole-hour day boundary'); }
      if ('sessionMinutes' in f) number(f.sessionMinutes, 1, 1440, 'Default session');
      if ('reviewEvery' in f) number(f.reviewEvery, 1, 1440, 'Repeat interval');
      if ('reviewTime' in f) assert(/^([01]\d|2[0-3]):[0-5]\d$/.test(f.reviewTime), 'Choose a valid review time');
      if ('availability' in f) assert(Array.isArray(f.availability) && f.availability.length === 7 && f.availability.every(function (n) { return n == null || (isFinite(n) && n >= 0 && n <= 24); }), 'Availability must contain seven values between 0 and 24 hours');
      if ('weekStart' in f) number(f.weekStart, 0, 6, 'Week start');
      if ('boardReminder' in f) f.boardReminder = boardReminder(Object.assign({}, s.settings.boardReminder, f.boardReminder), now, s.settings.boardReminder);
      Object.keys(f).forEach(function (k) { assert(['dayBoundary', 'sessionMinutes', 'reviewEvery', 'reviewTime', 'reviewEnabled', 'startup', 'availability', 'weekStart', 'boardReminder'].indexOf(k) >= 0, 'Unknown setting'); });
      Object.assign(s.settings, f); break;
    case 'ui.save': Object.assign(s.ui, p); break;
    case 'import.merge': merge(s, p.data, now); break;
    case 'import.replace':
      assert(p.data && Array.isArray(p.data.quests) && Array.isArray(p.data.completed), 'This is not a QuestHUD backup');
      var replacement = normalize(copy(p.data), now); reduce(replacement, {type: 'sessions.recover'}, now); return replacement;
    case 'tick': rollover(s, now); break;
    default: throw new Error('Unknown command: ' + cmd.type);
    }
    return s;
  }
  function apply(input, cmd, now) {
    now = now == null ? Date.now() : now;
    var s = copy(input);
    if (cmd.requestId && s.requestIds.indexOf(cmd.requestId) >= 0) return s;
    expire(s, now); s = reduce(s, cmd, now);
    if (cmd.requestId) { s.requestIds.push(cmd.requestId); s.requestIds = s.requestIds.slice(-200); }
    s.completed.forEach(function (c) { if (c.sessionBacked) c.ms = taskEffort(s, c.taskId, now); });
    s.totalMs = totalEffort(s, now); s.revision = (input.revision || 0) + 1;
    return s;
  }
  function makeStore(ready) {
    var listeners = [], local;
    function preview() {
      try { local = normalize(JSON.parse(localStorage.getItem('questHud') || 'null')); } catch (e) { local = defaults(); }
      ready({kind: 'local', load: function (cb) { cb(JSON.stringify(local)); }, dispatch: function (cmd, cb) {
        try { local = apply(local, cmd); localStorage.setItem('questHud', JSON.stringify(local)); listeners.forEach(function (f) { f(); }); cb && cb({ok: true, state: local}); }
        catch (e) { cb && cb({ok: false, error: e.message}); }
      }, onChange: function (fn) { listeners.push(fn); }, onNavigate: function () {}, setOpacity: function () {}, setZoom: function () {}, openPanel: function () { root.open('panel.html'); }, exportData: function () { var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(local, null, 2)], {type: 'application/json'})); a.download = 'questhud-backup.json'; a.click(); URL.revokeObjectURL(a.href); }, importData: function (cb) { var i = document.createElement('input'); i.type = 'file'; i.accept = '.json'; i.onchange = function () { var r = new FileReader(); r.onload = function () { cb(r.result); }; if (i.files[0]) r.readAsText(i.files[0]); }; i.click(); }});
    }
    if (root.QWebChannel && root.qt && root.qt.webChannelTransport) {
      new root.QWebChannel(root.qt.webChannelTransport, function (ch) { var b = ch.objects.bridge;
        ready({kind: 'bridge', testBoardReminder: function(){ b.testBoardReminder(); }, load: function (cb) { b.load(cb); }, dispatch: function (cmd, cb) { cmd.requestId = cmd.requestId || 'ui-' + Date.now() + '-' + Math.random(); b.dispatch(JSON.stringify(cmd), function (r) { if (cb) cb(JSON.parse(r)); }); }, onChange: function (fn) { b.dataChanged.connect(fn); }, onNavigate: function (fn) { b.navigate.connect(fn); b.getRoute(fn); }, setOpacity: function (v) { b.setWindowOpacity(v); }, setZoom: function (v) { b.setZoom(v); }, setCollapsed: function (v) { b.setCollapsed(v); }, openPanel: function (tab) { b.openView(tab || 'today'); }, exportData: function () { b.exportData(); }, importData: function (cb) { b.importData(cb); }});
      });
    } else preview();
  }
  Object.assign(Q, {VERSION: 4, normalize: normalize, defaultState: defaults, copy: copy, apply: apply, find: find, shiftDay: shift, dayBoundary: boundary, trackingDay: trackingDay, isOff: off, elapsed: elapsed, taskEffort: taskEffort, routineDue: routineDue, rollover: rollover, expected: expected, projectedRoutines: projectedRoutines, pendingReviews: pendingReviews, reviewAt: reviewAt, entries: entries, daySummary: daySummary, projectSummary: projectSummary, totalEffort: totalEffort, makeStore: makeStore});
})(window);
