# Contributor and AI-agent context

QuestHUD is a local Windows planner with a compact RPG HUD and a full panel. Keep this one context file; do not add duplicate assistant-specific instruction files.

## Architecture

- `quest-core.js`: shared formatting/rewards/legacy defaults.
- `planner-core.js`: pure v4 domain model. `QC.apply(state, {type,payload,requestId?}, now)` returns a new candidate or throws. Never mutate canonical state from a page.
- `state_service.py`: single owner of canonical state inside QJSEngine, atomic JSON persistence, migration/import backups, scheduler helpers and startup integration.
- `hud.py`: native windows/tray, QWebChannel, one-second maintenance tick, single-instance guard and graceful quit.
- `panel.js` / `hud-ui.js` render snapshots; `ui-common.js` provides command-based dialogs. Both load core scripts in order. `panel.css` is shared only by the panel; preserve HUD transparency.

Bridge interface: `load()` returns JSON; `dispatch(commandJson)` returns `{ok,state,error?}`; `dataChanged` prompts reload. `openView(route)`/`navigate` route reviews. Pages cannot call an unrestricted save method. Export reads canonical state. Web previews use the same reducer with localStorage and lack native scheduling.

## Invariants

- Status never starts a timer. Sessions, tasks, allocations, reviews, and dated routine occurrences have separate identities.
- All timer work is bounded. Expiration is idempotent and never completes a task. Explicit extension starts at confirmation, excluding the gap.
- Multiple timers are legitimate. Summed effort and unique range-union time differ. Duration-only manual and legacy time never enter unique-time totals.
- Dates use a configurable local tracking-day boundary (default 04:00). Calendar arithmetic must handle month/year boundaries. Manual duration-only days stay explicit.
- A routine date is unique per template; old unfinished dates cannot block newer dates. Pausing/archiving never destroys recorded history.
- Planned time off suppresses routine generation/review prompts and is neutral in routine statistics. Actual work/deadlines remain.
- Completion rewards apply once. Session/manual corrections update totals without re-awarding XP/gold.
- Failed commands and failed writes must preserve memory and disk. Validate imported records before replacing state. Reject unsupported newer formats.
- Before a schema migration/import, make a byte-exact local backup. Never silently replace an invalid file with defaults.
- Preserve stable `uid` identities across exports/merges, remap numeric references, and deduplicate completion rewards.
- Preserve originals for suspicious legacy durations and corrected timer records. Do not invent historical ranges.
- A background signal must not wipe typed fields, settings, open dialogs or focus. Review drafts save as the user types.

## Conventions and safety

Vanilla JavaScript, no build step/framework/server/CDN/telemetry. Code must execute in Node, Chromium and QJSEngine. Use injected timestamps for domain tests. New mutations belong in the reducer. Keep UI strings sentence-case, dark styling, accent near `#6e8efb`, readable Persian with `dir="auto"`, labelled form inputs and keyboard focus states.

All personal data, backups, local screenshots and browser profiles remain under ignored `data/`. Never publish them. Tests use synthetic fixtures. `QUESTHUD_DATA_DIR` isolates manual tests and disables startup integration. Native service tests must not modify the real startup folder; use the helper's temporary-folder override.

Do not run old application instances against migrated data. Stop them after a safety backup before the first live upgrade. Startup belongs to this installation's named shortcut; do not change unrelated startup entries. Silent background launches use hidden windows.

## Commands and definition of done

Run from the repository root:

```bat
node tests/check_syntax.cjs
node --test tests/core.test.cjs
.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe -B tests/smoke_windows.py
```

Install via `run.bat` (Python 3.10–3.14, pinned PySide6). The smoke test needs an interactive Windows desktop and opens real Qt windows. CI covers the first three commands on Windows. Inspect captured synthetic screenshots for layout quality; passing DOM assertions alone does not prove visual quality.

Update README when features, requirements, state behavior, commands, backup or operation change. Meaningful model changes need boundary/failure tests. Verify migration preserves personal history/rewards and export/import round trips. Report actual Windows/notification/startup verification separately from simulations, and never claim a real reboot test from a simulated clock test.

Known boundaries: no cloud/external calendar sync; local JSON is unencrypted; notification display depends on Windows; PC-off reminders occur at next launch/login; backup retention is manual. Changing the boundary regroups ranged history. Planning capacity is unset until the user supplies availability.
