"""Native, transient board alerts. Configuration is saved; missed alerts never catch up."""
from __future__ import annotations

from datetime import datetime, timedelta
import json

TEN_MINUTES = 10 * 60 * 1000


class BoardReminder:
    def __init__(self):
        self.config_key = None
        self.previous = None
        self.last_slot = 0
        self.pending = False
        self.visible = False
        self.next_sound = 0
        self.until = 0
        self.testing = False

    def reset(self, now):
        visible = self.visible
        self.pending = self.visible = self.testing = False
        self.previous = now
        return "hide" if visible else None

    @staticmethod
    def allowed(config, now):
        local = datetime.fromtimestamp(now / 1000)
        if not config["enabled"] or (local.weekday() + 1) % 7 not in config["days"]:
            return False
        start, end = config.get("windowStart"), config.get("windowEnd")
        if config["mode"] != "interval" or not start or not end:
            return True
        time = local.strftime("%H:%M")
        return start <= time < end if start < end else time >= start or time < end

    @staticmethod
    def period_end(config, now):
        local = datetime.fromtimestamp(now / 1000)
        midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if config["mode"] == "interval" and config.get("windowEnd"):
            hour, minute = map(int, config["windowEnd"].split(":"))
            end = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if end <= local:
                end += timedelta(days=1)
            # Day selections are local calendar days, even for overnight windows.
            midnight = min(midnight, end)
        return int(midnight.timestamp() * 1000)

    def show(self, now, until, *, testing=False):
        self.pending = self.visible = True
        self.testing = testing
        self.until = until
        self.next_sound = now + TEN_MINUTES
        return "show"

    def test(self, now):
        # Preview does not acknowledge, replace or delay a real pending alert.
        if self.pending:
            self.visible = True
            return "show"
        return self.show(now, now + TEN_MINUTES, testing=True)

    def snooze(self, now):
        if self.pending:
            self.visible = False
            self.next_sound = now + TEN_MINUTES
            if self.testing:
                self.until = self.next_sound + TEN_MINUTES
        return "hide"

    def dismiss(self):
        self.pending = self.visible = self.testing = False
        return "hide"

    def poll(self, config, now):
        key = json.dumps(config, sort_keys=True)
        if key != self.config_key:
            self.config_key = key
            self.last_slot = 0
            return self.reset(now)
        previous = self.previous
        self.previous = now
        # Sleep, shutdown, long event-loop gaps and clock changes cannot replay alerts.
        if previous is None or now < previous or now - previous > 90000:
            return self.reset(now)
        if self.pending:
            if now >= self.until or (not self.testing and not self.allowed(config, now)):
                return self.dismiss()
            if now >= self.next_sound:
                self.next_sound = now + TEN_MINUTES
                action = "sound" if self.visible else "show"
                self.visible = True
                return action
            return None
        if not self.allowed(config, now):
            return None
        if config["mode"] == "daily":
            hour, minute = map(int, config["time"].split(":"))
            slot = int(datetime.fromtimestamp(now / 1000).replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp() * 1000)
        else:
            interval = config["intervalMinutes"] * 60000
            anchor = config["anchor"]
            slot = anchor + ((now - anchor) // interval) * interval
            if slot <= anchor:
                return None
        if previous < slot <= now and slot > self.last_slot and self.allowed(config, slot):
            self.last_slot = slot
            return self.show(now, self.period_end(config, now))
        return None
