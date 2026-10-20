# Contributor and AI-agent context

QuestHUD is a local Windows planner with a compact RPG HUD and a full panel. Keep this one context file; do not add duplicate assistant-specific instruction files.

## Architecture

- `quest-core.js`: shared formatting/rewards/legacy defaults.
- `planner-core.js`: pure v4 domain model. `QC.apply(state, {type,payload,requestId?}, now)` returns a new candidate or throws. Never mutate canonical state from a page.
- `state_service.py`: single owner of canonical state inside QJSEngine, atomic JSON persistence, migration/import backups, scheduler helpers and startup integration.
- `board_reminder.py`: injected-clock native reminder state machine; transient alerts/snoozes are never replayed after launch/resume. `board_alert.py` owns the non-modal popup and bundled Windows sound, not domain state.
- `hud.py`: native windows/tray, QWebChannel, one-second maintenance tick, single-instance guard and graceful quit.
- `window_geometry.py`: logical-pixel work-area fitting, real-screen selection and eight-edge resize regions. Never multiply QWidget geometry by DPR; preserve the user-selected logical size across `WM_DPICHANGED`/screen events. Use system move/resize and coalesce deferred native geometry changes.
- `panel.js` / `hud-ui.js` render snapshots; `ui-common.js` provides command helpers and delegates `U.dialog` to `editor-controller.js`. Load core, planner, editor controller, common helpers, then the page script. `panel.css` is shared only by the panel; preserve HUD transparency.

Bridge interface: `load()` returns JSON; `dispatch(commandJson)` returns `{ok,state,error?}`; `dataChanged` prompts reload. `openView(route)`/`navigate` route reviews. Pages cannot call an unrestricted save method. Export reads canonical state. Web previews use the same reducer with localStorage and lack native scheduling.

`testBoardReminder()` previews native UI without saving. Board configuration lives in `settings.boardReminder` (enabled/mode/time/intervalMinutes/days/windowStart/windowEnd/anchor); settings changes re-anchor intervals, unrelated saves do not. `routine.addOccurrence {routineId,day}` explicitly reuses/restores one active/paused occurrence. `dayOff.clear {start,end}` subtracts dates from all overlapping periods; keep identities/labels on remaining fragments. `task.complete` accepts a validated matching routine occurrence date; actual timestamps remain intact.

## Invariants

- Status never starts a timer. Sessions, tasks, allocations, reviews, and dated routine occurrences have separate identities.
- All timer work is bounded. Expiration is idempotent and never completes a task. Explicit extension starts at confirmation, excluding the gap.
- Multiple timers are legitimate. Summed effort and unique range-union time differ. Duration-only manual and legacy time never enter unique-time totals.
- Dates use a configurable local tracking-day boundary (default 04:00). Calendar arithmetic must handle month/year boundaries. Manual duration-only days stay explicit.
- A routine date is unique per template; old unfinished dates cannot block newer dates. Pausing/archiving never destroys recorded history.
- Planned time off suppresses routine generation/review prompts and is neutral in routine statistics. Actual work/deadlines remain.
- Board reminders run on days off; their local calendar schedule is independent of tracking-day boundaries. One native alert, ten-minute repeat/snooze, no missed-alert catch-up. Never change system volume.
- Explicit manual routine occurrences survive day-off suppression. Clearing time off restores eligible active occurrences through today, never resumes paused/archived routines, and never duplicates allocations/rewards. Keep days off neutral in capacity warnings.
- Hide and disable irrelevant recurrence controls; validate only the chosen repeat pattern and preserve editor input across changes. Use explicit Monday-Friday wording rather than inferring local weekends.
- Completion rewards apply once. Session/manual corrections update totals without re-awarding XP/gold.
- Failed commands and failed writes must preserve memory and disk. Validate imported records before replacing state. Reject unsupported newer formats.
- Before a schema migration/import, make a byte-exact local backup. Never silently replace an invalid file with defaults.
- Preserve stable `uid` identities across exports/merges, remap numeric references, and deduplicate completion rewards.
- Preserve originals for suspicious legacy durations and corrected timer records. Do not invent historical ranges.
- A background signal must not wipe typed fields, settings, open dialogs or focus. Review drafts save as the user types.
- Each editor owns its DOM and pending submission. Late replies must not close a later editor, attach errors to it or replace a snapshot with a lower revision. Preserve conditional disabled states when unlocking after a failed save.
- Keep editor focus, explicit Save/Ctrl+Enter permission, composition guards, Tab boundaries and close/refresh/restoration in the shared controller. Focus the first visible field synchronously; never focus Close on entry. Ordinary Enter must not implicitly save. Preserve native textarea/select/date behavior and IME confirmation. Clear focus from a closed dialog before rendering, then restore the opener by stable identity or fall back to the current heading. Do not add a second close-refresh handler in page code.
- Preserve selected archived relationships during edits. Delay filter/date redraws until a pending pointer action has received its click; retain keyboard focus and same-view scroll. Keep long editor actions visible at 640x460.

## Conventions and safety

Vanilla JavaScript, no build step/framework/server/CDN/telemetry. Code must execute in Node, Chromium and QJSEngine. Use injected timestamps for domain tests. New mutations belong in the reducer. Keep UI strings sentence-case, dark styling, accent near `#6e8efb`, readable Persian with `dir="auto"`, labelled form inputs and keyboard focus states.

All personal data, backups, local screenshots and browser profiles remain under ignored `data/`. Never publish them. Tests use synthetic fixtures. `QUESTHUD_DATA_DIR` isolates manual tests and disables startup integration. Native service tests must not modify the real startup folder; use the helper's temporary-folder override.

Do not run old application instances against migrated data. Stop them after a safety backup before the first live upgrade. Startup belongs to this installation's named shortcut; do not change unrelated startup entries. Silent background launches use hidden windows.

## Commands and definition of done

Run from the repository root:

```bat
node tests/check_syntax.cjs
node --test tests/core.test.cjs tests/ui.test.cjs tests/editor.test.cjs
.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe -B tests/smoke_windows.py
.venv\Scripts\python.exe -B tests/smoke_displays.py
.venv\Scripts\python.exe -B tests/smoke_accountability.py
.venv\Scripts\python.exe -B tests/smoke_panel.py
.venv\Scripts\python.exe -B tests/smoke_keyboard.py
```

Install via `run.bat` (Python 3.10–3.14, pinned PySide6). The smoke test needs an interactive Windows desktop and opens real Qt windows. CI covers the first three commands on Windows. Inspect captured synthetic screenshots for layout quality; passing DOM assertions alone does not prove visual quality.

Editor regressions must include immediate typing after opening, not only assigning field values in JavaScript. Use Qt key events for ASCII and QInputMethodEvent commits for Persian; report simulated composition ordering separately from physical keyboard-layout/IME tests. Synchronize WebEngine's asynchronous key delivery before assertions. Verify Save through a real Qt pointer click too: native click default actions run after a microtask checkpoint, unlike a scripted `.click()` inside JavaScript. Use explicit Save button clicks in non-keyboard fixtures; direct `form.requestSubmit()` deliberately lacks commit permission. A native select/date popup may consume the first Escape before the editor can close.

Display regressions must test mixed-DPI transfers, legacy/off-screen geometry recovery, chosen-size persistence, close-button visibility and all edges/corners. Do not change OS display scale settings for tests. The tool-window HUD intentionally stays out of the taskbar; retain tray and keyboard recovery/quit paths.

Update README when features, requirements, state behavior, commands, backup or operation change. Meaningful model changes need boundary/failure tests. Verify migration preserves personal history/rewards and export/import round trips. Report actual Windows/notification/startup verification separately from simulations, and never claim a real reboot test from a simulated clock test.

Board-reminder additions keep v4 compatibility and create a pre-board-reminders backup for older v4 saves. Import merge preserves local settings; replace restores settings but never pending alerts. Smoke timings are simulated; a successful Windows sound call is not proof that the user heard it.

Known boundaries: no cloud/external calendar sync; local JSON is unencrypted; notification display depends on Windows; daily reviews catch up at launch/login, board alerts skip missed slots; backup retention is manual. Changing the boundary regroups ranged history. Planning capacity is unset until the user supplies availability.
