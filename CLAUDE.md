# CLAUDE.md

Guidance for AI assistants and contributors working in this repo.

## What this is

Quest HUD: a Windows desktop app — a translucent always-on-top RPG task
overlay plus a control-panel window. It's a small [PySide6](https://pypi.org/project/PySide6/)
shell hosting two HTML/JS pages that share one JSON data file.

There is **no build step** and **no frontend framework**. Edit the files
directly. The only runtime dependency is PySide6.

## Architecture

```
quest-core.js  ──  shared data model + storage layer (the brain)
     ▲    ▲
     │    └──────── panel.html   (control-panel UI)
     └───────────── hud.html     (overlay UI)

hud.py  ──  PySide6 launcher: two QWebEngineView windows + a Bridge (QWebChannel)
            that owns data/quests.json. Emits dataChanged so windows stay in sync.
```

**Single source of truth:** `data/quests.json`. Both UIs read/write it through
the `Bridge` exposed over `QWebChannel`. When one window saves, `Bridge.save()`
emits `dataChanged`; both pages listen and reload (with a ~600 ms self-save
debounce to avoid loops). In a plain browser (no bridge), `quest-core.js` falls
back to `localStorage` — used only for preview.

## Key files

| File | Role |
|------|------|
| `quest-core.js` | All data logic: model, difficulties/rewards, XP/level, achievements, recurring rollover, stats, and `makeStore()` (bridge-or-localStorage). Exposed as `window.QC`. |
| `hud.html` | Overlay UI. Header + bars + active quests + add box + log + stats + achievements. Settings (⚙): transparency toggle, opacity slider, open panel. |
| `panel.html` | Control panel. Tabs: Quests, Recurring, History, Stats, Backup. Charts are drawn with plain `<canvas>` (no CDN). |
| `hud.py` | `Bridge` (QObject with `load/save/exportData/importData/setWindowOpacity/openPanel` + signals), `HUD` (frameless translucent always-on-top), `Panel` (normal resizable window), tray menu, geometry persistence. |
| `run.bat` / `start-hud.vbs` / `install-startup.bat` | Setup, silent launch, autostart. |

## State shape

```js
{
  version, level, xp, xpMax, gold, goldEarned, totalMs, nextId,
  quests:    [{ id, title, obj, diff, started, gold?, xp?, fromRecurring? }],
  recurring: [{ id, title, obj, diff, repeat:"daily"|"weekdays"|"weekly", weekday, lastDate }],
  completed: [{ title, ms, at, gold, xp }],
  ach:       { first, five, gold500, deep, lvl5 },
  ui:        { translucent, opacity }
}
```

- Rewards default from `QC.DIFF[diff]`; per-quest `gold`/`xp` are optional overrides.
- `QC.normalize()` heals/migrates any loaded object — always run loaded JSON through it.
- `QC.rollover(state)` spawns due recurring quests; safe to call repeatedly (it
  won't duplicate a template that already has an active instance today).

## Conventions

- Mutations live in `quest-core.js` and operate on a passed `state`; the **caller saves** (`store.save(JSON.stringify(state))`) and re-renders.
- Keep UI text sentence-case; keep the minimal/clean aesthetic (accent `#6e8efb`, dark translucent panels).
- Vanilla ES5-ish JS (no modules/bundler) so files load directly via `file://` and `qrc://`.
- Don't introduce a server, external CDNs, or telemetry. Charts stay canvas-based.
- **Manual entry only** — app sync (Todoist/Notion/etc.) is intentionally out of scope unless explicitly requested.

## Running & testing

- Run on Windows via `run.bat` (creates `.venv`, installs PySide6, launches).
- JS syntax: `node --check quest-core.js` and extract+check the inline `<script>` of each HTML file.
- Core logic can be exercised in Node by shimming `global.window = global`,
  `eval`-ing `quest-core.js`, then calling `window.QC` functions (no DOM needed
  for the model functions).
- Qt runtime behavior (transparency, the QWebChannel handshake, tray) can only
  be verified on an actual Windows machine.

## Gotchas

- **QWebEngine transparency** needs all of: window `WA_TranslucentBackground`, frameless flag, `page().setBackgroundColor(Qt.transparent)`, and transparent CSS `body`. The `--enable-transparent-visuals` chromium flag is set before the WebEngine import. Some GPUs still render opaque on first run.
- **QWebChannel** requires `<script src="qrc:///qtwebchannel/qwebchannel.js">` to load before `quest-core.js`. The channel must be set on the page (`page.setWebChannel`) before `page.load()`.
- **Two windows share one `QWebEngineProfile`** — keep a Python reference to the profile and bridge for the app's lifetime (held in `app._questhud`).
- **Truncation watch:** when regenerating `panel.html`/`hud.html`, confirm the file ends with `</script></body></html>` and that `grep -c "</script>"` matches the number of script tags — a past write got cut off mid-file.
