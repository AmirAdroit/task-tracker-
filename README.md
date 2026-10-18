# QuestHUD

An offline Windows personal planner with an always-on-top RPG overlay. Plan goals and projects, keep standalone tasks, track bounded sessions or manually record effort, and review your days without losing history.

**Status:** v4 implementation. Uses PySide6 6.11.1, Qt WebEngine, and plain HTML/CSS/JavaScript. No server, accounts, telemetry, CDN, or frontend build step.

## Install and run

Requires Windows 10/11 and **Python 3.10–3.14**. Node.js 22+ is needed only for development checks.

```bat
git clone https://github.com/AmirAdroit/task-tracker-.git
cd task-tracker-
run.bat
```

`run.bat` creates `.venv` and installs the pinned dependency. Run it again after upgrading the source. Use `start-hud.vbs` for silent launches. Settings → Start with Windows manages this installation's startup shortcut; it defaults to enabled. `install-startup.bat` remains available for manual setup.

Launching twice opens the existing installation instead of creating competing writers. The HUD's `–` hides it to the tray. `×` and tray → Quit offer to pause or finish unresolved sessions before quitting. Closing the control panel leaves the HUD running. Exclusive-fullscreen games may cover the HUD; use borderless mode when needed.

The overlay stays out of the taskbar. Drag its top strip to move it, and drag **any edge or corner** to resize it. Monitor changes preserve its chosen size in logical pixels; oversized or disconnected-display geometry is brought inside a real display's usable area. Windows display scaling stays enabled.

If the HUD becomes hard to reach, use tray → **Reset size and position**, **Resize overlay…**, or **Move overlay to display**. The same menu is available by right-clicking its top strip. **Ctrl+Shift+R** resets the focused HUD; **Ctrl+Q** or **Alt+F4** uses graceful quit. Moving to a selected display preserves the chosen size; Reset restores 300×560. Old geometry without the new logical-size setting is migrated once to that safe size.

## Everyday workflow

1. Create a task in **Quests**. A task can stand alone or belong to a project and optional milestone. Set its total effort estimate and default session length independently of its deadline and difficulty.
2. Use **Planner** to allocate effort to a date. The same task can have allocations on several days. Scheduling effort does not duplicate the task or change its deadline.
3. In **Today**, start a bounded session or choose **Log time**. At the cap, time stops and the app asks you to finish or extend. A task marked in progress does not accumulate time by itself.
4. Complete a task when its outcome is achieved. Finishing a session and completing a task are separate actions. Completion grants XP/gold once.
5. Fill in the daily check-in. Record Done, Partial, Not done, or Skipped for scheduled tasks/routines; add missing effort and optional notes.
6. Use **Journal** to inspect a date, edit manual records, correct completed timers, or review earlier days.

### Views

| View | Contents |
|---|---|
| Today | Scheduled work, routines, sessions, effort totals, check-in, quick logging |
| Planner | Flexible periods, goals with success criteria, projects, milestones, weekly allocations and availability warnings |
| Journal | Month calendar, daily work records, completions, review outcomes, days off |
| Quests | Standalone/project tasks, status board, filters, estimates, checklists, categories and rewards |
| Routines | Daily, Mon–Fri, selected weekdays, weekly, every-N-days; date bounds, pause/resume/archive |
| Stats | Daily planned/actual effort, categories, projects, estimate overruns and routine outcomes |
| Settings | Reminders, day boundary, session defaults, weekly availability, startup, days off, corrections, backup/import |

The HUD has Focus / Today / Backlog / Sessions / Done lenses, category filtering, quick add, timers/manual logs, and transparency/zoom controls. Open the panel for full planning and review.

## Time accounting

- Session lengths are chosen at start, with 25/60/90/180-minute presets and a custom value. The initial suggestion is 60 minutes; task choices are remembered.
- Multiple timers are supported. **Summed effort** adds task durations; **unique timed work** merges known overlapping ranges. Duration-only manual entries and accepted legacy durations are excluded from unique-time calculations.
- Pause/resume excludes the gap. Extending an expired session starts counting from the extension confirmation, never from the unanswered alarm.
- Locking/sleeping does not auto-pause a timer. The cap still applies. Unexpected shutdown recovery requires acknowledgment before continuing; it never resumes an unbounded timer.
- The tracking day begins at **04:00 local PC time** by default. A 01:00 session belongs to the preceding evening. Ranged sessions split at the boundary. Manual duration-only logs belong to the selected date.
- Changing the boundary regroups ranged historical time. Duration-only logs keep their explicit day. Dates are Gregorian; the week start is configurable.
- Historical timers can be corrected after finishing; the original session is retained inside the corrected record. Deleting an entry changes effort totals, not prior completion rewards.

## Reviews, routines, and time off

The initial review time is **23:00**, repeating every **30 minutes**, both editable. The panel opens with the review and offers 15/30/60-minute snoozes. Drafts save while you type. Closing the panel or a notification does not submit the review. Notifications can be suppressed by Windows, so pending reviews also appear in the HUD/panel.

Reviews begin on the upgrade tracking day. Startup/resume gathers unanswered days into one catch-up view; it never invents months of earlier obligations. The app must be running to notify. Start with Windows allows catch-up at the next login; QuestHUD does not wake a powered-off PC or relaunch itself after an explicit Quit until you launch it or log in again.

Each routine date is independent; an unfinished yesterday does not block today. Future routine effort is forecast in the weekly capacity totals without generating future task cards. Editing a routine affects future occurrences; existing occurrence records retain their recorded identity. Pause stops scheduling temporarily; archive stops future appearances while retaining history. Resume starts again from the current day without filling the paused interval.

Plan **days off** using one date or an inclusive range, in advance or retrospectively. Automatic routine occurrences and review prompts are suppressed, and routine statistics exclude those dates. Catch-up waits until a normal tracking day. Deadlines, actual work and completions remain intact, and manual logging remains available. Removing time off restores current suppressed occurrences.

## Architecture and repository

```text
HUD / panel → QWebChannel commands → StateService → QJSEngine / shared reducer
                                           ↓
                                  atomic data/quests.json
                                           ↓
                                 updated snapshot to both windows
```

| Files | Responsibility |
|---|---|
| `quest-core.js` | Formatting, RPG rewards and legacy defaults |
| `planner-core.js` | Migration, commands, sessions, reviews, recurrence, planning and aggregation |
| `state_service.py` | Canonical state, shared JS engine, persistence, backups, reminders, startup integration |
| `hud.py` | Windows, bridge, native scheduler, tray, single-instance guard and quit workflow |
| `hud.html`, `hud-ui.js` | Compact overlay |
| `panel.html`, `panel.css`, `panel.js`, `ui-common.js` | Planner UI and shared dialogs |
| `tests/` | Model tests, native-service tests, syntax checks and isolated Windows UI smoke test |
| `data/` | Private runtime data, backups, profile/cache and local test artifacts; git-ignored |

Native changes are named commands, not whole-state replacements. The service applies a command to a candidate state, saves atomically, then publishes it. Failed commands/saves preserve the prior state. Recent request IDs prevent duplicate retries. A native scheduler expires sessions even when pages are hidden. UI updates preserve open editors and unsaved settings.

## Data, backups, and upgrades

Everything personal lives in `data/quests.json`. Local JSON is **not encrypted**; protect the Windows account and backup location. The whole `data/` directory is git-ignored. Never commit task data, screenshots containing real tasks, or exports to the public repository.

Before upgrading from v2/v3, QuestHUD makes a byte-for-byte backup in `data/backups/` with a `pre-v4` filename and content hash. It preserves categories, tasks, recurring templates, history and rewards. Old running timers are stopped and flagged for manual effort review. Legacy completed durations over 12 hours are preserved but excluded from effort totals until corrected or explicitly accepted in Settings. Completion records are never fabricated into historical sessions.

Settings → Backup exports all planning/tracking data. Import replace/merge makes a `pre-import` backup. Merge remaps entity relationships, deduplicates stable identities, and awards only newly imported completion rewards. Re-importing the same backup does not award them again. Malformed or newer saves fail visibly rather than resetting your data.

**Recovery:** quit QuestHUD, copy the chosen backup over `data/quests.json`, and relaunch. To roll back to old application code, first restore its corresponding pre-v4 save; old code does not understand v4 sessions/reviews. Keep off-device copies of exports or the save; automatic backups are on the same disk and do not protect against disk loss. Backup retention is manual.

## Development and verification

```bat
node tests/check_syntax.cjs
node --test tests/core.test.cjs
.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe -B tests/smoke_windows.py
.venv\Scripts\python.exe -B tests/smoke_displays.py
```

The smoke test opens the actual Qt windows using synthetic data under `data/ui-smoke/`, captures screenshots there, and checks QWebChannel synchronization, Persian text, editor preservation, session expiration, planner/journal rendering, routine creation and review drafts. It needs an interactive Windows desktop; CI runs syntax/model/native-service tests. Native tests use isolated data and test startup shortcuts only inside a temporary test folder.

The display smoke test repeatedly transfers an isolated HUD between the connected monitors, tests delayed DPI-inflation recovery, resizing persistence, all eight handles, folding, tray recovery, and quit shortcuts. It records synthetic screenshots and geometry under `data/display-smoke/`. Two differently scaled monitors are needed to exercise a real DPI transition; with one monitor, geometry/unit and simulated-inflation cases still run.

For an isolated manual installation:

```powershell
$env:QUESTHUD_DATA_DIR = Join-Path $PWD 'data\sandbox'
.\.venv\Scripts\python.exe -B hud.py
```

`QUESTHUD_DATA_DIR` is the only environment override; no variables are required for normal operation. Setting it disables host startup integration and gives that directory its own instance lock/profile. Do not point it at another running installation's save.

## Troubleshooting and limitations

- **Blank panel:** keep all HTML/JS/CSS files together. Run `run.bat` to see Python errors. Check asset completeness with the syntax command.
- **No reminders:** check Settings, planned days off, whether the app is in the tray, and Windows notification settings. A persistent pending-review indicator remains available.
- **Save error:** the app reports it and retains its previous state. Resolve disk/permission problems before retrying. Never delete the save to work around an error.
- **Transparent HUD appears opaque:** toggle Solid background, restart, or check GPU drivers. Fullscreen/GPU composition varies between machines.
- **Unexpected totals:** compare summed and unique effort. Review legacy corrections and parallel sessions. Time is self-reported; there is no activity surveillance.
- Plain-browser preview uses `localStorage`, separate from the desktop save. Native notifications/startup/instance protection are unavailable there.
- No external calendar/task sync, cloud account, mobile app, or automatic rescheduling. Actual work/quarter priorities must be entered explicitly.

Future improvements: portable packaging, optional encrypted exports, and richer calendar interaction. Keep operational reliability ahead of extra integrations.

## License

[MIT](LICENSE)
