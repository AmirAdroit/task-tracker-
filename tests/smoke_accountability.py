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
folder = ROOT / 'data' / 'accountability-smoke'
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



from board_alert import BoardAlertController, play_alert_sound
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import wave
sounds=[]
controller=BoardAlertController(service,bridge,sound=lambda:sounds.append(clock[0]))

def value(name, val, change=False):
    code='var el=document.querySelector('+json.dumps('[name='+name+']')+');el.value='+json.dumps(str(val))+';'
    if change: code+='el.dispatchEvent(new Event("change",{bubbles:true}));'
    return js(panel.page,code)

try:
    wait(lambda: js(panel.page,'!!(window.QUI && QUI.state && document.querySelector("h1"))'),'accountability panel loads')
    day=service._eval('QC.trackingDay(current,'+str(clock[0])+')').toString()
    js(panel.page,'document.querySelector("[data-view=routines]").click();document.querySelector("[data-action=routine-new]").click()')
    wait(lambda:js(panel.page,'document.querySelector("[name=every]").disabled && document.querySelector("[name=weekday]").disabled && document.querySelector("[name=dow-0]").disabled'),'daily hides and disables all irrelevant controls')
    value('title','تمرین روزانه')
    for mode, selector in [('weekly','weekday'),('selected','dow-1'),('interval','every'),('weekdays',None),('daily',None)]:
        value('repeat',mode,True)
        expected = ['dow-'+str(i) for i in range(7)] if mode=='selected' else [selector] if selector else []
        assertion='JSON.stringify(Array.from(document.querySelectorAll("[data-repeat] input,[data-repeat] select")).filter(e=>!e.disabled).map(e=>e.name)) === '+json.dumps(json.dumps(expected,separators=(',',':')))
        wait(lambda:js(panel.page,assertion),'only '+mode+' scheduling fields are enabled')
        if mode=='interval': value('every','3')
    value('repeat','interval',True)
    assert js(panel.page,'document.querySelector("[name=every]").value')=='3'
    value('repeat','daily',True)
    js(panel.page,'document.querySelector("#edit-form").requestSubmit()')
    wait(lambda:bool(service.snapshot()['recurring']),'daily saves without interval or weekday values')
    rid=service.snapshot()['recurring'][-1]['id']
    assert 'every' not in service.snapshot()['recurring'][-1]
    js(panel.page,'document.querySelector("[data-action=routine-edit]").click()')
    capture(panel,'routine-daily.png')
    js(panel.page,'document.querySelector("[data-cancel]").click();document.querySelector("[data-view=today]").click()')
    command('dayOff.save',{'start':day,'end':service._eval('QC.shiftDay('+json.dumps(day)+',2)').toString(),'label':'Rest'})
    wait(lambda:js(panel.page,'!!document.querySelector("[data-action=off-clear-day]")'),'Today offers direct remove day off')
    js(panel.page,'document.querySelector("[data-action=routine-add-day]").click();document.querySelector("#edit-form").requestSubmit()')
    wait(lambda:any(q.get('manualOccurrence') for q in service.snapshot()['quests']),'routine can be added explicitly on a day off')
    qid=next(q['id'] for q in service.snapshot()['quests'] if q.get('manualOccurrence'))
    js(panel.page,'document.querySelector('+json.dumps('[data-action=log][data-id="'+str(qid)+'"]')+').click()')
    value('minutes','12')
    js(panel.page,'document.querySelector("#edit-form").requestSubmit()')
    wait(lambda:any(x.get('taskId')==qid for x in service.snapshot()['sessions']),'off-day routine accepts a manual log')
    capture(panel,'today-off.png')
    js(panel.page,'document.querySelector("[data-action=off-clear-day]").click()')
    wait(lambda:not any(x['start']<=day<=x['end'] for x in service.snapshot()['daysOff']),'single click clears today while keeping rest of period')
    assert len(service.snapshot()['daysOff'])==1
    assert service.snapshot()['daysOff'][0]['start']>day
    js(panel.page,'document.querySelector("[data-view=journal]").click()')
    nextday=service.snapshot()['daysOff'][0]['start']
    value('journal-day',nextday,True)
    wait(lambda:js(panel.page,'!!document.querySelector("[data-action=off-clear-day]")'),'Journal offers selected-date removal')
    js(panel.page,'document.querySelector("[data-action=off-clear-day]").click()')
    wait(lambda:not any(x['start']<=nextday<=x['end'] for x in service.snapshot()['daysOff']),'Journal removal preserves neighbouring dates')
    js(panel.page,'document.querySelector("[data-view=settings]").click()')
    wait(lambda:js(panel.page,'document.querySelector("[name=boardHours]").disabled && !document.querySelector("[name=boardTime]").disabled'),'reminder settings adapt to daily mode')
    value('boardMode','interval',True)
    value('boardHours','2')
    value('boardStart','22:00')
    value('boardEnd','02:00')
    js(panel.page,'document.querySelector("[name=boardEnabled]").click();document.querySelector("#settings-form").requestSubmit()')
    wait(lambda:service.snapshot()['settings']['boardReminder']['enabled'],'interval settings save with overnight active hours')
    assert service.snapshot()['settings']['boardReminder']['intervalMinutes']==120
    capture(panel,'settings-board.png')
    # Preview must preserve an unsaved settings form, and native navigation must defer it.
    value('boardHours','3',True)
    before=service.path.read_bytes()
    js(panel.page,'document.querySelector("[data-action=board-test]").click()')
    wait(lambda:controller.window.isVisible() and len(sounds)==1,'Test alert opens the real native attention window and requests sound')
    assert controller.window.windowFlags() & Qt.WindowStaysOnTopHint
    capture(controller.window,'board-alert.png')
    assert service.path.read_bytes()==before
    controller.window.open_button.click()
    wait(lambda:js(panel.page,'document.querySelector("h1").textContent==="Settings" && document.querySelector("[name=boardHours]").value==="3"'),'Open board preserves unsaved settings')
    js(panel.page,'document.querySelector("#settings-form").requestSubmit()')
    wait(lambda:service.snapshot()['settings']['boardReminder']['intervalMinutes']==180,'unsaved settings can still be saved')
    controller.test()
    controller.window.snooze_button.click()
    assert not controller.window.isVisible()
    for i in range(10):
        clock[0]+=60000
        controller.poll()
    wait(lambda:controller.window.isVisible() and len(sounds)==3,'snooze reopens the same native window at ten simulated minutes')
    QTest.keyClick(controller.window,Qt.Key_Escape)
    assert not controller.window.isVisible() and service.board_reminder.pending
    controller.test()
    controller.window.close()
    assert not controller.window.isVisible() and service.board_reminder.pending
    controller.test()
    controller.window.dismiss_button.click()
    assert not controller.window.isVisible() and not service.board_reminder.pending
    controller.test()
    controller.resume()
    assert not controller.window.isVisible() and not service.board_reminder.pending
    js(panel.page,'document.querySelector("[data-view=routines]").click();document.querySelector("[data-action=routine-new]").click()')
    value('title','Unsaved routine draft')
    controller.test()
    controller.window.open_button.click()
    wait(lambda:js(panel.page,'document.querySelector("dialog[open] [name=title]").value==="Unsaved routine draft"'),'native reminder preserves an open editor')
    js(panel.page,'document.querySelector("[data-cancel]").click()')
    controller.test()
    controller.window.open_button.click()
    wait(lambda:js(panel.page,'document.querySelector("h1").textContent==="Today"'),'Open board navigates to Today when no edits are pending')
    with wave.open(str(ROOT/'assets'/'board-alert.wav'),'rb') as audio:
        assert audio.getnframes()>0 and audio.getnchannels()==1
    play_alert_sound() # Real Windows playback call; audibility depends on device/system volume.
    print('PASS: bundled sound accepted by real Windows playback API',flush=True)
    assert not errors,errors
    print(json.dumps({'ok':True,'screenshots':str(folder),'javascriptErrors':errors,'soundRequests':len(sounds)}),flush=True)
finally:
    controller.dismiss()
    app.removeNativeEventFilter(controller.filter)
    controller.window.deleteLater()
    panel.close()
    overlay.hide()
    overlay.tray.hide()
    panel.deleteLater()
    overlay.deleteLater()
    app.sendPostedEvents(None,QEvent.DeferredDelete)
    profile.deleteLater()
    app.sendPostedEvents(None,QEvent.DeferredDelete)
