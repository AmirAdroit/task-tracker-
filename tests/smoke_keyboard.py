"""Real Qt keyboard/IME regressions. Synthetic data only; no physical layout claims."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--enable-transparent-visuals")

from PySide6.QtCore import QEventLoop, QTimer, QSettings, QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
import hud
from state_service import StateService

app = QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)
folder = ROOT / 'data' / 'keyboard-smoke'
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


from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QInputMethodEvent
from PySide6.QtTest import QTest


def settle(ms=100):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def click(selector):
    assert js(panel.page, '!!document.querySelector(' + json.dumps(selector) + ')'), selector
    js(panel.page, 'document.querySelector(' + json.dumps(selector) + ').click()')


def key(key_code, modifiers=Qt.NoModifier):
    QTest.keyClick(panel.view.focusProxy(), key_code, modifiers)
    settle(25)


def typing(text):
    # QTest.keyClicks supports ASCII. Non-ASCII is committed through Qt's IME API below.
    QTest.keyClicks(panel.view.focusProxy(), text)
    settle(25)


def value(name):
    return js(panel.page, 'document.querySelector("dialog[open] [name=' + name + ']").value')


def focus(name):
    js(panel.page, 'document.querySelector("dialog[open] [name=' + name + ']").focus()')


def closed(label):
    wait(lambda: js(panel.page, '!document.querySelector("dialog[open]") && !QUI.editor.deferRender()'), label)


def open_editor(view, selector, first='title', keyboard=False):
    click('[data-view=' + view + ']')
    if keyboard:
        js(panel.page, 'document.querySelector(' + json.dumps(selector) + ').focus()')
        key(Qt.Key_Space)
    else:
        click(selector)
    assert js(panel.page, 'document.activeElement.name') == first, (selector, js(panel.page, 'document.activeElement.outerHTML'))


try:
    wait(lambda: js(panel.page, '!!(window.QUI && QUI.state && document.querySelector("h1"))'), 'keyboard regression window ready')
    command('entity.save', {'group': 'projects', 'fields': {'title': 'Keyboard fixture project'}})
    project = service.snapshot()['projects'][-1]['id']
    wait(lambda: js(panel.page, 'QUI.state.revision') == service.snapshot()['revision'], 'fixture reaches panel')
    editors = [
        ('planner', '[data-action=entity-new][data-group=periods]', 'periods'),
        ('planner', '[data-action=entity-new][data-group=goals]', 'goals'),
        ('planner', '[data-action=entity-new][data-group=projects]', 'projects'),
        ('planner', '[data-action=milestone-new][data-id="' + str(project) + '"]', 'milestones'),
        ('quests', '[data-action=task-new]', 'quests'),
        ('quests', '[data-action=entity-new][data-group=categories]', 'categories'),
        ('routines', '[data-action=routine-new]', 'recurring'),
    ]
    persian = '\u0628\u0631\u0646\u0627\u0645\u0647 \u0645\u0637\u0627\u0644\u0639\u0647'
    for index, (view, selector, group) in enumerate(editors):
        baseline = service.snapshot()
        open_editor(view, selector, keyboard=index % 2 == 0)
        typing('Study plan 42: [test]!?')
        assert value('title') == 'Study plan 42: [test]!?'
        key(Qt.Key_Return); settle()
        assert js(panel.page, '!!document.querySelector("dialog[open]")')
        assert service.snapshot() == baseline
        # Selection, Home/End, deletion, punctuation and a genuine Qt IME commit.
        key(Qt.Key_A, Qt.ControlModifier); typing('abcXYZ')
        key(Qt.Key_Home); key(Qt.Key_Delete); key(Qt.Key_End); key(Qt.Key_Backspace)
        assert value('title') == 'bcXY'
        key(Qt.Key_Home); key(Qt.Key_End, Qt.ShiftModifier); typing('Revised 7 ')
        event = QInputMethodEvent(); event.setCommitString(persian)
        QApplication.sendEvent(panel.view.focusProxy(), event)
        settle(25)
        assert value('title') == 'Revised 7 ' + persian
        assert service.snapshot() == baseline
        # The first/last boundary wraps without escaping; interior date segments stay native.
        js(panel.page, 'document.querySelector("dialog [type=submit]").focus()')
        key(Qt.Key_Tab)
        assert js(panel.page, 'document.activeElement.matches("dialog header [data-cancel]")'), js(panel.page, 'document.activeElement.outerHTML')
        key(Qt.Key_Tab, Qt.ShiftModifier)
        assert js(panel.page, 'document.activeElement.type') == 'submit'
        for _ in range(38):
            key(Qt.Key_Tab)
            assert js(panel.page, '!!document.activeElement.closest("dialog[open]") && !document.activeElement.disabled && !document.activeElement.closest("[hidden]")')
        key(Qt.Key_Escape); closed(group + ': immediate typing, Enter, editing, IME, Tab and Escape')
        assert js(panel.page, 'document.activeElement.matches(' + json.dumps(selector) + ')')
        assert service.snapshot() == baseline
        # Actual keyboard save, never field.value assignment.
        open_editor(view, selector)
        title = 'Saved ' + group + ' 17!'
        typing(title); key(Qt.Key_Return, Qt.ControlModifier)
        closed(group + ': Ctrl+Enter saves once')
        title_key = 'name' if group == 'categories' else 'title'
        assert sum(x.get(title_key) == title for x in service.snapshot()[group]) == 1

    click('[data-view=planner]')
    click('[data-action=entity-new][data-group=projects]')
    typing('Textarea and native controls')
    key(Qt.Key_Tab); assert js(panel.page, 'document.activeElement.name') == 'description'
    typing('Line one'); key(Qt.Key_Return); typing('Line two')
    assert value('description') == 'Line one\nLine two'
    revision = service.snapshot()['revision']
    key(Qt.Key_Tab); assert js(panel.page, 'document.activeElement.name') == 'goalId'
    key(Qt.Key_Down); key(Qt.Key_Return); settle()
    assert value('goalId') != ''
    assert service.snapshot()['revision'] == revision
    # Simulated DOM composition states cover Enter before/after compositionend;
    # the Persian commit above exercises Qt's real input-method delivery path.
    focus('title')
    js(panel.page, 'document.activeElement.dispatchEvent(new CompositionEvent("compositionstart",{bubbles:true}))')
    key(Qt.Key_Return, Qt.ControlModifier); key(Qt.Key_Return)
    assert service.snapshot()['revision'] == revision
    js(panel.page, 'var t=document.activeElement;t.dispatchEvent(new CompositionEvent("compositionend",{bubbles:true}));t.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",ctrlKey:true,bubbles:true}))')
    assert service.snapshot()['revision'] == revision
    click('dialog [data-cancel]'); closed('textarea, native select arrows and composition confirmation do not save')

    open_editor('planner', '[data-action=entity-new][data-group=periods]')
    typing('Date key handling')
    key(Qt.Key_Tab); assert js(panel.page, 'document.activeElement.name') == 'start'
    before = value('start'); key(Qt.Key_Up)
    assert value('start') != before
    key(Qt.Key_Return); settle()
    assert js(panel.page, '!!document.querySelector("dialog[open]")')
    key(Qt.Key_Escape); closed('date arrows and Enter preserve editor')

    # Native validation and service rejection must retain the draft and return to a useful field.
    open_editor('today', '[data-action=task-new]')
    key(Qt.Key_Return, Qt.ControlModifier)
    assert js(panel.page, 'document.activeElement.name') == 'title'
    typing('   '); key(Qt.Key_Return, Qt.ControlModifier)
    wait(lambda: bool(js(panel.page, 'document.querySelector("dialog #form-error").textContent')), 'rejected save remains in its editor')
    assert js(panel.page, 'document.activeElement.name') == 'title'
    assert value('title') == '   '
    key(Qt.Key_A, Qt.ControlModifier); typing('Corrected keyboard task')
    # Native validation failure must not arm the next plain Enter.
    key(Qt.Key_Return); settle()
    assert not any(q['title'] == 'Corrected keyboard task' for q in service.snapshot()['quests'])
    key(Qt.Key_Return, Qt.ControlModifier); closed('failed-save correction keeps focus and saves explicitly')

    task = next(q['id'] for q in service.snapshot()['quests'] if q['title'] == 'Corrected keyboard task')
    open_editor('quests', '[data-action=task-edit][data-id="' + str(task) + '"]')
    typing(' edited'); key(Qt.Key_Return); settle()
    assert next(q['title'] for q in service.snapshot()['quests'] if q['id'] == task) == 'Corrected keyboard task'
    key(Qt.Key_Return, Qt.ControlModifier); closed('editing an existing task uses the same keyboard policy')

    # Check the other shared editor shapes through their normal buttons.
    for view, selector, first in [
        ('today', '[data-action=schedule]', 'taskId'),
        ('today', '[data-action=log]', 'taskId'),
        ('settings', '[data-action=off]', 'start'),
        ('settings', '[data-action=off-clear-range]', 'start'),
        ('today', '[data-action=routine-add-day]', 'routineId'),
    ]:
        revision = service.snapshot()['revision']
        open_editor(view, selector, first)
        key(Qt.Key_Return); settle()
        assert service.snapshot()['revision'] == revision
        key(Qt.Key_Escape)  # First Escape can dismiss the native select/date popup.
        if js(panel.page, '!!document.querySelector("dialog[open]")'):
            key(Qt.Key_Escape)
        closed(first + ': shared editor shape retains focus and blocks implicit save')

    # Delayed submissions, rapid reopening and background changes while typing.
    click('[data-view=today]')
    js(panel.page, 'window.originalDispatch=QUI.store.dispatch;QUI.store.dispatch=function(c,cb){originalDispatch(c,function(r){setTimeout(function(){cb(r)},450)})}')
    click('[data-action=task-new]'); typing('Pending keyboard task')
    key(Qt.Key_Return, Qt.ControlModifier); key(Qt.Key_Return, Qt.ControlModifier)
    assert js(panel.page, 'document.querySelector("#edit-form").dataset.pending') == '1'
    key(Qt.Key_Escape); closed('pending editor can be cancelled')
    click('[data-action=task-new]'); typing('Newer typing draft')
    command('task.add', {'title': 'Concurrent background change'})
    settle(700)
    assert value('title') == 'Newer typing draft'
    assert js(panel.page, 'document.activeElement.name') == 'title'
    typing(' keeps focus')
    assert value('title') == 'Newer typing draft keeps focus'
    assert sum(q['title'] == 'Pending keyboard task' for q in service.snapshot()['quests']) == 1
    js(panel.page, 'QUI.store.dispatch=originalDispatch')
    capture(panel, 'normal-keyboard-editor.png')
    panel.resize(640, 460); settle()
    assert js(panel.page, 'var r=document.querySelector("dialog footer").getBoundingClientRect();r.bottom<=innerHeight && r.top>=0')
    capture(panel, 'minimum-keyboard-editor.png')
    key(Qt.Key_Escape); closed('new draft survives late reply and background updates at both sizes')
    assert js(panel.page, 'document.activeElement.matches("[data-action=task-new]")')

    # If a save removes its opener, use the current view heading.
    panel.resize(1300, 900)
    click('[data-view=planner]')
    click('[data-action=entity-edit][data-group=projects][data-id="' + str(project) + '"]')
    click('dialog [data-action=entity-archive]')
    closed('archived opener falls back to the view heading')
    assert js(panel.page, 'document.activeElement.tagName') == 'H1', js(panel.page, 'document.activeElement.outerHTML')

    # Inline Settings shares explicit commit policy, without trapping the page's Tab order.
    click('[data-view=settings]')
    js(panel.page, 'document.querySelector("[name=reviewEvery]").focus()')
    key(Qt.Key_A, Qt.ControlModifier); typing('73'); key(Qt.Key_Return); settle()
    assert service.snapshot()['settings']['reviewEvery'] != 73
    key(Qt.Key_Return, Qt.ControlModifier)
    wait(lambda: service.snapshot()['settings']['reviewEvery'] == 73 and js(panel.page, 'document.getElementById("notice").textContent==="Settings saved"'), 'Settings saves with Ctrl+Enter only')

    # HUD dialogs use the same controller; native key delivery targets the HUD here.
    wait(lambda: js(overlay.page, '!!(window.QUI && QUI.state)'), 'HUD keyboard test ready')
    js(overlay.page, 'QUI.start(' + str(task) + ')')
    assert js(overlay.page, 'document.activeElement.name') == 'minutes'
    QTest.keyClick(overlay.view.focusProxy(), Qt.Key_A, Qt.ControlModifier)
    QTest.keyClicks(overlay.view.focusProxy(), '3')
    QTest.keyClick(overlay.view.focusProxy(), Qt.Key_Return)
    settle(25)
    assert not service.snapshot()['sessions']
    QTest.keyClick(overlay.view.focusProxy(), Qt.Key_Return, Qt.ControlModifier)
    wait(lambda: bool(service.snapshot()['sessions']), 'HUD session editor respects explicit keyboard save')
    wait(lambda: js(overlay.page, '!document.querySelector("dialog[open]") && !QUI.editor.deferRender()'), 'HUD finishes its editor refresh')
    timer = service.snapshot()['sessions'][-1]['id']
    open_editor('today', '[data-action=extend][data-id="' + str(timer) + '"]', 'minutes')
    key(Qt.Key_A, Qt.ControlModifier); typing('15'); key(Qt.Key_Return); settle()
    assert service.snapshot()['sessions'][-1]['limitMs'] == 3 * 60000
    key(Qt.Key_Escape); closed('session extension requires explicit save')
    clock[0] += 60000
    command('session.finish', {'id': timer})
    day = service._eval('QC.trackingDay(current,' + str(clock[0]) + ')').toString()
    command('log.save', {'taskId': task, 'day': day, 'minutes': 12, 'note': 'Keyboard log fixture'})
    manual = service.snapshot()['sessions'][-1]['id']
    command('import.merge', {'data': {'version': 2, 'gold': 0, 'goldEarned': 0, 'quests': [], 'recurring': [],
        'completed': [{'title': 'Keyboard legacy fixture', 'at': clock[0], 'ms': 13 * 3600000, 'xp': 0}], 'nextId': 2}})
    wait(lambda: js(panel.page, 'QUI.state.revision') == service.snapshot()['revision'], 'correction fixtures reach the panel')
    for view, selector, first in [
        ('journal', '[data-action=log-edit][data-id="' + str(manual) + '"]', 'taskId'),
        ('journal', '[data-action=timer-correct][data-id="' + str(timer) + '"]', 'day'),
        ('settings', '[data-action=legacy-correct]', 'minutes'),
    ]:
        revision = service.snapshot()['revision']
        open_editor(view, selector, first)
        focus('minutes'); key(Qt.Key_A, Qt.ControlModifier); typing('5.5')
        key(Qt.Key_Return); settle()
        assert service.snapshot()['revision'] == revision
        key(Qt.Key_Escape); closed(view + ': log/time correction blocks implicit save')

    # A real pointer click on Save also commits once; the shortcut is optional.
    open_editor('today', '[data-action=task-new]')
    typing('Pointer saved keyboard draft')
    position = json.loads(js(panel.page, 'var r=document.querySelector("dialog [type=submit]").getBoundingClientRect();JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2})'))
    QTest.mouseClick(panel.view.focusProxy(), Qt.LeftButton, Qt.NoModifier, QPoint(round(position['x']), round(position['y'])))
    closed('pointer Save commits a keyboard-entered draft')
    assert sum(q['title'] == 'Pointer saved keyboard draft' for q in service.snapshot()['quests']) == 1
    assert not errors, errors
    print(json.dumps({'ok': True, 'javascriptErrors': errors, 'screenshots': str(folder),
                      'inputCoverage': 'Qt key events and IME commits; composition states simulated; physical Windows layout not tested'}), flush=True)
finally:
    panel.close(); overlay.hide(); overlay.tray.hide()
    panel.deleteLater(); overlay.deleteLater(); app.sendPostedEvents(None, QEvent.DeferredDelete)
    profile.deleteLater(); app.sendPostedEvents(None, QEvent.DeferredDelete)
