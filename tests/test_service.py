"""Native JS execution, migration, rollback, reminders and bridge isolation tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication, QDateTime
from state_service import StateService, configure_startup

APP = QCoreApplication.instance() or QCoreApplication([])
ROOT = Path(__file__).resolve().parents[1]
TEMP = ROOT / "data" / "test-runs"
TEMP.mkdir(parents=True, exist_ok=True)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEMP)
        self.path = Path(self.temp.name) / "quests.json"
        self.now = QDateTime.fromString("2026-10-18T23:00:00", "yyyy-MM-ddTHH:mm:ss").toMSecsSinceEpoch()
        self.service = StateService(self.path, clock=lambda: self.now)

    def tearDown(self):
        self.service.deleteLater()
        APP.sendPostedEvents()
        self.temp.cleanup()

    def command(self, kind, payload=None):
        return self.service.dispatch({"type": kind, "payload": payload or {}})

    def test_native_commands_and_simultaneous_clients_do_not_overwrite(self):
        initial = self.service.snapshot()
        a = self.command("task.add", {"title": "پروژه فارسی"})
        b = self.command("task.edit", {"id": initial["quests"][0]["id"], "fields": {"estimateMinutes": 180}})
        self.assertTrue(a["ok"])
        self.assertTrue(b["ok"])
        self.assertEqual(self.service.snapshot()["quests"][-1]["title"], "پروژه فارسی")
        self.assertEqual(self.service.snapshot()["quests"][0]["estimateMinutes"], 180)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), self.service.snapshot())

    def test_write_failure_rolls_back_memory_and_disk(self):
        before = self.path.read_bytes()
        with patch.object(self.service, "_write", side_effect=OSError("disk full")):
            result = self.command("task.add", {"title": "Must not survive"})
        self.assertFalse(result["ok"])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertNotIn("Must not survive", str(self.service.snapshot()))

    def test_invalid_save_is_never_replaced(self):
        invalid = Path(self.temp.name) / "broken.json"
        invalid.write_text("{broken", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            StateService(invalid)
        self.assertEqual(invalid.read_text(), "{broken")

    def test_migration_backup_is_byte_exact(self):
        old = {"version": 2, "quests": [], "recurring": [], "completed": [{"title": "Old", "at": self.now, "ms": 744 * 3600000}]}
        legacy = Path(self.temp.name) / "legacy.json"
        legacy.write_text(json.dumps(old), encoding="utf-8")
        original = legacy.read_bytes()
        migrated = StateService(legacy, clock=lambda: self.now)
        backups = list((legacy.parent / "backups").glob("*pre-v4*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertEqual(migrated.snapshot()["completed"][0]["timeReview"], "pending")
        migrated.deleteLater()

    def test_snooze_repeat_and_skip_persist(self):
        self.assertEqual(self.service.reminder_days(), ["2026-10-18"])
        self.assertEqual(self.service.reminder_days(), [])
        self.command("review.snooze", {"day": "2026-10-18", "minutes": 60})
        self.now += 30 * 60000
        self.assertEqual(self.service.reminder_days(), [])
        self.now += 30 * 60000
        self.assertEqual(self.service.reminder_days(), ["2026-10-18"])
        self.command("review.skip", {"day": "2026-10-18"})
        self.now += 3600000
        self.assertEqual(self.service.reminder_days(), [])

    def test_days_off_defer_catchup(self):
        self.command("dayOff.save", {"start": "2026-10-18", "end": "2026-10-20", "label": "Travel"})
        self.assertEqual(self.service.reminder_days(), [])
        self.now += 3 * 86400000
        self.assertEqual(self.service.reminder_days(), ["2026-10-21"])

    def test_native_tick_expires_session_without_javascript_page(self):
        task = self.service.snapshot()["quests"][0]["id"]
        self.command("session.start", {"taskId": task, "minutes": 180})
        self.now += 700 * 3600000
        result = self.service.tick()
        self.assertTrue(result["ok"])
        session = self.service.snapshot()["sessions"][0]
        self.assertEqual(session["status"], "expired")
        self.assertEqual(sum(x["end"] - x["start"] for x in session["segments"]), 3 * 3600000)

    def test_import_backups_and_repeated_merge(self):
        incoming = self.service.snapshot()
        self.assertTrue(self.command("import.merge", {"data": incoming})["ok"])
        self.assertTrue(self.command("import.merge", {"data": incoming})["ok"])
        self.assertEqual(len(self.service.snapshot()["quests"]), len(incoming["quests"]))
        self.assertTrue(list((self.path.parent / "backups").glob("*pre-import*.json")))

    def test_idempotent_request_after_restart(self):
        cmd = {"type": "task.add", "requestId": "test-repeat", "payload": {"title": "Only once"}}
        self.assertTrue(self.service.dispatch(cmd)["ok"])
        restarted = StateService(self.path, clock=lambda: self.now)
        self.assertTrue(restarted.dispatch(cmd)["ok"])
        self.assertEqual(sum(q["title"] == "Only once" for q in restarted.snapshot()["quests"]), 1)
        restarted.deleteLater()

    def test_board_reminder_backup_settings_restart_and_day_off(self):
        old = self.service.snapshot()
        del old["settings"]["boardReminder"]
        path = Path(self.temp.name) / "old-v4.json"
        path.write_text(json.dumps(old), encoding="utf-8")
        original = path.read_bytes()
        upgraded = StateService(path, clock=lambda: self.now)
        backups = list((path.parent / "backups").glob("*pre-board-reminders*.json"))
        self.assertEqual(backups[-1].read_bytes(), original)
        self.assertFalse(upgraded.snapshot()["settings"]["boardReminder"]["enabled"])
        upgraded.deleteLater()
        self.now = QDateTime.fromString("2026-10-18T12:59:59", "yyyy-MM-ddTHH:mm:ss").toMSecsSinceEpoch()
        self.command("dayOff.save", {"start":"2026-10-18", "end":"2026-10-18"})
        self.assertTrue(self.command("settings.save", {"fields":{"boardReminder":{"enabled":True,"mode":"daily","time":"13:00"}}})["ok"])
        self.assertIsNone(self.service.board_reminder_action())
        self.now += 1000
        self.assertEqual(self.service.board_reminder_action(), "show")
        self.assertEqual(self.service.reminder_days(), [])
        restarted = StateService(self.path, clock=lambda:self.now)
        self.assertEqual(restarted.snapshot()["settings"]["boardReminder"], self.service.snapshot()["settings"]["boardReminder"])
        self.assertIsNone(restarted.board_reminder_action())
        restarted.deleteLater()

    def test_new_commands_remain_atomic_on_failed_write(self):
        self.command("routine.save", {"fields":{"title":"روزانه", "repeat":"daily"}})
        rid = self.service.snapshot()["recurring"][-1]["id"]
        self.command("dayOff.save", {"start":"2026-10-18", "end":"2026-10-21"})
        before = self.path.read_bytes()
        for kind, payload in [("dayOff.clear",{"start":"2026-10-19","end":"2026-10-19"}),
                              ("routine.addOccurrence",{"routineId":rid,"day":"2026-10-18"})]:
            with patch.object(self.service,"_write",side_effect=OSError("disk full")):
                self.assertFalse(self.command(kind,payload)["ok"])
            self.assertEqual(self.path.read_bytes(), before)
            self.assertEqual(json.loads(before), self.service.snapshot())

    @unittest.skipUnless(sys.platform == 'win32', 'Windows shortcut integration')
    def test_startup_toggle_in_isolated_folder(self):
        folder = Path(self.temp.name)
        configure_startup(True, startup_dir=folder)
        self.assertTrue((folder / 'Quest HUD.lnk').exists())
        configure_startup(False, startup_dir=folder)
        self.assertFalse((folder / 'Quest HUD.lnk').exists())


if __name__ == "__main__":
    unittest.main()
