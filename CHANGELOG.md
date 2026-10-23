# Changelog

## 4.0.5 — rendering stability and recoverable rollback

- Retain unchanged header/HUD DOM, deduplicate repeated snapshot notifications, and leave surviving focused fields/IME selection untouched during review autosaves. A reproduced 144-character entry previously caused 288 header rebuilds and 288 range resets; the repaired path causes zero of either. Preserve the heading focus anchor across late updates after archiving.
- Complete editor teardown independently of delayed browser close events. Release native browser pages before their shared profile at shutdown.
- Default to stable software rendering with full raster updates, retain an explicit automatic-graphics comparison, and add native Repair display/recovery controls plus a build/mode report.
- Add verified app/data restore points, path/hash/size checks, a running-instance guard, pre-rollback safety copies, failed-write reversal and interrupted-restore marker. Code rollback preserves newer task data by default; data recovery is explicit. No domain-model/schema migration.
- Add rendering/IME/frame stress, headless CI rendering and native rollback/launch drills alongside the existing keyboard, panel, accountability, native and display checks. Require visible, nonblank, settled frames and synchronized viewports; retain synthetic failure screenshots. Report physical-monitor and simulated/offscreen coverage separately.

## 4.0.4 — reliable editor keyboard handling

- Centralize editor focus, explicit Save/Ctrl+Enter commits, composition guards, Tab boundaries and close/refresh/focus restoration while retaining the existing dialog interface and style.
- Focus titles immediately instead of Close, prevent accidental implicit Enter saves, preserve textarea newlines and native dropdown/date/IME keys, and show the save shortcut.
- Clear obsolete closed-input focus before refreshing; restore the opening control or current heading. Keep drafts and editing focus after failed validation, with existing pending-save and stale-reply protection.
- Add actual Qt keyboard/IME editor regressions, normal/minimum-size captures and CI keyboard-policy tests; update existing fixtures to activate Save explicitly. No data migration or domain behavior changes.

## 4.0.3 — control-panel UI stability

- Prevent repeated form submissions and keep delayed replies/errors scoped to their original editor; reject stale UI snapshots.
- Preserve unsaved Settings while editing categories, selected archived relationships, and completed-task allocation selections.
- Fix lost clicks after changing filters, keyboard focus, same-view scroll restoration and stale cancelled drag state.
- Keep long-form Save/Cancel actions visible, prevent background scrolling behind editors and wrap long project/goal text inside the panel.
- Add delayed-response, menu-traversal, mouse/keyboard and small-window UI regressions. No domain model, data-format, timer, reward or scheduling changes.

## 4.0.2 — clearer routines, board alerts and reversible days off

- Show only relevant recurrence controls, with explicit Monday–Friday wording and whole-day interval validation.
- Configurable daily/interval board reminders, selected weekdays and overnight active hours; native on-top window, bundled sound, ten-minute repeat/snooze and Today shortcut. Missed alerts are skipped and unsaved forms are preserved.
- Remove individual days off directly from Today/Journal or clear ranges in Settings; split overlapping periods and restore eligible routines without duplicate history or rewards.
- Explicitly add active/paused routine occurrences on any chosen date, including days off; retain retrospective work and neutral rest-day statistics.
- Additive v4 backup/defaults, scheduling/model/native failure checks and isolated Windows accountability smoke coverage.

## 4.0.1 — display and UI corrections

- Use native move/resize with stable logical sizing across mixed-DPI monitors; recover inflated/off-screen geometry and resize from all edges/corners.
- Larger native close controls, tray/header recovery and display-selection menus, explicit resize dialog, Ctrl+Q/Ctrl+Shift+R, and graceful Alt+F4.
- Fix compact HUD overflow and folding/expanded-size restoration.
- Fix stuck review forms, stale content after editor cancellation, live daily totals and duplicated allocations after date edits.
- Add geometry, mixed-display and expanded UI regression tests.

## 4.0 — personal planner and accountability

- Flexible planning periods, goals, projects, milestones, standalone tasks, checklists, effort estimates, weekly allocations and availability warnings.
- Independent bounded sessions, concurrent timers, pause/resume/extend, shutdown recovery, manual time entries and corrections.
- Today, Planner, Journal, Quests, Routines, Stats and Settings panel; compact HUD retained.
- Repeating daily reviews with saved drafts, startup catch-up, editable times and advance days off.
- Dated recurring occurrences, selected weekdays/every-N-days schedules, pause and archive with preserved history.
- Native command-based state ownership, atomic saves, migration/import backups, single-instance protection, idempotent merges and legacy-duration review.
- Automated model/native tests, Windows UI smoke harness and Windows CI.
