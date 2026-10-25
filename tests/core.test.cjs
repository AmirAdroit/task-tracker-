'use strict';
process.env.TZ = 'UTC';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({window: {}, Date, Math, JSON, Number, Object, Array, String, Error, isFinite});
for (const file of ['quest-core.js', 'planner-core.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
const Q = context.window.QC, MIN = 60000, H = 60 * MIN;
const at = value => new Date(value).getTime();
const t0 = at('2026-10-18T12:00:00Z');
const plain = value => JSON.parse(JSON.stringify(value));
function fresh(now = t0) { const s = Q.defaultState(now); s.quests = []; s.recurring = []; s.completed = []; s.sessions = []; s.gold = s.goldEarned = s.totalMs = 0; return s; }
function apply(s, type, payload = {}, now = t0) { return Q.apply(s, {type, payload}, now); }
function task(s, title = 'Work', extra = {}) { return apply(s, 'task.add', {title, ...extra}); }
function last(s, group) { return s[group][s[group].length - 1]; }

test('review notes save independently, preserve plain text, and clear explicitly without rewards', () => {
  let s = fresh(); const initial = plain(s);
  const text = 'Call tomorrow\nیادآوری فارسی <script>literal</script>';
  s = apply(s, 'review.save', {day:'2026-10-18', note:'Today went well', nextDayNote:text});
  assert.deepEqual(plain(Q.nextDayReminder(s, '2026-10-19')), {sourceDay:'2026-10-18', targetDay:'2026-10-19', text});
  s = apply(s, 'review.save', {day:'2026-10-18', note:'Revised daily note'});
  assert.equal(s.reviews['2026-10-18'].nextDayNote, text);
  s = apply(s, 'review.save', {day:'2026-10-18', nextDayNote:''});
  assert.equal(s.reviews['2026-10-18'].note, 'Revised daily note');
  assert.equal(Q.nextDayReminder(s, '2026-10-19'), null);
  s = apply(s, 'review.save', {day:'2026-10-18', nextDayNote:' \n '});
  assert.equal(Q.nextDayReminder(s, '2026-10-19'), null);
  for (const key of ['quests','sessions','completed','gold','goldEarned','xp','level']) assert.deepEqual(plain(s[key]), initial[key], key);
});

test('next-day reminders follow tracking days, month ends, leap days and year ends', () => {
  let s = apply(fresh(), 'review.save', {day:'2026-12-31', nextDayNote:'New year'});
  assert.equal(Q.nextDayReminder(s, Q.trackingDay(s, at('2027-01-01T03:59:59Z'))), null);
  assert.equal(Q.nextDayReminder(s, Q.trackingDay(s, at('2027-01-01T04:00:00Z'))).text, 'New year');
  s = apply(s, 'review.save', {day:'2028-02-28', nextDayNote:'Leap day'});
  s = apply(s, 'review.save', {day:'2028-02-29', nextDayNote:'March'});
  assert.equal(Q.nextDayReminder(s, '2028-02-29').text, 'Leap day');
  assert.equal(Q.nextDayReminder(s, '2028-03-01').text, 'March');
});

test('saved draft, submitted and skipped reminders remain available on days off', () => {
  let s = fresh();
  for (const [day,status] of [['2026-10-18','draft'],['2026-10-19','submitted'],['2026-10-20','skipped']]) {
    s = apply(s, 'review.save', {day, nextDayNote:status});
    if (status === 'submitted') s = apply(s, 'review.submit', {day});
    if (status === 'skipped') s = apply(s, 'review.skip', {day});
    assert.equal(s.reviews[day].status, status);
    assert.equal(Q.nextDayReminder(s, Q.shiftDay(day,1)).text, status);
  }
  s = apply(s, 'dayOff.save', {start:'2026-10-21',end:'2026-10-21',label:'Rest'});
  assert.equal(Q.nextDayReminder(s, '2026-10-21').text, 'skipped');
});

test('catch-up reminders stay on the reviewed date and never automatically carry forward', () => {
  let s = apply(fresh(), 'review.save', {day:'2020-01-31', nextDayNote:'Historical reminder'});
  assert.equal(Q.nextDayReminder(s, '2020-02-01').text, 'Historical reminder');
  assert.equal(Q.nextDayReminder(s, '2026-10-19'), null);
  s = apply(s, 'tick', {}, t0 + 3 * 86400000);
  assert.equal(s.reviews['2020-02-01'], undefined);
  s = apply(s, 'review.save', {day:'2020-01-31', nextDayNote:'Updated'});
  assert.equal(Q.nextDayReminder(s, '2020-02-01').text, 'Updated');
  s = apply(s, 'review.save', {day:'2020-01-31', nextDayNote:''});
  assert.equal(Q.nextDayReminder(s, '2020-02-01'), null);
});

test('old saves and export/import preserve reminders while same-day merge keeps local reviews', () => {
  let old = fresh(); old.reviews['2026-10-18'] = {day:'2026-10-18',status:'draft',note:'Local daily note',outcomes:{}};
  old = Q.normalize(plain(old), t0);
  assert.equal(old.version, 4); assert.equal(Q.nextDayReminder(old, '2026-10-19'), null);
  let incoming = apply(fresh(), 'review.save', {day:'2026-10-18',nextDayNote:'Incoming conflict'});
  incoming = apply(incoming, 'review.submit', {day:'2026-10-19',note:'Daily',nextDayNote:'Tomorrow\nفارسی'});
  const roundTrip = Q.normalize(plain(incoming), t0);
  assert.equal(roundTrip.reviews['2026-10-19'].nextDayNote, 'Tomorrow\nفارسی');
  const replaced = apply(old, 'import.replace', {data:plain(incoming)});
  assert.equal(replaced.reviews['2026-10-18'].nextDayNote, 'Incoming conflict');
  const merged = apply(old, 'import.merge', {data:plain(incoming)});
  assert.equal(merged.reviews['2026-10-18'].note, 'Local daily note');
  assert.equal(merged.reviews['2026-10-18'].nextDayNote, undefined);
  assert.equal(merged.reviews['2026-10-19'].nextDayNote, 'Tomorrow\nفارسی');
  assert.deepEqual(plain(apply(merged, 'import.merge', {data:plain(incoming)}).reviews), plain(merged.reviews));
});

test('invalid next-day reminder types reject commands and imports without altering the save', () => {
  const s = fresh(), original = plain(s);
  for (const nextDayNote of [null, 42, {}, []]) {
    assert.throws(() => apply(s, 'review.save', {day:'2026-10-18',nextDayNote}), /must be text/);
    const invalid = plain(s); invalid.reviews['2026-10-18'] = {day:'2026-10-18',status:'draft',nextDayNote};
    assert.throws(() => Q.normalize(invalid, t0), /must be text/);
    assert.throws(() => apply(s, 'import.replace', {data:invalid}), /must be text/);
  }
  assert.deepEqual(plain(s), original);
});

test('migration preserves rewards and history, excludes suspicious legacy time, and stops old timers', () => {
  const old = {version: 2, gold: 50, goldEarned: 70, quests: [{id: 1, title: 'Old', started: t0 - 700 * H}], recurring: [], completed: [{title: 'Long', at: t0, ms: 744 * H, xp: 30}, {title: 'Short', at: t0, ms: H}], nextId: 2};
  const s = Q.normalize(old, t0);
  assert.equal(s.version, 4); assert.equal(s.gold, 50); assert.equal(s.completed[0].originalMs, 744 * H);
  assert.equal(s.completed[0].timeReview, 'pending'); assert.equal(Q.totalEffort(s, t0), H);
  assert.equal(s.quests[0].started, null); assert.equal(s.quests[0].legacyTimerNeedsReview, true);
  assert.equal(s.settings.trackingStart, '2026-10-18'); assert.equal(s.sessions.length, 0);
});
test('normalizing v4 keeps doing, waiting, and done independent of time', () => {
  let s = task(fresh()); const id = last(s, 'quests').id;
  s = apply(s, 'task.edit', {id, fields: {status: 'doing'}}); s = Q.normalize(s, t0);
  assert.equal(s.quests[0].status, 'doing'); assert.equal(s.sessions.length, 0);
});
test('three-hour sessions expire at exactly three hours even after 700 hours', () => {
  let s = task(fresh(), 'Gaming'), id = last(s, 'quests').id;
  s = apply(s, 'session.start', {taskId: id, minutes: 180}); const sid = last(s, 'sessions').id;
  s = apply(s, 'tick', {}, t0 + 700 * H);
  assert.equal(Q.elapsed(s.sessions[0], t0 + 900 * H), 3 * H); assert.equal(s.sessions[0].status, 'expired');
  assert.equal(s.quests[0].status, 'doing'); assert.equal(s.completed.length, 0); assert.equal(s.sessions[0].segments[0].end, t0 + 3 * H);
  s = apply(s, 'session.extend', {id: sid, minutes: 30}, t0 + 701 * H);
  s = apply(s, 'session.finish', {id: sid}, t0 + 701 * H + 15 * MIN);
  assert.equal(Q.elapsed(s.sessions[0], t0 + 900 * H), 3 * H + 15 * MIN);
});
test('pause and resume exclude gaps; repeat clicks cannot reset a running session', () => {
  let s = task(fresh()), id = s.quests[0].id;
  s = apply(s, 'session.start', {taskId: id, minutes: 60}); const sid = s.sessions[0].id;
  s = apply(s, 'session.pause', {id: sid}, t0 + 10 * MIN);
  s = apply(s, 'session.resume', {id: sid}, t0 + 2 * H);
  assert.throws(() => apply(s, 'session.resume', {id: sid}, t0 + 3 * H));
  s = apply(s, 'session.finish', {id: sid}, t0 + 2 * H + 20 * MIN);
  assert.equal(Q.elapsed(s.sessions[0], t0 + 10 * H), 30 * MIN);
});
test('shutdown recovery never resumes automatically and stays bounded', () => {
  let s = task(fresh()); s = apply(s, 'session.start', {taskId: s.quests[0].id, minutes: 60});
  s = apply(s, 'sessions.recover', {}, t0 + 15 * MIN);
  assert.equal(s.sessions[0].status, 'recovery'); assert.equal(s.sessions[0].needsAttention, true);
  assert.equal(Q.elapsed(s.sessions[0], t0 + 100 * H), 15 * MIN);
});
test('multiple timers count summed and unique time correctly', () => {
  let s = task(task(fresh(), 'A'), 'B');
  s = apply(s, 'session.start', {taskId: s.quests[0].id, minutes: 120});
  s = apply(s, 'session.start', {taskId: s.quests[1].id, minutes: 120}, t0 + 30 * MIN);
  const d = Q.daySummary(s, '2026-10-18', t0 + H);
  assert.equal(d.summedMs, 90 * MIN); assert.equal(d.uniqueMs, H); assert.equal(d.overlapMs, 30 * MIN);
});
test('manual duration belongs to selected day; edits and deletion never double count', () => {
  let s = task(fresh()); const taskId = s.quests[0].id;
  s = apply(s, 'log.save', {taskId, day: '2026-10-17', minutes: 120, note: 'Study'});
  assert.equal(Q.daySummary(s, '2026-10-17', t0).summedMs, 2 * H); assert.equal(Q.daySummary(s, '2026-10-17', t0).uniqueMs, 0);
  const id = s.sessions[0].id; s = apply(s, 'log.save', {id, taskId, day: '2026-10-17', minutes: 60});
  assert.equal(Q.totalEffort(s, t0), H); assert.equal(s.completed.length, 0);
  s = apply(s, 'log.delete', {id}); assert.equal(Q.totalEffort(s, t0), 0);
});
test('time ranges split at 04:00 including across month boundaries', () => {
  let s = task(fresh()); const taskId = s.quests[0].id;
  s = apply(s, 'log.save', {taskId, day: '2026-10-31', minutes: 120, start: at('2026-11-01T03:00:00Z'), end: at('2026-11-01T05:00:00Z')});
  assert.equal(Q.daySummary(s, '2026-10-31', t0).summedMs, H); assert.equal(Q.daySummary(s, '2026-11-01', t0).summedMs, H);
  assert.equal(Q.trackingDay(s, at('2026-10-18T01:00:00Z')), '2026-10-17');
});
test('invalid time ranges and zero-length timer sessions are rejected atomically', () => {
  let s = task(fresh()), before = JSON.stringify(s), taskId = s.quests[0].id;
  assert.throws(() => apply(s, 'session.start', {taskId, minutes: 0}));
  assert.throws(() => apply(s, 'log.save', {taskId, day: '2026-10-18', minutes: 30, start: t0, end: t0 - 1}));
  assert.equal(JSON.stringify(s), before);
});
test('completion grants rewards once and does not duplicate session effort', () => {
  let s = task(fresh()), id = s.quests[0].id;
  s = apply(s, 'log.save', {taskId: id, day: '2026-10-18', minutes: 60});
  s = apply(s, 'task.complete', {id}); const gold = s.gold;
  s = apply(s, 'task.complete', {id}); assert.equal(s.gold, gold); assert.equal(s.completed.length, 1); assert.equal(Q.totalEffort(s, t0), H);
});
test('request IDs make retried commands idempotent', () => {
  const c = {type: 'task.add', payload: {title: 'One'}, requestId: 'same'};
  const s = Q.apply(Q.apply(fresh(), c, t0), c, t0); assert.equal(s.quests.length, 1);
});
test('daily occurrences are independent and unfinished days never block tomorrow', () => {
  let s = apply(fresh(), 'routine.save', {fields: {title: 'Daily', repeat: 'daily', estimateMinutes: 15}});
  assert.equal(s.quests.length, 1); s = apply(s, 'tick', {}, t0 + 24 * H);
  assert.equal(s.quests.length, 2); assert.equal(s.quests[0].occurrenceDay, '2026-10-18'); assert.equal(s.quests[1].occurrenceDay, '2026-10-19');
  s = apply(s, 'tick', {}, t0 + 24 * H); assert.equal(s.quests.length, 2);
});
test('selected weekdays, weekly, and interval schedules respect boundaries', () => {
  const common = {state: 'active', createdDay: '2026-10-18'};
  assert.equal(Q.routineDue({...common, repeat: 'selected', days: [1, 3]}, '2026-10-19'), true);
  assert.equal(Q.routineDue({...common, repeat: 'selected', days: [1, 3]}, '2026-10-20'), false);
  assert.equal(Q.routineDue({...common, repeat: 'weekly', weekday: 0}, '2026-10-18'), true);
  assert.equal(Q.routineDue({...common, repeat: 'interval', every: 2, start: '2026-10-18', end: '2026-10-22'}, '2026-10-20'), true);
  assert.equal(Q.routineDue({...common, repeat: 'interval', every: 2, start: '2026-10-18', end: '2026-10-22'}, '2026-10-24'), false);
});
test('archived routines keep history and stop appearing', () => {
  let s = apply(fresh(), 'routine.save', {fields: {title: 'Daily', repeat: 'daily'}}), rid = s.recurring[0].id;
  s = apply(s, 'task.complete', {id: s.quests[0].id}); s = apply(s, 'routine.state', {id: rid, state: 'archived'});
  s = apply(s, 'tick', {}, t0 + 48 * H); assert.equal(s.quests.length, 1); assert.equal(s.completed.length, 1);
});
test('days off suppress occurrences and prompts, preserve deadlines and manual logging', () => {
  let s = task(fresh(), 'Deadline', {due: t0}); s = apply(s, 'routine.save', {fields: {title: 'Daily', repeat: 'daily'}});
  s = apply(s, 'dayOff.save', {start: '2026-10-18', end: '2026-10-20', label: 'Travel'});
  assert.equal(Q.expected(s, '2026-10-18').length, 0); assert.equal(s.quests[0].due, t0);
  assert.equal(Q.pendingReviews(s, t0 + 12 * H).length, 0);
  s = apply(s, 'tick', {}, t0 + 48 * H); assert.equal(s.quests.filter(q => !q.archived && q.fromRecurring).length, 0);
  s = apply(s, 'log.save', {taskId: s.quests[0].id, day: '2026-10-19', minutes: 30}); assert.equal(Q.daySummary(s, '2026-10-19', t0).summedMs, 30 * MIN);
});
test('review timing handles before/after-midnight and upgrade start without ancient catch-up', () => {
  let s = fresh(); assert.deepEqual(plain(Q.pendingReviews(s, at('2026-10-18T22:59:00Z'))), []);
  assert.deepEqual(plain(Q.pendingReviews(s, at('2026-10-18T23:00:00Z'))), ['2026-10-18']);
  s = apply(s, 'settings.save', {fields: {reviewTime: '01:00'}});
  assert.equal(Q.reviewAt(s, '2026-10-18'), at('2026-10-19T01:00:00Z'));
});
test('reviews preserve draft, require outcomes, and submit retrospectively without duplicate rewards', () => {
  let s = task(fresh()), id = s.quests[0].id;
  s = apply(s, 'allocation.save', {taskId: id, day: '2026-10-18', minutes: 60});
  s = apply(s, 'review.save', {day: '2026-10-18', note: 'draft', outcomes: {[id]: 'partial'}});
  assert.equal(s.reviews['2026-10-18'].status, 'draft');
  assert.throws(() => apply(s, 'review.submit', {day: '2026-10-18', outcomes: {}}));
  s = apply(s, 'review.submit', {day: '2026-10-18', outcomes: {[id]: 'done'}}, t0 + 24 * H);
  assert.equal(Q.daySummary(s, '2026-10-18', t0 + 24 * H).completed.length, 1);
  const gold = s.gold; s = apply(s, 'review.submit', {day: '2026-10-18', outcomes: {[id]: 'done'}}, t0 + 24 * H); assert.equal(s.gold, gold);
});
test('planning allocations do not duplicate tasks; capacity remains unset until supplied', () => {
  let s = task(fresh()), taskId = s.quests[0].id;
  s = apply(s, 'allocation.save', {taskId, day: '2026-10-18', minutes: 120}); s = apply(s, 'allocation.save', {taskId, day: '2026-10-19', minutes: 60});
  assert.equal(s.quests.length, 1); assert.equal(s.allocations.length, 2); assert.equal(Q.daySummary(s, '2026-10-18', t0).overCapacity, false);
  s = apply(s, 'settings.save', {fields: {availability: [1, null, null, null, null, null, null]}}); assert.equal(Q.daySummary(s, '2026-10-18', t0).overCapacity, true);
});
test('flexible periods, goal/project links, milestones, standalone tasks and rollups', () => {
  let s = apply(fresh(), 'entity.save', {group: 'periods', fields: {title: 'Season', start: '2026-10-18', end: '2027-01-16'}}), pid = s.periods[0].id;
  s = apply(s, 'entity.save', {group: 'goals', fields: {title: 'Learn', success: 'Build system', periodId: pid}}); const gid = s.goals[0].id;
  s = apply(s, 'entity.save', {group: 'projects', fields: {title: 'Lab', goalId: gid}}); const projectId = s.projects[0].id;
  s = apply(s, 'entity.save', {group: 'milestones', fields: {title: 'Restore proof', projectId, targetDay: '2026-11-01', done: false}});
  s = task(s, 'Project task', {projectId, estimateMinutes: 120, milestoneId: s.milestones[0].id}); const tid = last(s, 'quests').id;
  s = task(s, 'Independent'); assert.equal(last(s, 'quests').projectId, null);
  s = apply(s, 'log.save', {taskId: tid, day: '2026-10-18', minutes: 180}); const sum = Q.projectSummary(s, projectId, t0);
  assert.equal(sum.actualMs, 3 * H); assert.equal(sum.overrunMs, H); assert.equal(sum.remainingMs, 0); assert.equal(s.milestones[0].done, false);
});
test('backup merge remaps relationships and repeated merges add no records or rewards', () => {
  let original = task(fresh(), 'Imported'); original = apply(original, 'log.save', {taskId: original.quests[0].id, day: '2026-10-18', minutes: 60}); original = apply(original, 'task.complete', {id: original.quests[0].id});
  let dest = task(fresh(), 'Existing'); dest = apply(dest, 'import.merge', {data: plain(original)}); const count = dest.quests.length, gold = dest.gold;
  dest = apply(dest, 'import.merge', {data: plain(original)}); assert.equal(dest.quests.length, count); assert.equal(dest.gold, gold); assert.equal(dest.sessions[0].taskId, dest.quests[1].id);
});
test('repeated legacy backup merges are idempotent', () => {
  const legacy = {version: 2, quests: [{id: 1, title: 'Legacy', status: 'active'}], recurring: [], completed: [], categories: []};
  let s = apply(fresh(), 'import.merge', {data: legacy}); s = apply(s, 'import.merge', {data: legacy}); assert.equal(s.quests.length, 1);
});
test('correcting suspicious historical durations keeps originals and recomputes accepted totals', () => {
  let s = Q.normalize({version: 2, quests: [], completed: [{title: 'Long', at: t0, ms: 744 * H}], recurring: []}, t0);
  const id = s.completed[0].id; s = apply(s, 'legacy.correct', {id, minutes: 120}); assert.equal(Q.totalEffort(s, t0), 2 * H); assert.equal(s.completed[0].originalMs, 744 * H);
});
test('correcting a completed timer preserves original segments and updates completion effort', () => {
  let s = task(fresh()), tid = s.quests[0].id; s = apply(s, 'session.start', {taskId: tid, minutes: 60}); s = apply(s, 'task.complete', {id: tid}, t0 + H);
  s = apply(s, 'session.correct', {id: s.sessions[0].id, day: '2026-10-18', minutes: 15}); assert.equal(Q.totalEffort(s, t0 + H), 15 * MIN); assert.equal(s.completed[0].ms, 15 * MIN); assert.equal(s.sessions[0].originalSession.kind, 'timer');
});
test('removing a planned day off restores current occurrences without duplicating them', () => {
  let s = apply(fresh(), 'routine.save', {fields: {title: 'Daily', repeat: 'daily'}});
  s = apply(s, 'dayOff.save', {start: '2026-10-18', end: '2026-10-18'});
  s = apply(s, 'dayOff.delete', {id: s.daysOff[0].id});
  assert.equal(Q.expected(s, '2026-10-18').length, 1); assert.equal(s.quests.length, 1); assert.equal(s.allocations.length, 1);
});
test('future routine forecasts appear in planned capacity without creating future tasks', () => {
  let s = apply(fresh(), 'routine.save', {fields: {title: 'Daily', repeat: 'daily', estimateMinutes: 30}});
  assert.equal(s.quests.length, 1); assert.equal(Q.daySummary(s, '2026-10-19', t0).plannedMinutes, 30);
  s = apply(s, 'dayOff.save', {start: '2026-10-19', end: '2026-10-20'});
  assert.equal(Q.daySummary(s, '2026-10-19', t0).plannedMinutes, 0);
});
test('checklist changes never start a timer or reward a completion', () => {
  let s = task(fresh(), 'Checklist', {checklist: [{title: 'Inspect', done: false}]});
  s = apply(s, 'task.check', {id: s.quests[0].id, index: 0, done: true});
  assert.equal(s.quests[0].checklist[0].done, true); assert.equal(s.sessions.length, 0); assert.equal(s.gold, 0);
});
test('creating a completed task logs its reward once', () => {
  let s = task(fresh(), 'Already done', {status: 'done'});
  assert.equal(s.completed.length, 1); const gold = s.gold;
  s = apply(s, 'task.complete', {id: s.quests[0].id}); assert.equal(s.gold, gold);
});
test('malformed progression and time entries are rejected instead of risking corrupted totals', () => {
  const bad = plain(fresh()); bad.xpMax = 0;
  assert.throws(() => Q.normalize(bad, t0), /xpMax/);
  const invalid = plain(fresh()); invalid.sessions = [{id: 100, kind: 'timer', status: 'running', limitMs: -1, segments: []}];
  assert.throws(() => Q.normalize(invalid, t0), /timer/);
});
test('editing an allocation moves it instead of leaving a duplicate on the old date', () => {
  let s = task(fresh()), taskId = s.quests[0].id;
  s = apply(s, 'allocation.save', {taskId, day:'2026-10-18', minutes:60}); const id=s.allocations[0].id;
  s = apply(s, 'allocation.save', {taskId, day:'2026-10-19', minutes:90});
  s = apply(s, 'allocation.save', {id, taskId, day:'2026-10-19', minutes:120});
  assert.equal(s.allocations.length,1); assert.equal(s.allocations[0].day,'2026-10-19'); assert.equal(s.allocations[0].minutes,120);
});


test('routine validation uses only the active pattern and requires whole interval days', () => {
  let s = apply(fresh(), 'routine.save', {fields:{title:'Daily',repeat:'daily',every:'n/a',days:[],weekday:99}});
  assert.equal(s.quests.length, 1);
  assert.throws(() => apply(s, 'routine.save', {fields:{title:'Interval',repeat:'interval',every:1.5}}), /whole/);
  assert.throws(() => apply(s, 'routine.save', {fields:{title:'Selected',repeat:'selected',days:[]}}), /weekday/);
  assert.throws(() => apply(s, 'routine.save', {fields:{title:'Weekly',repeat:'weekly',weekday:1.5}}), /weekday/);
});
test('clearing a middle day splits every overlapping period and keeps labels', () => {
  let s = apply(fresh(), 'dayOff.save', {start:'2026-10-18',end:'2026-10-22',label:'Rest'});
  s = apply(s, 'dayOff.save', {start:'2026-10-19',end:'2026-10-21',label:'Travel'});
  s = apply(s, 'dayOff.clear', {start:'2026-10-20',end:'2026-10-20'});
  assert.equal(s.daysOff.length, 4); assert.equal(Q.isOff(s,'2026-10-20'), undefined);
  assert.equal(Q.isOff(s,'2026-10-19').label, 'Rest'); assert.equal(Q.isOff(s,'2026-10-21').label, 'Rest');
  assert.equal(s.daysOff.filter(d=>d.label==='Travel').length, 2);
  const ids = s.daysOff.map(d=>d.uid);
  s = apply(s, 'dayOff.clear', {start:'2026-10-20',end:'2026-10-20'});
  assert.deepEqual(plain(s.daysOff.map(d=>d.uid)), plain(ids));
});
test('clearing range boundaries and whole periods leaves other dates untouched', () => {
  for (const range of [['2026-10-18','2026-10-18'],['2026-10-22','2026-10-22'],['2026-10-17','2026-10-23']]) {
    let s = apply(fresh(), 'dayOff.save', {start:'2026-10-18',end:'2026-10-22',label:'Rest'});
    s = apply(s, 'dayOff.clear', {start:range[0],end:range[1]});
    for(let i=18;i<=22;i++) {const day='2026-10-'+i; assert.equal(!!Q.isOff(s,day), !(range[0]<=day && day<=range[1]));}
  }
});
test('clearing past days restores only due active routines through today without duplicates', () => {
  let s = apply(fresh(), 'routine.save', {fields:{title:'Daily',repeat:'daily'}}), rid=s.recurring[0].id, original=s.quests[0].id;
  s = apply(s, 'dayOff.save', {start:'2026-10-18',end:'2026-10-22'});
  s = apply(s, 'tick', {}, t0+2*24*H);
  s = apply(s, 'dayOff.clear', {start:'2026-10-18',end:'2026-10-22'}, t0+2*24*H);
  assert.equal(s.quests.length,3); assert.equal(s.quests[0].id,original); assert.equal(s.quests[0].archived,false);
  assert.equal(s.allocations.length,3); assert.equal(s.quests.filter(q=>q.occurrenceDay>'2026-10-20').length,0);
  assert.equal(Q.projectedRoutines(s,'2026-10-22').length,1);
  s = apply(s,'dayOff.clear',{start:'2026-10-18',end:'2026-10-22'},t0+2*24*H);
  assert.equal(s.quests.length,3); assert.equal(s.allocations.length,3);
  for(const status of ['paused','archived']) {
    let p=apply(fresh(),'routine.save',{fields:{title:status,repeat:'daily'}});
    p=apply(p,'dayOff.save',{start:'2026-10-18',end:'2026-10-18'});
    p=apply(p,'routine.state',{id:p.recurring[0].id,state:status});
    p=apply(p,'dayOff.clear',{start:'2026-10-18',end:'2026-10-18'});
    assert.equal(p.recurring[0].state,status); assert.equal(Q.expected(p,'2026-10-18').length,0);
  }
});
test('clearing a day re-enables review eligibility and preserves submitted reviews and work', () => {
  let s = task(fresh()); const id=s.quests[0].id, evening=at('2026-10-18T23:30:00Z');
  s=apply(s,'log.save',{taskId:id,day:'2026-10-18',minutes:12});
  s=apply(s,'dayOff.save',{start:'2026-10-18',end:'2026-10-18'});
  assert.equal(Q.pendingReviews(s,evening).length,0);
  s=apply(s,'dayOff.clear',{start:'2026-10-18',end:'2026-10-18'},evening);
  assert.deepEqual(plain(Q.pendingReviews(s,evening)),['2026-10-18']);
  s=apply(s,'review.submit',{day:'2026-10-18',note:'Kept'},evening);
  s=apply(s,'dayOff.save',{start:'2026-10-18',end:'2026-10-18'},evening);
  s=apply(s,'dayOff.clear',{start:'2026-10-18',end:'2026-10-18'},evening);
  assert.equal(s.reviews['2026-10-18'].note,'Kept'); assert.equal(Q.pendingReviews(s,evening).length,0);
  assert.equal(Q.daySummary(s,'2026-10-18',evening).summedMs,12*MIN);
});
test('explicit day-off routines reuse suppressed occurrences and survive suppression', () => {
  let s=apply(fresh(),'routine.save',{fields:{title:'Dailies',repeat:'daily',estimateMinutes:15}});
  const rid=s.recurring[0].id, qid=s.quests[0].id;
  s=apply(s,'dayOff.save',{start:'2026-10-18',end:'2026-10-18'});
  for(let i=0;i<2;i++) s=apply(s,'routine.addOccurrence',{routineId:rid,day:'2026-10-18'});
  assert.equal(s.quests.length,1); assert.equal(s.quests[0].id,qid); assert.equal(s.quests[0].archived,false);
  assert.equal(s.allocations.length,1); assert.equal(s.quests[0].manualOccurrence,true);
  s=apply(s,'dayOff.save',{start:'2026-10-18',end:'2026-10-18'});
  assert.equal(s.quests[0].archived,false); assert.equal(Q.daySummary(s,'2026-10-18',t0).overCapacity,false);
  s=apply(s,'log.save',{taskId:qid,day:'2026-10-18',minutes:10});
  s=apply(s,'task.complete',{id:qid,day:'2026-10-18'}); const gold=s.gold;
  s=apply(s,'task.complete',{id:qid,day:'2026-10-18'});
  assert.equal(s.gold,gold); assert.equal(s.completed.length,1); assert.equal(Q.daySummary(s,'2026-10-18',t0).summedMs,10*MIN);
});
test('paused routines can be explicitly recorded retrospectively without resuming', () => {
  let s=apply(fresh(),'routine.save',{fields:{title:'Paused',repeat:'daily'}}), rid=s.recurring[0].id;
  s=apply(s,'routine.state',{id:rid,state:'paused'});
  s=apply(s,'routine.addOccurrence',{routineId:rid,day:'2026-10-17'});
  const q=last(s,'quests'); s=apply(s,'task.complete',{id:q.id});
  assert.equal(last(s,'completed').day,'2026-10-17'); assert.equal(last(s,'completed').at,t0);
  assert.equal(s.recurring[0].state,'paused');
  s=apply(s,'routine.state',{id:rid,state:'archived'});
  assert.throws(()=>apply(s,'routine.addOccurrence',{routineId:rid,day:'2026-10-19'}),/active or paused/);
});
test('board reminders default off; settings validate and preserve interval anchors', () => {
  let s=fresh(); assert.equal(s.settings.boardReminder.enabled,false);
  const b={enabled:true,mode:'interval',intervalMinutes:120,days:[0,1,2,3,4,5,6],windowStart:'22:00',windowEnd:'02:00'};
  s=apply(s,'settings.save',{fields:{boardReminder:b}}); assert.equal(s.settings.boardReminder.anchor,t0);
  s=apply(s,'settings.save',{fields:{boardReminder:b}},t0+H); assert.equal(s.settings.boardReminder.anchor,t0);
  assert.equal(Q.normalize(s,t0+H).settings.boardReminder.anchor,t0);
  s=apply(s,'settings.save',{fields:{boardReminder:{intervalMinutes:180}}},t0+H); assert.equal(s.settings.boardReminder.anchor,t0+H);
  assert.throws(()=>apply(s,'settings.save',{fields:{boardReminder:{mode:'daily',time:''}}}),/time/);
  assert.throws(()=>apply(s,'settings.save',{fields:{boardReminder:{days:[]}}}),/weekday/);
  assert.throws(()=>apply(s,'settings.save',{fields:{boardReminder:{intervalMinutes:0}}}),/interval/);
  assert.throws(()=>apply(s,'settings.save',{fields:{boardReminder:{windowEnd:'22:00'}}}),/start\/end/);
  const restored=apply(fresh(),'import.replace',{data:s}); assert.deepEqual(plain(restored.settings.boardReminder),plain(s.settings.boardReminder));
});
