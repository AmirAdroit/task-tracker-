"""Exercise both real Qt WebEngine windows using synthetic, isolated data. No host startup changes."""
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
folder = ROOT / 'data' / 'panel-ui-smoke'
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
from PySide6.QtTest import QTest


def sync():
    revision=service.snapshot()['revision']
    wait(lambda:js(panel.page,'QUI.state.revision >= '+str(revision)),'latest snapshot reaches panel')


def click(selector):
    assert js(panel.page,'!!document.querySelector('+json.dumps(selector)+')'),selector
    js(panel.page,'document.querySelector('+json.dumps(selector)+').click()')


def field(name,value,event=None):
    code='var f=document.querySelector('+json.dumps('[name='+name+']')+');f.value='+json.dumps(str(value))+';'
    if event: code+='f.dispatchEvent(new Event('+json.dumps(event)+',{bubbles:true}));'
    js(panel.page,code)


def close_editor():
    click('dialog[open] [data-cancel]')
    wait(lambda:js(panel.page,'!document.querySelector("dialog[open]") && !QUI.editor.deferRender()'),'editor closes and restores page focus')


def settle(ms=550):
    loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()


try:
    wait(lambda:js(panel.page,'!!(window.QUI && QUI.state && document.querySelector("h1"))'),'panel UI regression window ready')
    command('entity.save',{'group':'periods','fields':{'title':'Period','start':'2026-01-01','end':'2026-12-31'}})
    period=service.snapshot()['periods'][-1]['id']
    command('entity.save',{'group':'goals','fields':{'title':'هدف آزمایشی','periodId':period}})
    goal=service.snapshot()['goals'][-1]['id']
    command('entity.save',{'group':'projects','fields':{'title':'Project','goalId':goal}})
    project=service.snapshot()['projects'][-1]['id']
    command('entity.save',{'group':'milestones','fields':{'title':'Milestone','projectId':project}})
    milestone=service.snapshot()['milestones'][-1]['id']
    command('task.add',{'title':'Linked task','projectId':project,'milestoneId':milestone})
    task=service.snapshot()['quests'][-1]['id']
    day=service._eval('QC.trackingDay(current,'+str(clock[0])+')').toString()
    command('allocation.save',{'taskId':task,'day':day,'minutes':30})
    allocation=service.snapshot()['allocations'][-1]['id']

    for group,id,owner_group,owner_id,field_name in [('periods',period,'goals',goal,'periodId'),('goals',goal,'projects',project,'goalId')]:
        command('entity.archive',{'group':group,'id':id});sync()
        click('[data-view=planner]')
        click('[data-action=entity-edit][data-group='+owner_group+'][data-id="'+str(owner_id)+'"]')
        assert js(panel.page,'document.querySelector('+json.dumps('[name='+field_name+']')+').value')==str(id)
        js(panel.page,'document.querySelector("#edit-form [type=submit]").click()')
        wait(lambda:js(panel.page,'!document.querySelector("dialog[open]") && !QUI.editor.deferRender()'),owner_group+' editor preserves its archived parent association')
    command('entity.save',{'group':'periods','fields':{'title':'Temporary period','start':'2026-01-01','end':'2026-12-31'}})
    temporary_period=service.snapshot()['periods'][-1]['id'];sync()
    click('[data-view=planner]');field('period-filter',temporary_period,'change')
    wait(lambda:js(panel.page,'!!document.querySelector("[data-action=entity-edit][data-group=periods]")'),'selected period renders its edit action')
    click('[data-action=entity-edit][data-group=periods]');click('[data-action=entity-archive]')
    wait(lambda:js(panel.page,'!document.querySelector("dialog[open]") && !QUI.editor.deferRender() && document.querySelector("[name=period-filter]").value===""'),'archiving selected period resets the visible filter consistently')

    for group,id in [('periods',period),('goals',goal),('projects',project),('milestones',milestone)]:
        command('entity.archive',{'group':group,'id':id})
    sync()
    click('[data-view=quests]')
    click('[data-action=task-edit][data-id="'+str(task)+'"]')
    assert js(panel.page,'document.querySelector("[name=projectId]").value')==str(project)
    assert js(panel.page,'document.querySelector("[name=milestoneId]").value')==str(milestone)
    field('title','Linked task edited')
    js(panel.page,'document.querySelector("#edit-form [type=submit]").click()')
    wait(lambda:js(panel.page,'!document.querySelector("dialog[open]") && !QUI.editor.deferRender()'),'task editor preserves archived project and milestone associations')
    q=next(q for q in service.snapshot()['quests'] if q['id']==task)
    assert (q['projectId'],q['milestoneId'])==(project,milestone)
    command('task.complete',{'id':task}); sync()
    click('[data-view=planner]')
    click('[data-action=week-now]')
    click('[data-action=allocation-edit][data-id="'+str(allocation)+'"]')
    assert js(panel.page,'document.querySelector("[name=taskId]").value')==str(task)
    field('minutes','35')
    js(panel.page,'document.querySelector("#edit-form [type=submit]").click()')
    wait(lambda:next(a for a in service.snapshot()['allocations'] if a['id']==allocation)['minutes']==35,'completed-task allocations remain editable')
    wait(lambda:js(panel.page,'!document.querySelector("dialog[open]") && !QUI.editor.deferRender()'),'allocation editor closes')
    click('[data-view=settings]')
    field('reviewEvery','77','input')
    click('[data-action=entity-edit][data-group=categories]')
    field('title','Edited category')
    js(panel.page,'document.querySelector("#edit-form [type=submit]").click()')
    wait(lambda:js(panel.page,'!document.querySelector("dialog[open]") && !QUI.editor.deferRender()'),'category edit completes')
    assert js(panel.page,'document.querySelector("[name=reviewEvery]").value')=='77'
    print('PASS: category editing preserves unsaved Settings input',flush=True)
    js(panel.page,'document.querySelector("#settings-form [type=submit]").click()')
    wait(lambda:js(panel.page,'document.getElementById("notice").textContent==="Settings saved"'),'settings draft can be saved afterward')
    click('[data-view=today]')
    js(panel.page,'window.rawDispatch=QUI.store.dispatch;window.delayedReplies=0;QUI.store.dispatch=function(c,cb){rawDispatch(c,function(r){setTimeout(function(){cb(r);delayedReplies++},400)})}')
    for action,title in [('task-new','Double task'),('entity-new','Double goal')]:
        if action=='entity-new':
            click('[data-view=planner]');click('[data-action=entity-new][data-group=goals]')
        else: click('[data-action=task-new]')
        field('title',title)
        js(panel.page,'document.querySelector("#edit-form [type=submit]").click();document.querySelector("#edit-form [type=submit]").click()')
        wait(lambda:js(panel.page,'!document.querySelector("dialog[open]") && !QUI.editor.deferRender()'),'pending '+title+' form sends one save')
        group='goals' if action=='entity-new' else 'quests'
        assert sum(q['title']==title for q in service.snapshot()[group])==1
    click('[data-view=today]')
    click('[data-action=task-new]');field('title','Older pending task')
    js(panel.page,'document.querySelector("#edit-form [type=submit]").click();document.querySelector("[data-cancel]").click();document.querySelector("[data-action=task-new]").click();document.querySelector("#edit-form [name=title]").value="New unsaved editor"')
    wait(lambda:any(q['title']=='Older pending task' for q in service.snapshot()['quests']),'older task reaches canonical state')
    command('task.add',{'title':'Newer background task'})
    sync();settle()
    assert js(panel.page,'document.querySelector("dialog[open] [name=title]").value')=='New unsaved editor'
    assert js(panel.page,'QUI.state.revision')==service.snapshot()['revision']
    assert js(panel.page,'QUI.state.quests.some(q=>q.title==="Newer background task")')
    print('PASS: delayed reply preserves a newer editor and a newer snapshot',flush=True)
    close_editor()
    click('[data-action=task-new]');field('title','   ')
    js(panel.page,'document.querySelector("#edit-form [type=submit]").click();document.querySelector("[data-cancel]").click();document.querySelector("[data-action=task-new]").click();document.querySelector("#edit-form [name=title]").value="Another clean draft"')
    settle()
    assert js(panel.page,'document.querySelector("dialog[open] #form-error").textContent')==''
    assert js(panel.page,'!document.querySelector("dialog[open] [name=title]").disabled')
    print('PASS: a late rejection cannot write errors into the next editor',flush=True)
    close_editor()
    js(panel.page,'QUI.store.dispatch=rawDispatch')
    # Exercise every entity editor repeatedly without changing any domain records.
    baseline=service.snapshot()
    for _ in range(3):
        for view_name in ['planner','journal','quests','routines','stats','settings','today']:
            click('[data-view='+view_name+']')
            assert js(panel.page,'!!document.querySelector("nav [data-view='+view_name+'].active")')
        click('[data-view=planner]')
        for group in ['periods','goals','projects']:
            click('[data-action=entity-new][data-group='+group+']');field('title','Cancelled draft');close_editor()
    assert service.snapshot()==baseline
    print('PASS: repeated menu/editor traversal leaves domain data unchanged',flush=True)

    click('[data-view=quests]')
    js(panel.page,'document.querySelector("[name=filter-search]").focus()')
    QTest.keyClicks(panel.view.focusProxy(),'No match')
    position=json.loads(js(panel.page,'var r=document.querySelector("[data-action=task-new]").getBoundingClientRect();JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2})'))
    QTest.mouseClick(panel.view.focusProxy(),Qt.LeftButton,Qt.NoModifier,QPoint(round(position['x']),round(position['y'])))
    wait(lambda:js(panel.page,'!!document.querySelector("dialog[open]")'),'first mouse click after typing a filter opens its editor')
    close_editor()
    js(panel.page,'document.querySelector("[name=filter-search]").focus()')
    QTest.keyClicks(panel.view.focusProxy(),' more')
    QTest.keyClick(panel.view.focusProxy(),Qt.Key_Tab)
    wait(lambda:js(panel.page,'document.activeElement.name==="filter-status"'),'filter refresh preserves keyboard Tab navigation')
    field('filter-search','','change');settle(50)

    # All footer actions must remain visible on the smallest supported panel.
    panel.resize(640,460)
    click('[data-view=today]');click('[data-action=task-new]')
    field('title','Small screen draft')
    wait(lambda:js(panel.page,'var r=document.querySelector("dialog footer").getBoundingClientRect();r.bottom<=innerHeight && r.top>=0'),'long editor keeps Save/Cancel inside a small viewport')
    js(panel.page,'document.querySelector("dialog .form-grid").scrollTop=10000')
    assert js(panel.page,'document.querySelector("dialog header").getBoundingClientRect().top>=0')
    assert js(panel.page,'getComputedStyle(document.documentElement).overflowY')=='hidden'
    capture(panel,'small-task-editor.png')
    close_editor()
    # Stress wrapping without changing task/goal/project behavior.
    long_title='A'*200+' پروژه فارسی '*20
    command('entity.save',{'group':'projects','fields':{'title':long_title}});sync()
    click('[data-view=planner]')
    wait(lambda:js(panel.page,'document.documentElement.scrollWidth<=innerWidth+1'),'long project text does not widen the whole panel')
    capture(panel,'small-planner.png')
    js(panel.page,'document.querySelector(".week").scrollLeft=150;document.activeElement.blur()')
    command('task.add',{'title':'Background while planner is scrolled'});sync()
    assert js(panel.page,'document.querySelector(".week").scrollLeft')==150
    print('PASS: background updates preserve the weekly planner scroll position',flush=True)
    assert not errors,errors
    print(json.dumps({'ok':True,'javascriptErrors':errors,'screenshots':str(folder)},ensure_ascii=False),flush=True)
finally:
    panel.close();overlay.hide();overlay.tray.hide()
    panel.deleteLater();overlay.deleteLater();app.sendPostedEvents(None,QEvent.DeferredDelete)
    profile.deleteLater();app.sendPostedEvents(None,QEvent.DeferredDelete)
