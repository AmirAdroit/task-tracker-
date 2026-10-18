"""Injected local clocks; these are timing simulations, not real suspend tests."""
from datetime import datetime
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_reminder import BoardReminder, TEN_MINUTES


def at(value):
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def config(**fields):
    return dict(enabled=True, mode="daily", time="13:00", intervalMinutes=60,
                days=[0, 1, 2, 3, 4, 5, 6], windowStart="", windowEnd="",
                anchor=at("2026-10-18T12:00:00"), **fields)


class BoardReminderTests(unittest.TestCase):
    def setUp(self):
        self.reminder = BoardReminder()
        self.b = config()
        self.now = at("2026-10-18T12:59:59")
        self.assertIsNone(self.reminder.poll(self.b, self.now))

    def trigger(self):
        self.now += 1000
        self.assertEqual(self.reminder.poll(self.b, self.now), "show")

    def advance(self, minutes):
        actions = []
        for _ in range(minutes):
            self.now += 60000
            action = self.reminder.poll(self.b, self.now)
            if action:
                actions.append(action)
        return actions

    def test_one_window_repeat_sound_and_dismiss(self):
        self.trigger()
        self.assertIsNone(self.reminder.poll(self.b, self.now))
        self.assertEqual(self.advance(9), [])
        self.assertEqual(self.advance(1), ["sound"])
        self.assertEqual(self.advance(10), ["sound"])
        self.assertEqual(self.reminder.dismiss(), "hide")
        self.assertEqual(self.advance(20), [])

    def test_snooze_reopens_after_exactly_ten_minutes(self):
        self.trigger()
        self.assertEqual(self.reminder.snooze(self.now), "hide")
        self.assertFalse(self.reminder.visible)
        self.assertEqual(self.advance(9), [])
        self.assertEqual(self.advance(1), ["show"])
        self.assertTrue(self.reminder.visible)

    def test_restart_long_gap_and_resume_skip_missed_alerts(self):
        self.assertIsNone(BoardReminder().poll(self.b, at("2026-10-18T13:01:00")))
        self.assertIsNone(self.reminder.poll(self.b, at("2026-10-18T15:00:00")))
        self.reminder = BoardReminder()
        self.reminder.poll(self.b, self.now)
        self.trigger()
        self.assertEqual(self.reminder.reset(self.now + 10000), "hide")
        self.assertIsNone(self.reminder.poll(self.b, self.now + 11000))

    def test_clock_changes_cannot_replay_a_daily_alert(self):
        self.trigger()
        self.reminder.dismiss()
        self.reminder.poll(self.b, self.now - 2000)
        self.assertIsNone(self.reminder.poll(self.b, self.now))

    def test_interval_anchor_survives_restart_and_snooze_ignores_new_slots(self):
        self.b = {**self.b, "mode": "interval", "intervalMinutes": 15}
        self.reminder.poll(self.b, self.now)
        self.trigger()
        self.advance(9)
        self.reminder.snooze(self.now)
        self.assertEqual(self.advance(9), [])  # 13:15 slot does not interrupt snooze
        self.assertEqual(self.advance(1), ["show"])
        restarted = BoardReminder()
        restarted.poll(self.b, at("2026-10-18T13:29:59"))
        self.assertEqual(restarted.poll(self.b, at("2026-10-18T13:30:00")), "show")

    def test_selected_days_and_overnight_window(self):
        b = {**self.b, "mode": "interval", "windowStart": "22:00", "windowEnd": "02:00"}
        for stamp, expected in [("2026-10-18T21:59:59", False), ("2026-10-18T22:00:00", True),
                                ("2026-10-19T01:59:59", True), ("2026-10-19T02:00:00", False)]:
            self.assertEqual(BoardReminder.allowed(b, at(stamp)), expected)
        b["days"] = [0]
        self.assertFalse(BoardReminder.allowed(b, at("2026-10-19T01:00:00")))

    def test_quiet_hours_and_midnight_end_unanswered_alerts(self):
        self.b = {**self.b, "mode": "interval", "windowStart": "12:00", "windowEnd": "13:05"}
        self.reminder.poll(self.b, self.now)
        self.trigger()
        self.assertEqual(self.advance(5), ["hide"])
        self.b = {**self.b, "mode": "daily", "time": "23:59"}
        self.now = at("2026-10-18T23:58:59")
        self.reminder.poll(self.b, self.now)
        self.trigger()
        self.assertEqual(self.advance(1), ["hide"])

    def test_changed_or_disabled_schedule_hides_pending_alert(self):
        self.trigger()
        self.b = {**self.b, "enabled": False}
        self.assertEqual(self.reminder.poll(self.b, self.now), "hide")
        self.assertFalse(self.reminder.pending)

    def test_test_alert_does_not_replace_or_acknowledge_pending_schedule(self):
        self.trigger()
        until, repeat = self.reminder.until, self.reminder.next_sound
        self.reminder.test(self.now + 1000)
        self.assertEqual((self.reminder.until, self.reminder.next_sound), (until, repeat))
        self.assertFalse(self.reminder.testing)
        self.reminder.dismiss()
        self.assertEqual(self.reminder.test(self.now), "show")
        self.assertTrue(self.reminder.testing)


if __name__ == "__main__":
    unittest.main()
