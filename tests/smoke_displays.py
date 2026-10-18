"""Real mixed-DPI display transfers plus simulated delayed-DPI geometry regression."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--enable-transparent-visuals')
from PySide6.QtCore import QEventLoop, QTimer, QSettings, QEvent, QPoint, QSize
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from hud import HUD, Bridge
from state_service import StateService

app = QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)
folder = ROOT / 'data' / 'display-smoke'
folder.mkdir(parents=True, exist_ok=True)
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(folder / 'settings'))
service = StateService(folder / ('quests-' + str(int(time.time()*1000)) + '.json'), host_integration=False)
bridge = Bridge(service)
profile = QWebEngineProfile(app)
profile.setPersistentStoragePath(str(folder / 'profile'))
window = HUD(profile, bridge, lambda: None)
window.request_quit = lambda: None
bridge.collapsedRequested.connect(window.set_collapsed)
window.show()


def settle(ms=300):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def assert_controls():
    assert window.rect().contains(window.bar.quitBtn.mapTo(window, QPoint()) + window.bar.quitBtn.rect().bottomRight()), 'Close control clipped'
    assert window.bar.quitBtn.isVisible(), 'Close control hidden'
    assert window.screen().availableGeometry().contains(window.geometry()), 'Window outside work area'


try:
    settle(1200)
    screens = app.screens()
    rows = []
    for i in range(12):
        screen = screens[i % len(screens)]
        window.move(screen.availableGeometry().topLeft() + QPoint(70, 70))
        settle()
        assert window.size() == QSize(300, 560), (window.size(), window._preferred_size)
        assert_controls()
        rows.append({'screen': window.screen().name(), 'dpr': window.devicePixelRatioF(), 'size': [window.width(), window.height()]})
    print('PASS: 12 physical display transfers keep 300x560 logical pixels and visible close controls', flush=True)
    window._moving = True
    window._dpi_transition = True
    window.resize(1013, 1890)
    window.end_interaction()
    settle()
    assert window.size() == QSize(300, 560)
    assert_controls()
    print('PASS: delayed native DPI inflation is corrected without learning the inflated size', flush=True)
    window.resize(360, 620)
    settle()
    assert window._preferred_size == QSize(360, 620)
    for screen in reversed(screens):
        window.move_to_screen(screen)
        settle()
        assert window.size() == QSize(360, 620)
    print('PASS: user-selected resize survives display changes', flush=True)
    assert len(window.resize_handles) == 8
    for handle in window.resize_handles:
        assert handle.isVisible() and not handle.geometry().isEmpty()
    print('PASS: eight visible resize handles cover edges and corners', flush=True)
    window.set_collapsed(True)
    settle()
    assert window.height() == 156
    window.set_collapsed(False)
    settle()
    assert window.size() == QSize(360, 620)
    print('PASS: folding and unfolding restore expanded size', flush=True)
    window.move(10000, -10000)
    window.reset_layout(screens[0])
    settle()
    assert window.size() == QSize(300, 560)
    assert_controls()
    actions = [a.text() for a in window.tray.contextMenu().actions()]
    assert 'Reset size and position' in actions and 'Quit' in actions
    print('PASS: tray recovery restores an off-screen HUD', flush=True)
    called = []
    window.request_quit = lambda: called.append(True)
    window.activateWindow()
    settle()
    QTest.keyClick(window, Qt.Key_Q, Qt.ControlModifier)
    settle()
    assert called
    print('PASS: Ctrl+Q invokes the graceful quit path', flush=True)
    called.clear()
    window.close()
    assert called
    print('PASS: native close/Alt+F4 uses the same graceful quit path', flush=True)
    window.grab().save(str(folder / 'hud.png'))
    (folder / 'transfers.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
finally:
    window.tray.hide()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    profile.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
