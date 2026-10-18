"""Non-modal native attention window. No browser audio or notification permission needed."""
import ctypes
import os
from pathlib import Path

from PySide6.QtCore import Qt, QObject, QAbstractNativeEventFilter, QRect, QSize
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from window_geometry import fit_rect


def play_alert_sound():
    if os.name == "nt":
        import winsound
        winsound.PlaySound(str(Path(__file__).parent / "assets" / "board-alert.wav"),
                          winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    else:
        QApplication.beep()


class AlertWindow(QDialog):
    def __init__(self, controller):
        super().__init__(None, Qt.Window | Qt.WindowStaysOnTopHint)
        self.controller = controller
        self.setWindowTitle("QuestHUD — Check your board")
        self.setModal(False)
        self.resize(420, 210)
        self.setStyleSheet("QDialog{background:#191b24;color:#e9ebf5} QLabel{color:#e9ebf5} "
                           "QPushButton{background:#2b3146;color:#e9ebf5;border:1px solid #46516e;"
                           "border-radius:7px;padding:9px} QPushButton:focus{border:2px solid #8ca4ff}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        heading = QLabel("Time to check your board")
        heading.setStyleSheet("font-size:18px;font-weight:600")
        layout.addWidget(heading)
        self.message = QLabel("Take a look at Today and decide what comes next.")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        buttons = QHBoxLayout()
        self.open_button = QPushButton("Open board")
        self.open_button.clicked.connect(controller.open_board)
        self.snooze_button = QPushButton("Snooze 10 minutes")
        self.snooze_button.clicked.connect(controller.snooze)
        self.dismiss_button = QPushButton("Dismiss")
        self.dismiss_button.clicked.connect(controller.dismiss)
        for button in (self.open_button, self.snooze_button, self.dismiss_button):
            button.setAutoDefault(False)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        hint = QLabel("Sounds again every 10 minutes. Closing or Escape snoozes for 10 minutes.")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:11px;color:#a2a9bf")
        layout.addWidget(hint)

    def reject(self):
        self.controller.snooze()

    def closeEvent(self, event):
        event.ignore()
        self.controller.snooze()

    def show_on_current_screen(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        self.adjustSize()
        if screen:
            rect = QRect(0, 0, self.width(), self.height())
            rect.moveCenter(screen.availableGeometry().center())
            self.setGeometry(fit_rect(rect, screen.availableGeometry(), QSize(280, 180)))
        self.show()
        self.raise_()
        self.activateWindow()


class ResumeFilter(QAbstractNativeEventFilter):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

    def nativeEventFilter(self, event_type, message):
        if os.name == "nt" and event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            # WM_POWERBROADCAST, suspend or automatic/user resume.
            if msg.message == 0x0218 and msg.wParam in (0x0004, 0x0007, 0x0012):
                self.controller.resume()
        return False, 0


class BoardAlertController(QObject):
    def __init__(self, service, bridge, *, sound=play_alert_sound):
        super().__init__(bridge)
        self.service = service
        self.bridge = bridge
        self.sound = sound
        self.window = AlertWindow(self)
        self.filter = ResumeFilter(self)
        QApplication.instance().installNativeEventFilter(self.filter)
        bridge.boardReminderTestRequested.connect(self.test)
        # Persist the schedule before any corresponding native UI transition.
        service.changed.connect(self.poll)
        self.poll()

    def apply(self, action):
        if action == "hide":
            self.window.hide()
        elif action in ("show", "sound"):
            if action == "show":
                self.window.message.setText("Preview: this is your board reminder." if self.service.board_reminder.testing else "Take a look at Today and decide what comes next.")
                self.window.show_on_current_screen()
            try:
                self.sound()
            except Exception as exc:
                self.window.message.setText("Sound could not play. Check your audio device. " + str(exc))

    def poll(self):
        self.apply(self.service.board_reminder_action())

    def test(self):
        self.apply(self.service.board_reminder.test(self.service.clock()))

    def snooze(self):
        self.apply(self.service.board_reminder.snooze(self.service.clock()))

    def dismiss(self):
        self.apply(self.service.board_reminder.dismiss())

    def open_board(self):
        self.dismiss()
        self.bridge.openView("today")

    def resume(self):
        self.apply(self.service.board_reminder.reset(self.service.clock()))
