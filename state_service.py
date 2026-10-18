"""Single owner of QuestHUD state. UI commands and native ticks use the same JS reducer."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtQml import QJSEngine
from board_reminder import BoardReminder

BASE = Path(__file__).resolve().parent


def configure_startup(enabled: bool, base: Path = BASE, startup_dir: Path | None = None):
    """Only manage this application's named startup shortcut; no registry changes."""
    if os.name != "nt":
        return
    folder = startup_dir or Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
    shortcut = folder / "Quest HUD.lnk"
    if not enabled:
        if shortcut.exists():
            # Check the shortcut's target before removing anything.
            script = "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:QH_LINK); if($s.TargetPath -eq $env:QH_TARGET){Remove-Item -LiteralPath $env:QH_LINK} else {throw 'Startup shortcut belongs to another installation'}"
        else:
            return
    else:
        script = "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut($env:QH_LINK); $s.TargetPath=$env:QH_TARGET; $s.WorkingDirectory=$env:QH_BASE; $s.Save()"
    env = dict(os.environ, QH_LINK=str(shortcut), QH_TARGET=str(base / "start-hud.vbs"), QH_BASE=str(base))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env,
                   check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)


class StateService(QObject):
    changed = Signal()
    failed = Signal(str)

    def __init__(self, data_file: Path, *, clock=None, host_integration=False):
        super().__init__()
        self.path = Path(data_file)
        self.clock = clock or (lambda: int(time.time() * 1000))
        self.board_reminder = BoardReminder()
        self.host_integration = host_integration
        self.engine = QJSEngine(self)
        self._eval("var window = this;")
        for name in ("quest-core.js", "planner-core.js"):
            self._eval((BASE / name).read_text(encoding="utf-8"), name)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = None
        if self.path.exists():
            # Invalid data must never silently become a fresh save.
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not isinstance(raw.get("quests"), list):
                raise ValueError("Invalid QuestHUD save. Restore a backup before continuing.")
        if raw is not None and raw.get("version", 0) > 4:
            raise ValueError("This save belongs to a newer QuestHUD version.")
        if raw is not None and raw.get("version", 0) < 4:
            self.backup("pre-v4")
        elif raw is not None and "boardReminder" not in raw.get("settings", {}):
            self.backup("pre-board-reminders")
        self._eval("var current = QC.normalize(" + json.dumps(raw, ensure_ascii=True) + "," + str(self.clock()) + ");")
        self._eval("current = QC.apply(current, {type:'sessions.recover'}, " + str(self.clock()) + ");")
        self._eval("current = QC.apply(current, {type:'tick'}, " + str(self.clock()) + ");")
        self._write(self.snapshot())
        self._startup_applied = None
        self.sync_startup()

    def _eval(self, source, name="command"):
        value = self.engine.evaluate(source, name)
        if value.isError():
            raise ValueError(value.toString() + " (" + name + ":" + value.property("lineNumber").toString() + ")")
        return value

    def snapshot(self):
        return json.loads(self._eval("JSON.stringify(current)").toString())

    def _write(self, state):
        fd, filename = tempfile.mkstemp(prefix="quests-", suffix=".json.tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(filename, self.path)
        finally:
            if os.path.exists(filename):
                os.unlink(filename)

    def backup(self, reason):
        if not self.path.exists():
            return None
        folder = self.path.parent / "backups"
        folder.mkdir(exist_ok=True)
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()[:12]
        target = folder / (time.strftime("%Y%m%d-%H%M%S") + "-" + reason + "-" + digest + ".json")
        shutil.copy2(self.path, target)
        return target

    def dispatch(self, command):
        before = self.snapshot()
        try:
            if not isinstance(command, dict) or not isinstance(command.get("type"), str):
                raise ValueError("Invalid command")
            if command["type"].startswith("import."):
                incoming = command.get("payload", {}).get("data")
                if not isinstance(incoming, dict) or not isinstance(incoming.get("quests"), list) or not isinstance(incoming.get("completed"), list):
                    raise ValueError("This is not a QuestHUD backup")
                if incoming.get("version", 0) > 4:
                    raise ValueError("Cannot import a newer backup format")
                self.backup("pre-import")
            source = "var candidate = QC.apply(current," + json.dumps(command, ensure_ascii=True) + "," + str(self.clock()) + "); JSON.stringify(candidate);"
            candidate = json.loads(self._eval(source).toString())
            if candidate != before:
                if self.host_integration and candidate["settings"]["startup"] != before["settings"]["startup"]:
                    configure_startup(candidate["settings"]["startup"])
                    self._startup_applied = candidate["settings"]["startup"]
                self._write(candidate)
                self._eval("current = candidate;")
                self.changed.emit()
            return {"ok": True, "state": candidate}
        except Exception as exc:
            self.failed.emit(str(exc))
            return {"ok": False, "error": str(exc), "state": before}

    def sync_startup(self):
        if not self.host_integration:
            return
        desired = self.snapshot()["settings"]["startup"]
        if self._startup_applied != desired:
            try:
                configure_startup(desired)
                self._startup_applied = desired
            except Exception as exc:
                self.failed.emit("Could not update Start with Windows: " + str(exc))

    def tick(self):
        """Avoid unnecessary disk writes; the reducer runs only for an actual transition."""
        now = self.clock()
        changed = self._eval("JSON.stringify((function(){var n=QC.copy(current); QC.rollover(n," + str(now) + "); return n;})())").toString()
        state = self.snapshot()
        expiration = any(x.get("status") == "running" and
                         sum(r["end"] - r["start"] for r in x["segments"]) + max(0, now - x["runStart"]) >= x["limitMs"]
                         for x in state["sessions"])
        if json.loads(changed) != state or expiration:
            return self.dispatch({"type": "tick"})
        return {"ok": True, "state": state}

    def reminder_days(self):
        now = self.clock()
        days = json.loads(self._eval("JSON.stringify(QC.pendingReviews(current," + str(now) + "))").toString())
        state = self.snapshot()
        due = [day for day in days if state["reviews"].get(day, {}).get("nextPrompt", 0) <= now]
        if due:
            # One catch-up prompt for the batch, then respect snoozes on every pending day.
            for day in days:
                if day in due:
                    self.dispatch({"type": "review.prompt", "payload": {"day": day}})
            return days
        return []

    def board_reminder_action(self):
        return self.board_reminder.poll(self.snapshot()["settings"]["boardReminder"], self.clock())
