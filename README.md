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

Stable software rendering is the default. It avoids Chromium GPU compositing and uses full-frame Qt raster updates, including at fractional Windows scaling. This can use more CPU than automatic graphics. After an update, **quit from the tray and relaunch**; closing the panel alone keeps the existing UI process running. `start-stable.vbs` explicitly selects stable rendering. For a comparison/troubleshooting run, use `run.bat --renderer auto` or `QUESTHUD_RENDERER=auto` before launch. Rendering selection is outside task settings and does not change the JSON save.

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

The routine editor shows controls for the selected pattern: Daily needs no extra controls, Monday–Friday is fixed, Selected weekdays shows checkboxes, Weekly asks for one day, and Every N days asks for a whole-number interval (1–365) and an optional first-occurrence anchor. Without an anchor, intervals use the routine's creation date. Optional start/end dates and effort settings remain available. Switching patterns preserves your temporary input within the editor.

Plan **days off** using one date or an inclusive range, in advance or retrospectively. Automatic routine occurrences and daily review prompts are suppressed, and routine statistics exclude those dates. Catch-up waits until a normal tracking day. Deadlines, actual work and completions remain intact, and manual logging remains available.

Use **Remove day off** on Today's banner or the Journal's selected date to make that date normal again. Clearing a date inside a longer period splits the period and preserves its other dates and labels, including overlapping periods. Settings also offers **Remove days off…** for a range and **Remove entire period** for one saved period. Eligible active routines are restored through today without duplicate occurrences or rewards; future dates return to forecasting. Paused/archived routines stay paused/archived. Existing submitted reviews and work remain intact; cleared dates become eligible for normal reviews.

Use **Add routine to this day** in Today or Journal to choose an active or paused routine explicitly, even on a day off. Log time, start a session, or complete it normally without resuming its repeating schedule. Existing occurrences are reused. Manual logs and retrospective completions use the selected date; the actual completion timestamp is retained. Optional work counts toward effort without missed-routine penalties or rest-day capacity warnings.

## Board reminders

In **Settings → Board reminders**, enable one schedule: **At a daily time** or **Every X hours** (0.25–24 hours, in quarter-hour steps). Choose weekdays and, for interval reminders, optional active hours; overnight windows such as 22:00–02:00 are supported. Weekday choices refer to each reminder's local calendar date, independently of the tracking-day boundary. Board reminders run on planned days off. They are initially disabled until you configure them.

The native on-top window plays a bundled sound and offers **Open board** (Today), **Snooze 10 minutes**, and **Dismiss**. Unanswered windows sound again every ten minutes. Closing/Escape snoozes rather than dismissing. One alert remains pending; overlapping occurrences do not produce more windows or interrupt a snooze. Unsaved editors and settings are preserved; finish/save them before navigating to Today. **Test alert** previews the window and sound without saving or changing the schedule.

Interval cadence starts when its configuration is enabled/changed; the anchor survives restarts. Outside the chosen days/hours there are no alerts. Pending alerts end at local midnight or the active-hours end, whichever comes first. Resume/relaunch skips missed reminders and stale snoozes; only future schedule slots trigger. Windows power events and scheduling gaps over 90 seconds discard stale alerts. Daily review catch-up remains separate. Sound uses the current Windows audio device/volume; QuestHUD does not change volume, wake the PC, or run after you quit it.

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
| `board_reminder.py`, `board_alert.py`, `assets/board-alert.wav` | Transient reminder scheduler, native attention window and original bundled sound |
| `hud.html`, `hud-ui.js` | Compact overlay |
| `panel.html`, `panel.css`, `panel.js`, `ui-common.js`, `editor-controller.js` | Planner UI, commands and shared editor lifecycle |
| `tests/` | Model tests, native-service tests, syntax checks and isolated Windows UI smoke test |
| `data/` | Private runtime data, backups, profile/cache and local test artifacts; git-ignored |

Native changes are named commands, not whole-state replacements. The service applies a command to a candidate state, saves atomically, then publishes it. Failed commands/saves preserve the prior state. Recent request IDs prevent duplicate retries. A native scheduler expires sessions even when pages are hidden. UI updates preserve open editors and unsaved settings.

Control-panel editors prevent duplicate submissions while a save is pending. Delayed replies belong to their original editor and cannot close a newer draft or replace a newer snapshot. Editing linked records preserves archived relationships; archived options appear only when already selected. Long editors scroll internally with Save/Cancel visible, and menu/filter changes preserve clicks, keyboard navigation and same-view scroll positions.

Editors focus their first relevant field immediately. **Save or Ctrl+Enter** commits; Enter in ordinary fields does not save, and Enter in text areas inserts a newline. Native dropdown/date keys and Persian input composition remain available. Tab/Shift+Tab stays inside the editor. Escape, Cancel and Close restore focus after refreshing the page; if the original control disappeared, focus goes to the current view's heading. Validation errors retain the draft and return focus to a useful field. Settings also uses Save/Ctrl+Enter. This UI repair does not change the save format or require migration.

Background snapshots leave existing focused fields and their native selection/composition untouched. Unchanged header/HUD markup is retained rather than rebuilt for each review-note autosave, and duplicate/stale load notifications do not redraw an already accepted revision. The view heading has a stable focus anchor for late updates after an opening control is removed. Closing an editor completes its lifecycle without waiting for Chromium's render-timed close event. Native shutdown destroys pages before the shared browser profile.

The panel's native **Repair display** button (or **Ctrl+Shift+R** while the panel is focused) repaints its surfaces without reloading, resizing the viewport, changing task state, or discarding an open editor. **Recovery → Display details** shows the active renderer and a UI build fingerprint. The native controls remain available if the web content draws incorrectly. If repainting is insufficient, quit and relaunch in stable mode. A complete renderer/process crash can still lose an unsaved editor; saved tasks and native review drafts remain recoverable. There is no automatic destructive reset or profile deletion.

## Data, backups, and upgrades

Everything personal lives in `data/quests.json`. Local JSON is **not encrypted**; protect the Windows account and backup location. The whole `data/` directory is git-ignored. Never commit task data, screenshots containing real tasks, or exports to the public repository.

Before upgrading from v2/v3, QuestHUD makes a byte-for-byte backup in `data/backups/` with a `pre-v4` filename and content hash. It preserves categories, tasks, recurring templates, history and rewards. Old running timers are stopped and flagged for manual effort review. Legacy completed durations over 12 hours are preserved but excluded from effort totals until corrected or explicitly accepted in Settings. Completion records are never fabricated into historical sessions.

Existing v4 saves without board-reminder settings receive a byte-exact `pre-board-reminders` backup before additive defaults are saved. The JSON version remains 4. Export includes the reminder configuration and interval anchor; transient popups/snoozes are not exported. Import merge retains this installation's settings; import replace restores the backup's settings, with no missed-alert catch-up.

Settings → Backup exports all planning/tracking data. Import replace/merge makes a `pre-import` backup. Merge remaps entity relationships, deduplicates stable identities, and awards only newly imported completion rewards. Re-importing the same backup does not award them again. Malformed or newer saves fail visibly rather than resetting your data.

**Recovery:** quit QuestHUD, copy the chosen backup over `data/quests.json`, and relaunch. Only when rolling back across the schema boundary to a **v2/v3 application**, restore its corresponding pre-v4 save; those versions do not understand v4 sessions/reviews. For a v4-to-v4 UI rollback, keep current task data as described below. Keep off-device copies of exports or the save; automatic backups are on the same disk and do not protect against disk loss. Backup retention is manual.

### Verified app rollback

**Recovery → Create restore point** creates a private ZIP under `data/recovery/` with app files, task data, per-file sizes/SHA-256 hashes, and a format manifest. The folder/profile/virtual environment and Git internals are excluded. The archive is verified before it is finalized. Backups are unencrypted; keep them private and restore only your own trusted copies.

From this installation's folder:

```bat
recovery.bat create
recovery.bat list
recovery.bat verify "data\recovery\restore-EXAMPLE.zip"
```

**Quit from the tray first**, then roll back app files:

```bat
recovery.bat restore "data\recovery\restore-EXAMPLE.zip"
```

The default restores **code only**, preserving the current `quests.json` and newer work/rewards. It verifies the archive and destination paths, claims the same single-instance lock as the app, and makes another verified safety copy before applying any changes. It uses atomic file replacements and reverses completed replacements on a write failure. It does not reset Git history/branches or replace `.venv`. In this release both versions use the same dependencies and v4 data format.

To deliberately restore the snapshot's older task data too, add `--include-data`. This reverts work recorded since that snapshot; the pre-restore safety copy preserves the newer bytes. A corrupt current save can also be backed up as-is during recovery, but corrupt/newer-format archive data cannot be restored through this option. A checksum detects corruption, not the trustworthiness of executable code.

If power/process interruption leaves `data/recovery-in-progress.json`, the repaired app refuses to start. Rerun the restore command using the archive path recorded there; the record also identifies the pre-rollback safety copy. Do not delete task data to bypass recovery. Multi-file code replacement is not one filesystem-wide transaction; the marker and verified copies provide the resume/recovery path. Older code may not understand this marker, so finish recovery before launching any version.

For alternate test installations, pass `--data-dir` or set `QUESTHUD_DATA_DIR`. The recovery commands never launch the app automatically or kill a running instance. Use the newly created pre-rollback copy to undo a rollback while retaining current task data.

## Development and verification

```bat
node tests/check_syntax.cjs
node --test tests/core.test.cjs tests/ui.test.cjs tests/editor.test.cjs
.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe -B tests/smoke_windows.py
.venv\Scripts\python.exe -B tests/smoke_displays.py
.venv\Scripts\python.exe -B tests/smoke_accountability.py
.venv\Scripts\python.exe -B tests/smoke_panel.py
.venv\Scripts\python.exe -B tests/smoke_keyboard.py
.venv\Scripts\python.exe -B tests/smoke_rendering.py
.venv\Scripts\python.exe -B tests/smoke_recovery.py --working-tree
```

The smoke test opens the actual Qt windows using synthetic data under `data/ui-smoke/`, captures screenshots there, and checks QWebChannel synchronization, Persian text, editor preservation, session expiration, planner/journal rendering, routine creation and review drafts. It needs an interactive Windows desktop; CI runs syntax/model/native-service tests. Native tests use isolated data and test startup shortcuts only inside a temporary test folder.

The display smoke test repeatedly transfers an isolated HUD between the connected monitors, tests delayed DPI-inflation recovery, resizing persistence, all eight handles, folding, tray recovery, and quit shortcuts. It records synthetic screenshots and geometry under `data/display-smoke/`. Two differently scaled monitors are needed to exercise a real DPI transition; with one monitor, geometry/unit and simulated-inflation cases still run.

The accountability smoke test covers conditional recurrence controls, optional rest-day routines/logging, direct day-off removal, reminder settings, real native popup buttons, editor preservation and the Windows sound playback API. Screenshots use synthetic data under `data/accountability-smoke/`. Repeat/snooze/resume timings use injected clocks; these are not physical suspend/reboot or speaker-audibility tests. Use **Test alert** to check sound on your current audio device.

The panel smoke test uses synthetic data under `data/panel-ui-smoke/`. It injects delayed replies, double submits and background changes, exercises repeated task/goal/project editor navigation, archived links and completed-task allocations, and checks real Qt mouse/keyboard filter interactions, small-window layouts and scroll preservation. `tests/ui.test.cjs` covers out-of-order snapshots, form ownership, duplicate-submit protection and recovery after failed saves in CI.

The keyboard smoke test opens the actual Qt editors and types through Qt key events, including immediate multiword titles, punctuation, numbers, selection/deletion, Tab/Shift+Tab, Enter, Ctrl+Enter and Escape. It covers entity/task/routine forms, native dropdown/date controls, textarea newlines, failed-save correction, rapid reopening, delayed replies, background changes, Settings and HUD sessions. It commits Persian text through Qt's input-method API and separately simulates composition event ordering. These are not physical Windows keyboard-layout tests. Normal/minimum-size screenshots remain private under `data/keyboard-smoke/`. `tests/editor.test.cjs` runs keyboard policy and composition guards in CI; native picker/focus assertions require the Windows smoke test.

The rendering soak runs 32 editor cycles by default, exercises actual Qt IME preedit plus background snapshots, checks that review autosave performs no header replacement/caret resets, suppresses native close events, and compares frames before/after native repair. Captures wait for unchanged, nonblank pixels as well as completed style restoration; a JavaScript reply alone does not mean the browser's frame has reached Qt. Resizes synchronize both viewport dimensions; native Windows captures provide separate visual evidence. CI retains only synthetic PNG/result files for seven days on failure. Run `QUESTHUD_RENDERER=auto` in a fresh process for the graphics comparison. `QUESTHUD_SOAK_CYCLES` sets the cycle count. The fixture restores only its own minimized test window, requires visible/exposed browser state, records exposure recoveries, and uses test-owned Qt focus so occlusion/focus changes do not masquerade as paint failures. Pixel captures cover visible samples, not proof against every driver-level fault. Current results distinguish actual available monitors from simulated/offscreen DPI cases.

`tests/smoke_recovery.py --baseline <commit>` restores that committed code in a temporary installation, retains newer synthetic work/rewards, launches the restored native app and undoes the rollback. `--working-tree` tests unpublished changes. Pre-fix versions need test-owned browser teardown for that launch check; the repaired version exercises its own ordered shutdown. Native recovery unit tests inject write failures, tampering, unsafe paths and a running-instance lock; no personal data is used. CI runs an offscreen software rendering check and an isolated current-commit rollback/launch in addition to model/native checks. Offscreen CI does not replace physical Windows/monitor tests.

For an isolated manual installation:

```powershell
$env:QUESTHUD_DATA_DIR = Join-Path $PWD 'data\sandbox'
.\.venv\Scripts\python.exe -B hud.py
```

No environment variables are required for normal operation. `QUESTHUD_DATA_DIR` isolates task data/profile/instance lock and disables host startup integration. Do not point it at another running installation's save. `QUESTHUD_RENDERER` optionally selects `software` or `auto`; command-line `--renderer` takes precedence. `QTWEBENGINE_CHROMIUM_FLAGS` retains unrelated diagnostic flags; stable mode adds GPU/compositing-disable flags, sets `QT_QUICK_BACKEND=software` and disables partial raster updates. No sandbox-disabling flags are added. See [Qt WebEngine diagnostics](https://doc.qt.io/qt-6/qtwebengine-debugging.html), [Qt software rendering and fractional DPI](https://doc.qt.io/qt-6/qtquick-visualcanvas-adaptations-software.html) and [Chromium compositor switches](https://chromium.googlesource.com/chromium/src/+/master/content/public/common/content_switches.cc).

## Troubleshooting and limitations

- **Blank panel:** keep all HTML/JS/CSS files together. Run `run.bat` to see Python errors. Check asset completeness with the syntax command.
- **Flicker/duplicated pieces while editing:** use native Repair display, then quit from the tray and relaunch with `start-stable.vbs` if needed. Check Recovery → Display details to distinguish a still-running older build. The renderer can emit native fallback/teardown diagnostics even when page/frame checks pass; report the active mode and build fingerprint. Do not wipe the save or browser profile as a workaround.
- **No daily reviews:** check Settings, planned days off, whether the app is in the tray, and Windows notification settings. A persistent pending-review indicator remains available.
- **No board alert/sound:** enable and save its schedule, check its weekdays/active hours, and use Test alert. Check your output device/volume. Missed board alerts deliberately do not catch up; these reminders need the Windows app running, and work on days off.
- **Save error:** the app reports it and retains its previous state. Resolve disk/permission problems before retrying. Never delete the save to work around an error.
- **Transparent HUD appears opaque:** toggle Solid background, restart, or check GPU drivers. Fullscreen/GPU composition varies between machines.
- **Unexpected totals:** compare summed and unique effort. Review legacy corrections and parallel sessions. Time is self-reported; there is no activity surveillance.
- Plain-browser preview uses `localStorage`, separate from the desktop save. Native notifications/startup/instance protection are unavailable there.
- No external calendar/task sync, cloud account, mobile app, or automatic rescheduling. Actual work/quarter priorities must be entered explicitly.

Future improvements: portable packaging, optional encrypted exports, and richer calendar interaction. Keep operational reliability ahead of extra integrations.

## License

[MIT](LICENSE)
