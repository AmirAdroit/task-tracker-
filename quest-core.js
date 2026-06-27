/* quest-core.js — shared data model + storage for the overlay and the control panel.
   Single source of truth = a JSON file on disk via the Python bridge (QWebChannel).
   Falls back to localStorage when opened in a plain browser (preview mode). */
(function (root) {
  "use strict";

  var DIFF = {
    easy:   { color: "#7bb86b", xp: 30,  gold: 15  },
    normal: { color: "#6e8efb", xp: 60,  gold: 35  },
    hard:   { color: "#d6743b", xp: 120, gold: 80  },
    epic:   { color: "#b06bd6", xp: 250, gold: 180 }
  };
  var DIFF_ORDER = ["easy", "normal", "hard", "epic"];

  /* Urgency is a separate axis from difficulty. Difficulty = reward size;
     urgency = how soon it matters. Urgency is *derived* (from the due date +
     a manual pin), never stored. rank is used for sorting (lower = hotter). */
  var URGENCY = {
    emergency: { color: "#e24b4a", label: "Emergency", rank: 0 },
    high:      { color: "#ef9f27", label: "High",      rank: 1 },
    normal:    { color: "#6e8efb", label: "Normal",    rank: 2 }
  };

  var CAT_COLORS = ["#378add", "#7f77dd", "#1d9e75", "#d4537e", "#ef9f27",
                    "#97c459", "#d6743b", "#5dcaa5"];

  var ACHS = [
    { key: "first",   icon: "⚑", name: "First Blood — finish 1 quest" },
    { key: "five",    icon: "✦", name: "On a Roll — finish 5 quests" },
    { key: "gold500", icon: "◉", name: "Coin Collector — hold 500 gold" },
    { key: "deep",    icon: "⏳", name: "Deep Work — a quest 25 min+" },
    { key: "lvl5",    icon: "★", name: "Seasoned — reach level 5" }
  ];

  function defaultState() {
    return {
      version: 3,
      level: 1, xp: 0, xpMax: 100, gold: 0, goldEarned: 0, totalMs: 0,
      nextId: 24,
      categories: [
        { id: 1, name: "Work",     color: "#378add" },
        { id: 2, name: "Personal", color: "#7f77dd" },
        { id: 3, name: "Study",    color: "#1d9e75" }
      ],
      quests: [
        { id: 21, title: "Set up my quest HUD", obj: "You're looking at it", diff: "easy",   status: "active",  cat: null, due: null, pinned: false, started: null },
        { id: 22, title: "Plan today's top task", obj: "Pick the one that matters", diff: "normal", status: "active",  cat: 1,    due: null, pinned: false, started: null },
        { id: 23, title: "Tackle the big one", obj: "The thing you keep avoiding", diff: "hard", status: "backlog", cat: null, due: null, pinned: false, started: null }
      ],
      recurring: [],   /* templates: {id,title,obj,diff,repeat,weekday,lastDate,cat,dueOffset} */
      completed: [],   /* {title, ms, at, gold, xp, cat} */
      ach: { first: false, five: false, gold500: false, deep: false, lvl5: false },
      ui: { translucent: true, opacity: 1.0, hudScale: 1.0 }
    };
  }

  /* migrate / heal any loaded state so old saves keep working */
  function normalize(s) {
    var d = defaultState();
    if (!s || typeof s !== "object") return d;
    for (var k in d) if (!(k in s)) s[k] = d[k];
    if (!Array.isArray(s.quests)) s.quests = [];
    if (!Array.isArray(s.recurring)) s.recurring = [];
    if (!Array.isArray(s.completed)) s.completed = [];
    if (!Array.isArray(s.categories)) s.categories = d.categories;
    if (!s.ach) s.ach = d.ach;
    if (!s.ui) s.ui = d.ui;
    if (typeof s.ui.hudScale !== "number") s.ui.hudScale = 1.0;
    if (typeof s.nextId !== "number") s.nextId = 1;
    /* heal the new per-quest fields on older saves */
    s.quests.forEach(function (q) {
      if (q.status !== "backlog") q.status = "active";
      if (!("cat" in q)) q.cat = null;
      if (!("due" in q)) q.due = null;
      if (!("pinned" in q)) q.pinned = false;
    });
    return s;
  }

  function newId(s) { var id = s.nextId || 1; s.nextId = id + 1; return id; }

  /* ---------- formatting ---------- */
  function fmtDur(ms) {
    var sec = Math.round(ms / 1000), h = Math.floor(sec / 3600); sec -= h * 3600;
    var m = Math.floor(sec / 60); sec -= m * 60;
    if (h > 0) return h + "h " + m + "m";
    if (m > 0) return m + "m " + (sec < 10 ? "0" : "") + sec + "s";
    return sec + "s";
  }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function fmtClock(d) { return pad2(d.getHours()) + ":" + pad2(d.getMinutes()); }
  function fmtWhen(ts) {
    var d = new Date(ts), n = new Date(), same = d.toDateString() === n.toDateString();
    return (same ? "Today" : (d.getMonth() + 1) + "/" + d.getDate()) + " " + fmtClock(d);
  }
  function dayKey(ts) {
    var d = ts ? new Date(ts) : new Date();
    return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c];
    });
  }

  /* ---------- deadlines / urgency ---------- */
  function startOfDay(ts) { var d = new Date(ts); d.setHours(0, 0, 0, 0); return d.getTime(); }
  /* whole days from today to the due day: 0 = today, negative = overdue */
  function dueDaysLeft(due, now) {
    if (due == null) return null;
    return Math.round((startOfDay(due) - startOfDay(now || Date.now())) / 86400000);
  }
  function urgency(q, now) {
    if (q.pinned) return "emergency";
    var d = dueDaysLeft(q.due, now);
    if (d == null) return "normal";
    if (d <= 0) return "emergency";
    if (d <= 2) return "high";
    return "normal";
  }
  function urgencyColor(q, now) { return URGENCY[urgency(q, now)].color; }
  function fmtDue(due, now) {
    var d = dueDaysLeft(due, now);
    if (d == null) return "";
    if (d < 0) return "overdue " + (-d) + "d";
    if (d === 0) return "today";
    if (d === 1) return "tomorrow";
    if (d <= 6) return "in " + d + "d";
    var dt = new Date(due);
    return (dt.getMonth() + 1) + "/" + dt.getDate();
  }
  /* compare two quests for the overlay/board: hottest urgency, then soonest due, then order */
  function byHeat(now) {
    return function (a, b) {
      var ua = URGENCY[urgency(a, now)].rank, ub = URGENCY[urgency(b, now)].rank;
      if (ua !== ub) return ua - ub;
      var da = a.due == null ? Infinity : a.due, db = b.due == null ? Infinity : b.due;
      return da - db;
    };
  }

  /* ---------- categories ---------- */
  function catById(s, id) {
    if (id == null) return null;
    for (var i = 0; i < s.categories.length; i++) if (s.categories[i].id === id) return s.categories[i];
    return null;
  }
  function addCategory(s, fields) {
    var c = {
      id: newId(s),
      name: (fields.name || "New category").trim(),
      color: fields.color || CAT_COLORS[s.categories.length % CAT_COLORS.length]
    };
    s.categories.push(c);
    return c;
  }
  function editCategory(s, id, fields) {
    var c = catById(s, id); if (!c) return;
    if ("name" in fields) c.name = fields.name;
    if ("color" in fields) c.color = fields.color;
  }
  function removeCategory(s, id) {
    var i = s.categories.findIndex(function (c) { return c.id === id; });
    if (i < 0) return;
    s.categories.splice(i, 1);
    s.quests.forEach(function (q) { if (q.cat === id) q.cat = null; });
  }

  /* ---------- progression ---------- */
  function addXp(s, amount) {
    var ups = [];
    s.xp += amount;
    while (s.xp >= s.xpMax) {
      s.xp -= s.xpMax;
      s.level += 1;
      s.xpMax = Math.round(s.xpMax * 1.25);
      ups.push(s.level);
    }
    return ups;
  }
  function checkAch(s) {
    var a = s.ach;
    if (!a.first && s.completed.length >= 1) a.first = true;
    if (!a.five && s.completed.length >= 5) a.five = true;
    if (!a.gold500 && s.gold >= 500) a.gold500 = true;
    if (!a.deep && s.completed.some(function (c) { return c.ms >= 25 * 60 * 1000; })) a.deep = true;
    if (!a.lvl5 && s.level >= 5) a.lvl5 = true;
  }
  function reward(q) {
    var d = DIFF[q.diff] || DIFF.normal;
    return {
      gold: (typeof q.gold === "number") ? q.gold : d.gold,
      xp: (typeof q.xp === "number") ? q.xp : d.xp,
      color: d.color
    };
  }

  /* ---------- quest mutations (operate on state, caller saves) ---------- */
  function findIdx(s, id) { return s.quests.findIndex(function (q) { return q.id === id; }); }

  function addQuest(s, fields) {
    var q = {
      id: newId(s),
      title: (fields.title || "Untitled quest").trim(),
      obj: fields.obj || "",
      diff: DIFF[fields.diff] ? fields.diff : "normal",
      status: fields.status === "backlog" ? "backlog" : "active",
      cat: (fields.cat != null) ? fields.cat : null,
      due: (typeof fields.due === "number") ? fields.due : null,
      pinned: !!fields.pinned,
      started: null
    };
    if (typeof fields.gold === "number") q.gold = fields.gold;
    if (typeof fields.xp === "number") q.xp = fields.xp;
    s.quests.push(q);
    return q;
  }
  function editQuest(s, id, fields) {
    var i = findIdx(s, id); if (i < 0) return;
    var q = s.quests[i];
    if ("title" in fields) q.title = fields.title;
    if ("obj" in fields) q.obj = fields.obj;
    if ("diff" in fields && DIFF[fields.diff]) q.diff = fields.diff;
    if ("cat" in fields) q.cat = (fields.cat == null ? null : fields.cat);
    if ("due" in fields) q.due = (typeof fields.due === "number") ? fields.due : null;
    if ("pinned" in fields) q.pinned = !!fields.pinned;
    if ("gold" in fields) { if (fields.gold === null) delete q.gold; else q.gold = fields.gold; }
    if ("xp" in fields) { if (fields.xp === null) delete q.xp; else q.xp = fields.xp; }
  }
  /* move a quest between lanes. "backlog" parks it (and stops its timer);
     "active" commits it; "doing" commits it and starts the timer. */
  function setStatus(s, id, status) {
    var i = findIdx(s, id); if (i < 0) return;
    var q = s.quests[i];
    if (status === "backlog") { q.status = "backlog"; q.started = null; }
    else if (status === "doing") { q.status = "active"; if (!q.started) q.started = Date.now(); }
    else { q.status = "active"; q.started = null; }
  }
  function startQuest(s, id) { var i = findIdx(s, id); if (i >= 0) { s.quests[i].started = Date.now(); s.quests[i].status = "active"; } }
  function removeQuest(s, id) { var i = findIdx(s, id); if (i >= 0) s.quests.splice(i, 1); }
  function moveQuest(s, id, dir) {
    var i = findIdx(s, id); if (i < 0) return;
    var j = i + dir; if (j < 0 || j >= s.quests.length) return;
    var t = s.quests[i]; s.quests[i] = s.quests[j]; s.quests[j] = t;
  }
  function completeQuest(s, id) {
    var i = findIdx(s, id); if (i < 0) return [];
    var q = s.quests[i], ms = q.started ? (Date.now() - q.started) : 0, r = reward(q);
    s.quests.splice(i, 1);
    s.completed.unshift({ title: q.title, ms: ms, at: Date.now(), gold: r.gold, xp: r.xp, cat: q.cat });
    s.gold += r.gold; s.goldEarned += r.gold; s.totalMs += ms;
    var ups = addXp(s, r.xp);
    checkAch(s);
    return ups;
  }

  /* ---------- recurring ---------- */
  function recurDue(t, now) {
    var today = dayKey(now ? now.getTime() : Date.now());
    if (t.lastDate === today) return false;
    var dow = (now || new Date()).getDay(); /* 0=Sun..6=Sat */
    if (t.repeat === "daily") return true;
    if (t.repeat === "weekdays") return dow >= 1 && dow <= 5;
    if (t.repeat === "weekly") return dow === (t.weekday | 0);
    return false;
  }
  /* spawn any due recurring templates as active quests; returns true if state changed */
  function rollover(s, now) {
    var changed = false;
    (s.recurring || []).forEach(function (t) {
      var already = s.quests.some(function (q) { return q.fromRecurring === t.id; });
      if (!already && recurDue(t, now)) {
        var due = null;
        if (typeof t.dueOffset === "number") due = startOfDay(now ? now.getTime() : Date.now()) + t.dueOffset * 86400000;
        var q = addQuest(s, { title: t.title, obj: t.obj, diff: t.diff, cat: (t.cat != null ? t.cat : null), due: due });
        q.fromRecurring = t.id;
        t.lastDate = dayKey(now ? now.getTime() : Date.now());
        changed = true;
      }
    });
    return changed;
  }
  function addRecurring(s, fields) {
    var t = {
      id: newId(s),
      title: (fields.title || "Daily quest").trim(),
      obj: fields.obj || "",
      diff: DIFF[fields.diff] ? fields.diff : "normal",
      repeat: ["daily", "weekdays", "weekly"].indexOf(fields.repeat) >= 0 ? fields.repeat : "daily",
      weekday: (fields.weekday | 0),
      cat: (fields.cat != null) ? fields.cat : null,
      lastDate: null
    };
    if (typeof fields.dueOffset === "number") t.dueOffset = fields.dueOffset;
    s.recurring.push(t);
    return t;
  }
  function removeRecurring(s, id) {
    var i = s.recurring.findIndex(function (t) { return t.id === id; });
    if (i >= 0) s.recurring.splice(i, 1);
  }

  /* ---------- stats ---------- */
  function statsByDay(s, days) {
    days = days || 14;
    var out = [], today = new Date(); today.setHours(0, 0, 0, 0);
    for (var i = days - 1; i >= 0; i--) {
      var d = new Date(today.getTime() - i * 86400000);
      out.push({ key: dayKey(d.getTime()), label: (d.getMonth() + 1) + "/" + d.getDate(), count: 0, ms: 0 });
    }
    var map = {}; out.forEach(function (o) { map[o.key] = o; });
    s.completed.forEach(function (c) {
      var k = dayKey(c.at); if (map[k]) { map[k].count += 1; map[k].ms += c.ms; }
    });
    return out;
  }
  function streak(s) {
    var have = {}; s.completed.forEach(function (c) { have[dayKey(c.at)] = true; });
    var n = 0, d = new Date(); d.setHours(0, 0, 0, 0);
    /* allow today to be empty without breaking yesterday's streak */
    if (!have[dayKey(d.getTime())]) d = new Date(d.getTime() - 86400000);
    while (have[dayKey(d.getTime())]) { n += 1; d = new Date(d.getTime() - 86400000); }
    return n;
  }
  /* count of open quests (active or backlog) whose deadline has passed */
  function overdueCount(s, now) {
    return s.quests.filter(function (q) { var d = dueDaysLeft(q.due, now); return d != null && d < 0; }).length;
  }

  /* ---------- storage (bridge or localStorage) ---------- */
  function browserDownload(text, name) {
    try {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
      a.download = name || "quest-backup.json";
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    } catch (e) {}
  }
  function browserPick(cb) {
    var inp = document.createElement("input");
    inp.type = "file"; inp.accept = ".json,application/json";
    inp.onchange = function () {
      var f = inp.files && inp.files[0]; if (!f) { cb(""); return; }
      var r = new FileReader();
      r.onload = function () { cb(String(r.result || "")); };
      r.onerror = function () { cb(""); };
      r.readAsText(f);
    };
    inp.click();
  }

  function makeStore(onReady) {
    function localStore() {
      return {
        kind: "local",
        load: function (cb) { try { cb(localStorage.getItem("questHud") || ""); } catch (e) { cb(""); } },
        save: function (str) { try { localStorage.setItem("questHud", str); } catch (e) {} },
        exportData: function (str) { browserDownload(str, "quest-backup.json"); },
        importData: function (cb) { browserPick(cb); },
        onChange: function () {},
        setOpacity: function () {},
        setZoom: function () {},
        openPanel: function () { alert("Control panel opens from the app tray menu."); }
      };
    }
    if (root.QWebChannel && root.qt && root.qt.webChannelTransport) {
      try {
        new root.QWebChannel(root.qt.webChannelTransport, function (channel) {
          var b = channel.objects.bridge;
          onReady({
            kind: "bridge",
            load: function (cb) { b.load(function (r) { cb(r); }); },
            save: function (str) { b.save(str); },
            exportData: function (str) { b.exportData(str); },
            importData: function (cb) { b.importData(function (r) { cb(r); }); },
            onChange: function (fn) { b.dataChanged.connect(fn); },
            setOpacity: function (v) { b.setWindowOpacity(v); },
            setZoom: function (v) { if (b.setZoom) b.setZoom(v); },
            openPanel: function () { b.openPanel(); }
          });
        });
        return;
      } catch (e) { /* fall through */ }
    }
    onReady(localStore());
  }

  root.QC = {
    DIFF: DIFF, DIFF_ORDER: DIFF_ORDER, URGENCY: URGENCY, CAT_COLORS: CAT_COLORS, ACHS: ACHS,
    defaultState: defaultState, normalize: normalize, newId: newId,
    fmtDur: fmtDur, fmtWhen: fmtWhen, fmtClock: fmtClock, dayKey: dayKey, esc: esc,
    startOfDay: startOfDay, dueDaysLeft: dueDaysLeft, urgency: urgency, urgencyColor: urgencyColor,
    fmtDue: fmtDue, byHeat: byHeat,
    catById: catById, addCategory: addCategory, editCategory: editCategory, removeCategory: removeCategory,
    addXp: addXp, checkAch: checkAch, reward: reward,
    addQuest: addQuest, editQuest: editQuest, setStatus: setStatus, startQuest: startQuest,
    removeQuest: removeQuest, moveQuest: moveQuest, completeQuest: completeQuest,
    rollover: rollover, addRecurring: addRecurring, removeRecurring: removeRecurring,
    statsByDay: statsByDay, streak: streak, overdueCount: overdueCount,
    makeStore: makeStore
  };
})(window);
