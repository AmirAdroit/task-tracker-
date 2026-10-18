/* Shared formatting, RPG rewards, and legacy state defaults. Load before planner-core.js. */
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

  /* v4 mutations/storage are defined in planner-core.js, the sole command reducer. */
  root.QC = {
    DIFF:DIFF, DIFF_ORDER:DIFF_ORDER, URGENCY:URGENCY, CAT_COLORS:CAT_COLORS, ACHS:ACHS,
    defaultState:defaultState, normalize:normalize, newId:newId, fmtDur:fmtDur,
    fmtClock:fmtClock, fmtWhen:fmtWhen, dayKey:dayKey, esc:esc, startOfDay:startOfDay,
    dueDaysLeft:dueDaysLeft, urgency:urgency, urgencyColor:urgencyColor, fmtDue:fmtDue,
    byHeat:byHeat, catById:catById, addXp:addXp, checkAch:checkAch, reward:reward
  };
})(window);
