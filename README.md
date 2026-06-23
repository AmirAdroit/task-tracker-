# Quest HUD

A minimal, always-on-top RPG task tracker for Windows. A translucent quest
overlay floats on top of everything you do — turn tasks into quests, earn XP
and gold, level up, and keep a timed history of everything you finish. A
separate control-panel window gives you full management, charts, and backups.

No accounts, no cloud, no telemetry. Everything lives in a single local file.

---

## Features

- **Always-on-top overlay** — a compact, translucent HUD that stays visible over your apps (drag it anywhere, park it in a corner).
- **Adjustable transparency** — toggle translucent/solid and set opacity right from the overlay.
- **Quests with rewards** — easy / normal / hard / epic difficulties, each granting gold and XP. Start a quest to run a timer, then complete it.
- **XP, levels, gold, achievements** — light progression that builds as you work.
- **Timed history** — every completed quest is logged with how long it took and when it finished.
- **Recurring quests** — daily, weekday, or weekly quests that respawn automatically.
- **Control panel** — a full dashboard window: edit/reorder quests, manage recurring templates, search & filter history, and view productivity charts.
- **Backup & restore** — export everything to JSON; import to replace or merge.
- **Live sync** — the overlay and the control panel share one data file, so changes appear in both instantly.

## Requirements

- Windows 10 or 11
- [Python 3.9+](https://www.python.org/downloads/) (the only dependency the installer can't fetch for you)

The first launch creates a local virtual environment and installs
[PySide6](https://pypi.org/project/PySide6/) automatically.

## Quick start

```bat
git clone https://github.com/AmirAdroit/task-tracker-.git
cd task-tracker-
run.bat
```

Or just download the files and **double-click `run.bat`**. The first run sets
itself up (about 1–2 minutes); after that it starts in a couple of seconds.

If Python isn't installed, `run.bat` will tell you where to get it — install it
with **"Add python.exe to PATH"** checked, then run it again.

### Start with Windows (optional)

Double-click **`install-startup.bat`** once. The HUD will then launch silently
each time you log in. For a silent manual launch any time, use
**`start-hud.vbs`**.

To undo: press `Win + R`, type `shell:startup`, and delete the *Quest HUD* shortcut.

## Usage

**Overlay**

- Drag it by the thin top strip. `–` hides it to the system tray; `✕` quits.
- The **⚙** button opens settings: *Solid background* toggle, *opacity* slider, and *Open control panel*.
- Add a quest in the input box, press **Start** to run its timer, then **Done** to log it.

**System tray** (bottom-right of Windows)

- *Show / hide overlay*
- *Open control panel*
- *Click-through* — lets the mouse pass straight through the overlay (pure glance mode)
- *Quit*

**Control panel** — five tabs:

| Tab | What it does |
|-----|--------------|
| Quests | Edit title, objective, difficulty and gold/XP rewards; reorder; start/complete/delete. |
| Recurring | Create daily / weekday / weekly quests that spawn automatically. |
| History | Full completion log with search, date filter, and sorting. |
| Stats | Quests done, total time, current streak, and 14-day charts. |
| Backup | Export everything to JSON, or import (replace / merge). |

## How it works

```
          ┌─────────────┐        ┌──────────────────┐
          │  Overlay    │        │  Control panel   │
          │  hud.html   │        │  panel.html      │
          └──────┬──────┘        └────────┬─────────┘
                 │   QWebChannel bridge    │
                 └───────────┬─────────────┘
                       data/quests.json   ← single source of truth
```

- The UI is plain HTML/CSS/JS. Shared logic (the data model, progression,
  recurring rollover, stats) lives in `quest-core.js`.
- `hud.py` is a small [PySide6](https://pypi.org/project/PySide6/) launcher. It
  hosts both pages in `QWebEngineView`s and exposes a `Bridge` object over
  `QWebChannel` that reads/writes a single JSON file. When either window saves,
  the other reloads — that's the live sync.
- No server, no ports, no network. If you open the HTML files directly in a
  browser (for preview), they fall back to `localStorage`.

## Project structure

```
task-tracker-/
├─ hud.py               # PySide6 launcher: overlay window, panel window, data bridge, tray
├─ hud.html             # Overlay UI
├─ panel.html           # Control-panel UI
├─ quest-core.js        # Shared data model + storage (used by both UIs)
├─ run.bat              # First-run setup + launch
├─ start-hud.vbs        # Silent launcher (used for daily / startup)
├─ install-startup.bat  # Adds a startup shortcut
├─ requirements.txt     # PySide6
└─ data/                # Created at runtime — your quests.json lives here (git-ignored)
```

## Your data

Everything is stored in `data/quests.json` next to the app. To back it up or
move to another PC, use **Backup → Export** in the control panel (or just copy
that file). To start over, quit the app and delete `data/quests.json`.

## Troubleshooting

- **"Python was not found"** — install Python from python.org with *Add to PATH* checked, then re-run `run.bat`.
- **The overlay looks solid instead of see-through** — some GPU/driver setups don't composite the transparent web view on the first try. Toggle *Solid background* off in ⚙, or restart the app. If it persists, open an issue with your Windows + GPU details.
- **It won't show over a game** — overlays can't draw over *exclusive-fullscreen* games. Switch the game to *borderless windowed* mode and it'll appear.
- **The control panel opens blank** — make sure `panel.html` and `quest-core.js` are present next to `hud.py`. Run from `run.bat` once so any errors print.
- **Reset everything** — quit, delete the `data/` folder, relaunch.

## Built with

- [PySide6](https://pypi.org/project/PySide6/) (Qt for Python) + Qt WebEngine
- Vanilla HTML / CSS / JavaScript — no build step, no frontend framework

## License

[MIT](LICENSE)
