"""Rendering/caret stress on real Qt windows, with synthetic data and two backends."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--enable-transparent-visuals")

from rendering import configure_rendering
configure_rendering(sys.argv[1:])

from PySide6.QtCore import QEventLoop, QTimer, QSettings, QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
import hud
from state_service import StateService

app = QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)
folder = ROOT / 'data' / ('rendering-smoke-' + hud.RENDERER)
folder.mkdir(parents=True, exist_ok=True)
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(folder / 'settings'))
errors = []


class ConsolePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        if level == QWebEnginePage.ErrorMessageLevel:
            errors.append(f'{source}:{line}: {message}')


hud.QWebEnginePage = ConsolePage
clock = [int(time.time() * 1000)]
data_file = folder / ('quests-' + str(clock[0]) + '.json')
service = StateService(data_file, clock=lambda: clock[0])
bridge = hud.Bridge(service)
profile = QWebEngineProfile('questhud-smoke-' + str(clock[0]), app)
profile.setPersistentStoragePath(str(folder / 'profile'))
profile.setCachePath(str(folder / 'cache'))
panel = hud.Panel(profile, bridge)
panel.resize(1300, 900)
overlay = hud.HUD(profile, bridge, lambda: panel.show())
overlay.request_quit = lambda: None
bridge.collapsedRequested.connect(overlay.set_collapsed)
overlay.move(30, 30)
panel.move(360, 40)
panel.setWindowFlag(hud.Qt.WindowStaysOnTopHint, True)  # Keep the test's compositor exposed.
panel.show()
overlay.show()


def js(page, code):
    result = []
    loop = QEventLoop()
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    timeout.start(10000)
    def finished(value):
        result.append(value)
        loop.quit()
    page.runJavaScript(code, finished)
    loop.exec()
    timeout.stop()
    if not result:
        raise AssertionError('JS callback timed out: ' + code[:100])
    return result[0]


def wait(predicate, label, seconds=15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            print('PASS:', label, flush=True)
            return
        loop = QEventLoop()
        QTimer.singleShot(80, loop.quit)
        loop.exec()
    raise AssertionError('Timed out: ' + label + '\n' + '\n'.join(errors))


def command(kind, payload=None):
    result = service.dispatch({'type': kind, 'payload': payload or {}})
    assert result['ok'], result
    return result['state']


def capture(widget, filename):
    # Wait for compositor painting as well as DOM updates.
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec()
    assert widget.grab().save(str(folder / filename))


from PySide6.QtCore import Qt
from PySide6.QtGui import QInputMethodEvent
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest


def settle(ms=70):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def click(selector):
    assert js(panel.page, '!!document.querySelector(' + json.dumps(selector) + ')'), selector
    js(panel.page, 'document.querySelector(' + json.dumps(selector) + ').click()')


def press(key, modifiers=Qt.NoModifier):
    QTest.keyClick(panel.view.focusProxy(), key, modifiers); settle(20)


def type_text(text):
    QTest.keyClicks(panel.view.focusProxy(), text, Qt.NoModifier, 2); settle(35)


def viewport_ready():
    return (abs(js(panel.page, 'innerWidth') * panel.view.zoomFactor() - panel.view.width()) <= 2
            and abs(js(panel.page, 'innerHeight') * panel.view.zoomFactor() - panel.view.height()) <= 2)


exposure_recoveries = 0


def expose_panel():
    global exposure_recoveries
    if panel.isMinimized():
        exposure_recoveries += 1
        print('FIXTURE: restoring minimized synthetic test window', flush=True)
        panel.showNormal()
    panel.raise_()
    panel.activateWindow()
    wait(lambda: panel.windowHandle().isExposed() and panel.page.isVisible()
         and js(panel.page, 'document.visibilityState') == 'visible', 'synthetic browser is exposed')


def stable_frame():
    # A JS/rAF reply only confirms style restoration, not that Chromium's frame
    # has reached Qt. In hosted offscreen runs the old caret/opacity frame can
    # still be presented after that reply. Wait for actual, unchanged pixels.
    wait(lambda: js(panel.page, '!QUI.repaintPending'), 'repair styles restored')
    start = unchanged = time.monotonic()
    previous = None
    blank_reported = False
    while time.monotonic() - start < 5:
        if panel.isMinimized():
            expose_panel()
            previous = None
            unchanged = time.monotonic()
        settle(80)
        current = panel.view.grab().toImage()
        pixels = (current.size(), bytes(current.constBits()))
        now = time.monotonic()
        if len(set(pixels[1])) <= 32 and not blank_reported:
            print('BLANK:', js(panel.page, 'JSON.stringify({visibility:document.visibilityState,opacity:getComputedStyle(document.documentElement).opacity,dialog:!!document.querySelector("dialog[open]"),body:getComputedStyle(document.body).display})'),
                  app.applicationState(), panel.windowState(), panel.page.isVisible(), flush=True)
            blank_reported = True
        if pixels != previous:
            previous, unchanged = pixels, now
        elif now - start >= 0.5 and now - unchanged >= 0.35 and len(set(pixels[1])) > 32:
            return current
    current.save(str(folder / 'unstable-frame.png'))
    raise AssertionError('Chromium/Qt frame was blank or did not settle within five seconds')


def repaint_comparison(index):
    # Suppress only the blinking caret while comparing two otherwise identical
    # frames. Keep text, focus borders, editor contents and the page visible.
    expose_panel()
    print('WINDOW:', app.platformName(), panel.isVisible(), panel.windowHandle().isExposed(), panel.isActiveWindow(), panel.size(), flush=True)
    native = panel.screen().grabWindow(panel.winId(), 0, 0, panel.width(), panel.height())
    if not native.isNull():
        native.save(str(folder / 'native-before-capture.png'))
    js(panel.page, 'window.caretRule=document.createElement("style");caretRule.textContent="input,textarea{caret-color:transparent!important}";document.head.append(caretRule)')
    before = stable_frame()
    before_state = js(panel.page, 'JSON.stringify({pending:QUI.repaintPending,opacity:document.documentElement.style.opacity,width:innerWidth,height:innerHeight,focus:document.activeElement.name})')
    panel.repair_display()
    after = stable_frame()
    after_state = js(panel.page, 'JSON.stringify({pending:QUI.repaintPending,opacity:document.documentElement.style.opacity,width:innerWidth,height:innerHeight,focus:document.activeElement.name})')
    assert before.size() == after.size()
    a, b = bytes(before.constBits()), bytes(after.constBits())
    differences = sum(x != y for x, y in zip(a, b)) / max(1, len(a)) if a != b else 0
    before.save(str(folder / 'comparison-before.png'))
    after.save(str(folder / 'comparison-after.png'))
    print('FRAME:', json.dumps({'index': index, 'before': json.loads(before_state),
                               'after': json.loads(after_state), 'difference': differences,
                               'channelValues': [len(set(a)), len(set(b))]}), flush=True)
    assert differences < 0.002, ('frame changed outside the hidden caret', differences)
    assert after.save(str(folder / ('frame-' + str(index) + '.png')))
    js(panel.page, 'caretRule.remove()')
    return differences


try:
    wait(lambda: js(panel.page, '!!(window.QUI && QUI.state && document.querySelector("h1"))'), 'rendering stress window ready')
    backend = QQuickWindow.sceneGraphBackend()
    if hud.RENDERER == 'software':
        assert backend == 'software', backend
        assert '--disable-gpu' in os.environ['QTWEBENGINE_CHROMIUM_FLAGS'].split()
        assert os.environ['QSG_SOFTWARE_RENDERER_FORCE_PARTIAL_UPDATES'] == '0'
    command('task.add', {'title': 'Rendering fixture'})
    task = service.snapshot()['quests'][-1]['id']
    wait(lambda: js(panel.page, 'QUI.state.revision') == service.snapshot()['revision'], 'rendering fixture synchronized')
    js(panel.page, 'QUI.navigate("review:"+QC.trackingDay(QUI.state))')
    wait(lambda: js(panel.page, '!!document.querySelector("#review-form textarea")'), 'review textbox ready')
    panel.raise_(); panel.activateWindow(); panel.view.setFocus(); settle(100)
    js(panel.page, 'window.oldHeader=document.querySelector("#character").firstChild;window.headerMutations=0;window.rangeResets=0;new MutationObserver(ms=>headerMutations+=ms.length).observe(document.querySelector("#character"),{childList:true,subtree:true});window.nativeRange=HTMLTextAreaElement.prototype.setSelectionRange;HTMLTextAreaElement.prototype.setSelectionRange=function(){rangeResets++;return nativeRange.apply(this,arguments)};document.querySelector("#review-form textarea").focus()')
    review_text = 'Ordinary typing without repeated redraws. ' * 4
    type_text(review_text)
    day = service._eval('QC.trackingDay(current,' + str(clock[0]) + ')').toString()
    wait(lambda: service.snapshot()['reviews'].get(day, {}).get('note') == review_text, 'every typed review character reaches canonical draft')
    settle(300)
    measurements = json.loads(js(panel.page, 'JSON.stringify({headerReplaced:oldHeader!==document.querySelector("#character").firstChild,headerMutations,rangeResets})'))
    assert measurements == {'headerReplaced': False, 'headerMutations': 0, 'rangeResets': 0}, measurements
    print('PASS: autosave keeps header nodes and native caret untouched', flush=True)
    # Real Qt preedit, background snapshot, then composition commit.
    QApplication.setActiveWindow(panel)
    panel.view.setFocus(); settle(50)
    preedit = QInputMethodEvent('\u067e\u0698\u0648\u0647\u0634', [])
    QApplication.sendEvent(panel.view.focusProxy(), preedit); settle(40)
    resets = js(panel.page, 'rangeResets')
    command('task.edit', {'id': task, 'fields': {'obj': 'Background during IME'}}); settle(150)
    assert js(panel.page, 'rangeResets') == resets
    event = QInputMethodEvent(); event.setCommitString('\u067e\u0698\u0648\u0647\u0634')
    QApplication.sendEvent(panel.view.focusProxy(), event); settle(80)
    actual = js(panel.page, 'document.querySelector("#review-form textarea").value')
    assert actual.endswith('\u067e\u0698\u0648\u0647\u0634'), (actual, js(panel.page, 'document.activeElement.outerHTML'))
    print('PASS: native Persian preedit survives a concurrent snapshot', flush=True)
    click('[data-action=review-close]')
    # The DOM close event can be delayed by rendering. Suppress it entirely to
    # verify lifecycle cleanup does not depend on the next painted frame.
    js(panel.page, 'window.suppressClose=function(e){e.stopImmediatePropagation()};document.addEventListener("close",suppressClose,true)')
    click('[data-action=task-new]')
    type_text('Close event can be delayed')
    click('dialog [data-cancel]')
    wait(lambda: js(panel.page, '!document.querySelector("dialog[open]") && !QUI.editor.deferRender()'), 'cancel recovers even without the native close event')
    js(panel.page, 'document.removeEventListener("close",suppressClose,true)')
    cycles = int(os.environ.get('QUESTHUD_SOAK_CYCLES', '32'))
    screens = app.screens()
    comparisons = []
    for index in range(cycles):
        view, selector = [('today', '[data-action=task-new]'), ('planner', '[data-action=entity-new][data-group=goals]'),
                          ('planner', '[data-action=entity-new][data-group=projects]'), ('routines', '[data-action=routine-new]')][index % 4]
        area = screens[index % len(screens)].availableGeometry()
        expose_panel()
        panel.move(area.topLeft() + hud.QPoint(12, 12))
        panel.resize(min(1100, area.width() - 24), min(820, area.height() - 24))
        wait(viewport_ready, 'browser viewport matches the resized panel')
        QApplication.setActiveWindow(panel)
        panel.view.setFocus()
        click('[data-view=' + view + ']'); click(selector)
        assert js(panel.page, 'document.activeElement.name') == 'title'
        type_text('Paint cycle ' + str(index) + ' - text 123 !?')
        press(Qt.Key_A, Qt.ControlModifier); type_text('Replaced selection ' + str(index))
        press(Qt.Key_Home); press(Qt.Key_Delete); press(Qt.Key_End); press(Qt.Key_Backspace)
        js(panel.page, 'window.draftNode=document.querySelector("dialog [name=title]");window.draftValue=draftNode.value;window.draftCaret=draftNode.selectionStart')
        command('task.edit', {'id': task, 'fields': {'obj': 'Concurrent ' + str(index)}})
        settle(100)
        assert js(panel.page, 'draftNode===document.querySelector("dialog [name=title]") && draftNode.value===draftValue && document.activeElement===draftNode && draftNode.selectionStart===draftCaret')
        if index % 4 == 0:
            QTest.mouseClick(panel.repair_button, Qt.LeftButton); settle(80)
            assert js(panel.page, 'draftNode.value===draftValue && draftNode.selectionStart===draftCaret')
        else:
            press(Qt.Key_R, Qt.ControlModifier | Qt.ShiftModifier)
        assert js(panel.page, 'draftNode===document.querySelector("dialog [name=title]") && draftNode.value===draftValue && draftNode.selectionStart===draftCaret')
        if index % 8 == 0:
            comparisons.append(repaint_comparison(index))
        press(Qt.Key_Escape)
        wait(lambda: js(panel.page, '!document.querySelector("dialog[open]") && !QUI.editor.deferRender()'), 'stress cycle ' + str(index + 1) + '/' + str(cycles))
    expose_panel()
    panel.resize(640, 460)
    wait(lambda: panel.width() == 640 and panel.height() == 460 and viewport_ready(), 'minimum native and browser size synchronized')
    click('[data-view=today]'); click('[data-action=task-new]'); type_text('Minimum size render check')
    comparisons.append(repaint_comparison(cycles))
    capture(panel, 'minimum-native-recovery.png')
    assert js(panel.page, 'var r=document.querySelector("dialog footer").getBoundingClientRect();r.bottom<=innerHeight && r.top>=0')
    assert not errors, errors
    result = {'ok': True, 'mode': hud.RENDERER, 'qtBackend': backend, 'cycles': cycles,
              'screenDprs': [screen.devicePixelRatio() for screen in screens], 'reviewMeasurements': measurements,
              'frameDifferences': comparisons, 'exposureRecoveries': exposure_recoveries, 'javascriptErrors': errors}
    (folder / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
finally:
    native = panel.screen().grabWindow(panel.winId(), 0, 0, panel.width(), panel.height())
    if not native.isNull():
        native.save(str(folder / 'native-after-capture.png'))
    panel.close(); overlay.hide(); overlay.tray.hide()
    panel.deleteLater(); overlay.deleteLater(); app.sendPostedEvents(None, QEvent.DeferredDelete)
    profile.deleteLater(); app.sendPostedEvents(None, QEvent.DeferredDelete)
