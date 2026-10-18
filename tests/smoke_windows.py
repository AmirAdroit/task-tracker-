"""Exercise both real Qt WebEngine windows using synthetic, isolated data. No host startup changes."""
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
folder = ROOT / 'data' / 'ui-smoke'
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


try:
    wait(lambda: js(panel.page, '!!(window.QUI && QUI.state && document.querySelector("h1"))'), 'panel loads over QWebChannel')
    wait(lambda: js(overlay.page, '!!(window.QUI && QUI.state && document.getElementById("lvl").textContent)'), 'HUD loads over QWebChannel')
    command('task.add', {'title': 'یادگیری کوبرنتیز', 'obj': 'Build and restore a lab', 'estimateMinutes': 240})
    task = service.snapshot()['quests'][-1]['id']
    day = service._eval('QC.trackingDay(current,' + str(clock[0]) + ')').toString()
    command('allocation.save', {'taskId': task, 'day': day, 'minutes': 90})
    command('log.save', {'taskId': task, 'day': day, 'minutes': 45, 'note': 'تمرین عملی'})
    wait(lambda: js(panel.page, 'document.body.innerText.includes("یادگیری کوبرنتیز")'), 'Persian task reaches panel')
    wait(lambda: js(overlay.page, 'document.body.innerText.includes("یادگیری کوبرنتیز")'), 'Persian task reaches HUD')
    js(panel.page, 'document.querySelector("[data-action=task-new]").click()')
    js(panel.page, 'document.querySelector("#edit-form [name=title]").value="Unsaved draft"; document.querySelector("#edit-form [name=title]").focus()')
    command('task.edit', {'id': task, 'fields': {'obj': 'Changed from another window'}})
    wait(lambda: js(panel.page, 'document.querySelector("dialog").open && document.querySelector("#edit-form [name=title]").value === "Unsaved draft"'), 'background changes preserve editor and focus')
    js(panel.page, 'document.querySelector("#edit-form [name=title]").value="Created through UI"; document.querySelector("#edit-form").requestSubmit()')
    wait(lambda: any(q['title'] == 'Created through UI' for q in service.snapshot()['quests']), 'UI task form saves through native command service')
    command('session.start', {'taskId': task, 'minutes': 180})
    command('session.start', {'taskId': service.snapshot()['quests'][0]['id'], 'minutes': 60})
    wait(lambda: js(panel.page, 'document.body.innerText.includes("2 timers running together")'), 'concurrent session UI warns about overlaps')
    clock[0] += 4 * 3600000
    service.tick()
    wait(lambda: js(panel.page, 'document.body.innerText.includes("expired")'), 'native expiration reaches UI without page timer')
    js(panel.page, 'document.querySelector("[data-view=planner]").click()')
    wait(lambda: js(panel.page, 'document.querySelectorAll(".day").length === 7'), 'weekly planner renders seven allocation targets')
    js(panel.page, 'document.querySelector("[data-action=entity-new][data-group=periods]").click(); document.querySelector("#edit-form [name=title]").value="Quarter lab"; document.querySelector("[data-action=period-13]").click(); document.querySelector("#edit-form").requestSubmit()')
    wait(lambda: bool(service.snapshot()['periods']), 'flexible planning period saves through UI')
    pid = service.snapshot()['periods'][0]['id']
    js(panel.page, 'document.querySelector("[data-action=entity-new][data-group=goals]").click(); document.querySelector("#edit-form [name=title]").value="Reliable infrastructure"; document.querySelector("#edit-form [name=success]").value="Demonstrate a restore"; document.querySelector("#edit-form [name=periodId]").value=' + json.dumps(str(pid)) + '; document.querySelector("#edit-form").requestSubmit()')
    wait(lambda: bool(service.snapshot()['goals']), 'goal criterion and period relationship save through UI')
    gid = service.snapshot()['goals'][0]['id']
    js(panel.page, 'document.querySelector("[data-action=entity-new][data-group=projects]").click(); document.querySelector("#edit-form [name=title]").value="Kubernetes lab"; document.querySelector("#edit-form [name=goalId]").value=' + json.dumps(str(gid)) + '; document.querySelector("#edit-form").requestSubmit()')
    wait(lambda: bool(service.snapshot()['projects']), 'project can be linked to goal through UI')
    capture(panel, 'planner.png')
    js(panel.page, 'document.querySelector("[data-view=journal]").click()')
    wait(lambda: js(panel.page, 'document.querySelectorAll(".calendar button").length === 42'), 'journal calendar and daily records render')
    capture(panel, 'journal.png')
    js(panel.page, 'document.querySelector("[data-view=routines]").click(); document.querySelector("[data-action=routine-new]").click()')
    js(panel.page, 'document.querySelector("#edit-form [name=title]").value="Karate"; document.querySelector("#edit-form [name=repeat]").value="interval"; document.querySelector("#edit-form [name=every]").value="2"; document.querySelector("#edit-form").requestSubmit()')
    wait(lambda: any(t['title'] == 'Karate' for t in service.snapshot()['recurring']), 'routine editor saves every-other-day schedule')
    js(panel.page, 'document.querySelector("[data-view=settings]").click(); var r=document.querySelector("[name=reviewEvery]"); r.value="45"; r.dispatchEvent(new Event("input",{bubbles:true}))')
    bridge.openView('review:' + day)
    wait(lambda: js(panel.page, 'document.querySelector("h1").textContent === "Settings" && document.querySelector("[name=reviewEvery]").value === "45"'), 'review reminder cannot discard unsaved settings')
    js(panel.page, 'document.querySelector("#settings-form").requestSubmit()')
    wait(lambda: service.snapshot()['settings']['reviewEvery'] == 45, 'settings save through native service')
    js(panel.page, 'document.querySelector("[data-view=today]").click(); document.querySelector("[data-action=log]").click(); document.querySelector("#edit-form [name=taskId]").value=' + json.dumps(str(task)) + '; document.querySelector("#edit-form [name=minutes]").value="20"; document.querySelector("#edit-form [name=note]").value="Manual UI log"; document.querySelector("#edit-form").requestSubmit()')
    wait(lambda: any(x.get('note') == 'Manual UI log' for x in service.snapshot()['sessions']), 'manual effort can be logged without starting a timer')
    command('settings.save', {'fields': {'reviewTime': '00:00'}})
    bridge.openView('review:' + day)
    wait(lambda: js(panel.page, '!!document.getElementById("review-form")'), 'native review navigation opens check-in')
    js(panel.page, 'var n=document.querySelector("#review-form [name=note]"); n.value="Saved draft فارسی"; n.dispatchEvent(new Event("input",{bubbles:true}))')
    wait(lambda: service.snapshot()['reviews'].get(day, {}).get('note') == 'Saved draft فارسی', 'daily review draft persists while typing')
    capture(panel, 'today-review.png')
    js(panel.page, 'document.querySelector("[data-action=review-close]").click()')
    wait(lambda: js(panel.page, '!document.getElementById("review-form")'), 'closing a review actually removes its form')
    bridge.openView('review:' + day)
    wait(lambda: js(panel.page, '!!document.getElementById("review-form")'), 'closed draft can be reopened')
    js(panel.page, 'document.querySelectorAll("#review-form select").forEach(function(s){s.value="partial";s.dispatchEvent(new Event("change",{bubbles:true}))})')
    wait(lambda: len(service.snapshot()['reviews'][day].get('outcomes', {})) == 2, 'review outcomes save before submission')
    js(panel.page, 'document.querySelector("[data-action=review-submit]").click()')
    wait(lambda: service.snapshot()['reviews'][day]['status'] == 'submitted' and js(panel.page, '!document.getElementById("review-form")'), 'submitting a review closes it without a stuck focused form')
    js(panel.page, 'document.querySelector("[data-action=task-new]").click()')
    command('task.add', {'title':'Added while editor open'})
    js(panel.page, 'document.querySelector("#edit-form [data-cancel]").click()')
    wait(lambda: js(panel.page, '!document.querySelector("dialog[open]") && document.getElementById("update").hidden'), 'cancelling an editor applies deferred background updates')
    overlay.resize(240, 320)
    QTimer.singleShot(0, lambda: None)
    wait(lambda: js(overlay.page, 'document.getElementById("addBtn").getBoundingClientRect().right <= innerWidth && document.getElementById("addBtn").getBoundingClientRect().bottom <= innerHeight'), 'compact HUD keeps add controls inside its viewport')
    js(overlay.page, 'document.getElementById("collapseBtn").click()')
    wait(lambda: overlay.height() == 156 and js(overlay.page, 'getComputedStyle(document.querySelector(".collapsible")).display === "none"'), 'HUD collapse hides content and shrinks the native window')
    js(overlay.page, 'document.getElementById("collapseBtn").click()')
    wait(lambda: overlay.height() == 320, 'HUD expansion restores its previous height')
    capture(overlay, 'hud.png')
    assert not errors, errors
    print(json.dumps({'ok': True, 'screenshots': str(folder), 'javascriptErrors': errors}, ensure_ascii=False), flush=True)
finally:
    panel.close()
    overlay.hide()
    overlay.tray.hide()
    panel.deleteLater()
    overlay.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    profile.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
