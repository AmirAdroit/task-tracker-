# Changelog

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
