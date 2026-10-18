"""
Quest HUD - always-on-top translucent RPG task overlay for Windows, plus a
full control-panel window. Both share one JSON data file via a Qt bridge, so
they stay in sync. Run via run.bat (installs Python deps automatically).
"""
import os
import sys
import json
import hashlib
from pathlib import Path

# Must be set BEFORE QtWebEngine is imported so the overlay can be transparent.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--enable-transparent-visuals")

try:
    from PySide6.QtCore import Qt, QUrl, QSettings, QObject, Signal, Slot, QTimer
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtGui import (QGuiApplication, QIcon, QPixmap, QPainter,
                               QColor, QAction, QPainterPath)
    from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                                   QPushButton, QLabel, QSystemTrayIcon, QMenu, QFileDialog,
                                   QSizeGrip, QMessageBox)
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
    from PySide6.QtWebChannel import QWebChannel
except ImportError:
    sys.stderr.write(
        "\n[!] PySide6 is not installed.\n"
        "    Just double-click run.bat - it installs everything the first time.\n\n")
    raise

BASE = os.path.dirname(os.path.abspath(__file__))
HUD_HTML = os.path.join(BASE, "hud.html")
PANEL_HTML = os.path.join(BASE, "panel.html")
DATA = os.environ.get("QUESTHUD_DATA_DIR", os.path.join(BASE, "data"))
DATA_FILE = os.path.join(DATA, "quests.json")
from state_service import StateService

WIN_W, WIN_H = 300, 560
BAR_H = 22
RADIUS = 12
PANEL_RGBA = (18, 18, 22, 153)
ACCENT = "#6e8efb"


class Bridge(QObject):
    """Command bridge. Pages never replace the application's whole state."""
    dataChanged = Signal()
    opacityRequested = Signal(float)
    zoomRequested = Signal(float)
    openPanelRequested = Signal()
    navigate = Signal(str)
    error = Signal(str)

    def __init__(self, service):
        super().__init__()
        self.service = service
        self.route = "today"
        service.changed.connect(self.dataChanged)
        service.failed.connect(self.error)

    @Slot(result=str)
    def load(self):
        return json.dumps(self.service.snapshot(), ensure_ascii=False)

    @Slot(str, result=str)
    def dispatch(self, command):
        try:
            return json.dumps(self.service.dispatch(json.loads(command)), ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot()
    def exportData(self):
        fn, _ = QFileDialog.getSaveFileName(None, "Export Quest HUD backup",
                                            "quest-backup.json", "JSON files (*.json)")
        if fn:
            try:
                with open(fn, "w", encoding="utf-8") as f:
                    json.dump(self.service.snapshot(), f, ensure_ascii=False, indent=2)
            except Exception as exc:
                self.error.emit("Export failed: " + str(exc))

    @Slot(result=str)
    def importData(self):
        fn, _ = QFileDialog.getOpenFileName(None, "Import Quest HUD backup",
                                            "", "JSON files (*.json)")
        if fn:
            try:
                with open(fn, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as exc:
                self.error.emit("Import failed: " + str(exc))
                return ""
        return ""

    @Slot(float)
    def setWindowOpacity(self, v):
        self.opacityRequested.emit(v)

    @Slot(float)
    def setZoom(self, v):
        self.zoomRequested.emit(v)

    @Slot()
    def openPanel(self):
        self.openPanelRequested.emit()

    @Slot(str)
    def openView(self, view):
        self.route = view
        self.openPanelRequested.emit()
        self.navigate.emit(view)

    @Slot(result=str)
    def getRoute(self):
        return self.route


def attach_channel(page, bridge):
    ch = QWebChannel(page)
    ch.registerObject("bridge", bridge)
    page.setWebChannel(ch)
    return ch


class DragBar(QWidget):
    """Slim top strip: drag the frameless window, plus hide/quit buttons."""
    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self._drag = None
        self.setFixedHeight(BAR_H)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0)
        lay.setSpacing(4)
        grip = QLabel("• • •")
        grip.setStyleSheet("color: rgba(255,255,255,0.35); font-size: 11px;")
        lay.addWidget(grip)
        lay.addStretch(1)
        self.hideBtn = QPushButton("–")
        self.quitBtn = QPushButton("✕")
        for b in (self.hideBtn, self.quitBtn):
            b.setFixedSize(20, 16)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton{border:none;background:transparent;color:rgba(255,255,255,0.5);font-size:13px;}"
                "QPushButton:hover{color:#ffffff;}")
            lay.addWidget(b)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(*PANEL_RGBA))
        r = self.rect()
        path = QPainterPath()
        path.moveTo(r.left(), r.bottom() + 1)
        path.lineTo(r.left(), r.top() + RADIUS)
        path.quadTo(r.left(), r.top(), r.left() + RADIUS, r.top())
        path.lineTo(r.right() - RADIUS, r.top())
        path.quadTo(r.right(), r.top(), r.right(), r.top() + RADIUS)
        path.lineTo(r.right(), r.bottom() + 1)
        path.closeSubpath()
        p.drawPath(path)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag is not None and (e.buttons() & Qt.LeftButton):
            self._win.move(e.globalPosition().toPoint() - self._drag)
            e.accept()

    def mouseReleaseEvent(self, _):
        self._drag = None


class HUD(QWidget):
    def __init__(self, profile, bridge, open_panel):
        super().__init__()
        self._open_panel = open_panel
        self.setWindowTitle("Quest HUD")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(WIN_W, WIN_H)
        self.setMinimumSize(190, 240)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.bar = DragBar(self)
        lay.addWidget(self.bar)

        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(profile, self.view)
        self.page.setBackgroundColor(Qt.transparent)
        self.view.setPage(self.page)
        self.view.setAttribute(Qt.WA_TranslucentBackground, True)
        self.view.setStyleSheet("background: transparent;")
        self.view.setContextMenuPolicy(Qt.NoContextMenu)
        self._channel = attach_channel(self.page, bridge)
        self.page.load(QUrl.fromLocalFile(HUD_HTML))
        lay.addWidget(self.view, 1)

        # bottom-right corner grip so the frameless overlay can be resized by dragging
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        self.grip.setToolTip("Drag to resize")
        self.grip.move(self.width() - 16, self.height() - 16)
        self.grip.raise_()

        self.bar.hideBtn.clicked.connect(self.hide)
        self.bar.quitBtn.clicked.connect(lambda: self.request_quit())

        self._restore_geometry()
        self._build_tray()

    def set_zoom(self, factor):
        try:
            self.view.setZoomFactor(max(0.5, min(2.0, float(factor))))
        except Exception:
            pass

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "grip"):
            self.grip.move(self.width() - self.grip.width(), self.height() - self.grip.height())
            self.grip.raise_()

    # ---- tray ----
    def _tray_pixmap(self):
        pm = QPixmap(32, 32)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ACCENT))
        p.drawEllipse(5, 5, 22, 22)
        p.setBrush(QColor(255, 255, 255, 235))
        p.drawEllipse(12, 12, 8, 8)
        p.end()
        return pm

    def _build_tray(self):
        self.tray = QSystemTrayIcon(QIcon(self._tray_pixmap()), self)
        self.tray.setToolTip("Quest HUD")
        menu = QMenu()
        act_show = QAction("Show / hide overlay", self)
        act_show.triggered.connect(self._toggle_visible)
        act_panel = QAction("Open control panel", self)
        act_panel.triggered.connect(lambda: self._open_panel())
        self.act_click = QAction("Click-through (let mouse pass)", self, checkable=True)
        self.act_click.triggered.connect(self._toggle_clickthrough)
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(lambda: self.request_quit())
        menu.addAction(act_show)
        menu.addAction(act_panel)
        menu.addAction(self.act_click)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._toggle_visible()

    def _toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def _toggle_clickthrough(self, on):
        flags = self.windowFlags()
        if on:
            flags |= Qt.WindowTransparentForInput
        else:
            flags &= ~Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.show()

    # ---- geometry ----
    def _restore_geometry(self):
        geo = QSettings("QuestHUD", "overlay").value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            scr = QGuiApplication.primaryScreen().availableGeometry()
            self.move(scr.right() - WIN_W - 18, scr.top() + 18)

    def save_geometry(self):
        QSettings("QuestHUD", "overlay").setValue("geometry", self.saveGeometry())

    def closeEvent(self, e):
        self.save_geometry()
        super().closeEvent(e)


class Panel(QWidget):
    """Normal resizable control-panel window."""
    def __init__(self, profile, bridge):
        super().__init__()
        self.setWindowTitle("Quest HUD — Control Panel")
        self.setWindowIcon(QIcon(self._icon()))
        self.resize(940, 640)
        self.setMinimumSize(640, 460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(profile, self.view)
        self.view.setPage(self.page)
        self._channel = attach_channel(self.page, bridge)
        self.page.load(QUrl.fromLocalFile(PANEL_HTML))
        lay.addWidget(self.view)

        geo = QSettings("QuestHUD", "panel").value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)

    def _icon(self):
        pm = QPixmap(32, 32)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ACCENT))
        p.drawEllipse(4, 4, 24, 24)
        p.end()
        return pm

    def closeEvent(self, e):
        QSettings("QuestHUD", "panel").setValue("geometry", self.saveGeometry())
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    os.makedirs(DATA, exist_ok=True)

    # One writer per data directory, including test installations.
    identity = "questhud-" + hashlib.sha256(os.path.abspath(DATA).lower().encode()).hexdigest()[:20]
    socket = QLocalSocket()
    socket.connectToServer(identity)
    if socket.waitForConnected(400):
        socket.write(b"show")
        socket.waitForBytesWritten(400)
        return
    server = QLocalServer()
    QLocalServer.removeServer(identity)
    if not server.listen(identity):
        QMessageBox.critical(None, "QuestHUD", "Could not acquire the application's single-instance lock.")
        return
    try:
        service = StateService(Path(DATA_FILE), host_integration=False)
    except Exception as exc:
        QMessageBox.critical(None, "QuestHUD data error", str(exc) + "\nYour save has not been replaced.")
        return
    profile = QWebEngineProfile("questhud")
    profile.setPersistentStoragePath(os.path.join(DATA, "web-profile"))
    profile.setCachePath(os.path.join(DATA, "web-cache"))
    bridge = Bridge(service)

    holder = {"panel": None}

    def open_panel():
        if holder["panel"] is None:
            holder["panel"] = Panel(profile, bridge)
        p = holder["panel"]
        p.show()
        p.raise_()
        p.activateWindow()

    hud = HUD(profile, bridge, open_panel)
    def request_quit():
        pending = [s for s in service.snapshot()["sessions"] if s["status"] == "running" or s.get("needsAttention")]
        if pending:
            box = QMessageBox(hud)
            box.setWindowTitle("Finish for now?")
            box.setText("There are running or unresolved sessions. Pause them or finish the sessions before quitting.")
            pause = box.addButton("Pause sessions", QMessageBox.AcceptRole)
            finish = box.addButton("Finish sessions", QMessageBox.AcceptRole)
            box.addButton(QMessageBox.Cancel)
            box.exec()
            button = box.clickedButton()
            if button not in (pause, finish):
                return
            result = service.dispatch({"type": "sessions.pauseAll" if button == pause else "sessions.finishAll"})
            if not result["ok"]:
                return
        app.quit()
    hud.request_quit = request_quit
    bridge.openPanelRequested.connect(open_panel)
    bridge.opacityRequested.connect(hud.setWindowOpacity)
    bridge.zoomRequested.connect(hud.set_zoom)
    hud.show()
    service.failed.connect(lambda message: QMessageBox.warning(holder["panel"] or hud, "QuestHUD", message))
    if not os.environ.get("QUESTHUD_DATA_DIR"):
        service.host_integration = True
        QTimer.singleShot(1500, service.sync_startup)

    def incoming():
        connection = server.nextPendingConnection()
        if connection:
            connection.waitForReadyRead(200)
            connection.readAll()
            open_panel()
            connection.disconnectFromServer()
            connection.deleteLater()
    server.newConnection.connect(incoming)
    announced = set()
    def maintain():
        result = service.tick()
        if not result["ok"]:
            return
        state = service.snapshot()
        attention = [x for x in state["sessions"] if x.get("needsAttention")]
        unseen = [x for x in attention if x["id"] not in announced]
        # Planned days off are quiet; unresolved sessions remain visible in Today.
        day_off = service._eval("!!QC.isOff(current, QC.trackingDay(current," + str(service.clock()) + "))").toBool()
        if unseen and not day_off:
            announced.update(x["id"] for x in unseen)
            hud.tray.showMessage("Session needs your attention", "Finish or extend your session in QuestHUD.")
            bridge.openView("today")
        announced.intersection_update(x["id"] for x in attention)
        days = service.reminder_days()
        if days:
            hud.tray.showMessage("Daily check-in", str(len(days)) + " day(s) waiting for review.")
            bridge.openView("review:" + days[-1])
    timer = QTimer(app)
    timer.setInterval(1000)
    timer.timeout.connect(maintain)
    timer.start()
    QTimer.singleShot(2000, maintain)
    app.aboutToQuit.connect(hud.save_geometry)

    # keep references alive
    app._questhud = (profile, bridge, hud, holder, service, timer, server)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
