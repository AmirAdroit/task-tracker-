"""Roll code back in an isolated installation, launch it, then undo the rollback."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QCoreApplication
from state_service import StateService
import recovery

parser = argparse.ArgumentParser()
parser.add_argument('--baseline', default='HEAD')
parser.add_argument('--working-tree', action='store_true')
options = parser.parse_args()
app = QCoreApplication.instance() or QCoreApplication([])
folder = ROOT / 'data' / 'rollback-drill'
folder.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory(dir=folder) as temporary:
    installation = Path(temporary).resolve()
    assert installation.is_relative_to(folder.resolve())
    if options.working_tree:
        for name, source in recovery.source_files(ROOT):
            target = recovery.code_path(installation, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    else:
        bundle = subprocess.check_output(['git', 'archive', '--format=zip', options.baseline], cwd=ROOT)
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                target = recovery.code_path(installation, entry.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(entry))
    data = installation / 'data'
    service = StateService(data / 'quests.json', host_integration=False)
    point = recovery.create_restore_point(installation, data, 'Rollback drill baseline')
    code_before = (installation / 'hud.py').read_bytes()
    (installation / 'hud.py').write_bytes(code_before + b'\n# Synthetic deployment marker\n')
    result = service.dispatch({'type': 'task.add', 'payload': {'title': 'New work retained after rollback'}})
    assert result['ok'], result
    task = result['state']['quests'][-1]['id']
    result = service.dispatch({'type': 'task.complete', 'payload': {'id': task}})
    assert result['ok'], result
    newer = (data / 'quests.json').read_bytes()
    state_before = json.loads(newer)
    safety = recovery.restore(point, installation, data)
    assert (installation / 'hud.py').read_bytes() == code_before
    assert (data / 'quests.json').read_bytes() == newer
    print('PASS: isolated previous code restored; newer work and rewards remain byte-exact', flush=True)
    child = '''import hud
print('Native app module imported', flush=True)
hud.QSettings.setDefaultFormat(hud.QSettings.IniFormat)
hud.QSettings.setPath(hud.QSettings.IniFormat, hud.QSettings.UserScope, hud.os.path.join(hud.DATA, 'test-settings'))
class SmokeApp(hud.QApplication):
    def __init__(self, *args):
        super().__init__(*args)
        print('Native application created', flush=True)
        hud.QTimer.singleShot(1600, self.finish)
    def finish(self):
        if not hasattr(hud, 'release_webengine'):
            # The old version lacks orderly native teardown. The harness owns
            # cleanup for that launch-only compatibility check.
            profile, bridge, overlay, holder, service, timer, server, alert = self._questhud
            timer.stop()
            self.aboutToQuit.disconnect(overlay.save_geometry)
            for window in (holder['panel'], overlay, alert.window):
                if window is not None:
                    window.hide()
                    if hasattr(window, 'tray'): window.tray.hide()
                    window.deleteLater()
            self.sendPostedEvents(None, hud.QEvent.DeferredDelete)
            profile.deleteLater()
            self.sendPostedEvents(None, hud.QEvent.DeferredDelete)
        self.quit()
hud.QApplication = SmokeApp
hud.main()
'''
    env = dict(os.environ, QUESTHUD_DATA_DIR=str(data), QUESTHUD_RENDERER='software')
    process = subprocess.run([sys.executable, '-X', 'utf8', '-X', 'faulthandler', '-u', '-B', '-c', child], cwd=installation,
                             env=env, capture_output=True, text=True, timeout=35)
    assert process.returncode == 0, (process.returncode, process.stdout, process.stderr)
    reopened = json.loads((data / 'quests.json').read_text(encoding='utf-8'))
    for key in ('gold', 'xp', 'level', 'completed'):
        assert reopened[key] == state_before[key], key
    assert any(q['id'] == task for q in reopened['quests'])
    print('PASS: rolled-back native application launches and preserves completed work/rewards', flush=True)
    current_data = (data / 'quests.json').read_bytes()
    recovery.restore(safety, installation, data)
    assert (installation / 'hud.py').read_bytes().endswith(b'# Synthetic deployment marker\n')
    assert (data / 'quests.json').read_bytes() == current_data
    print('PASS: undoing the code rollback also preserves current task data', flush=True)
    if options.working_tree or 'release_webengine' in (installation / 'hud.py').read_text(encoding='utf-8'):
        marker = data / 'recovery-in-progress.json'
        marker.write_text(json.dumps({'restorePoint': str(point), 'safetyCopy': str(safety)}), encoding='utf-8')
        blocked_child = '''import hud
hud.QMessageBox.critical = lambda *args: print('RECOVERY_BLOCKED_STARTUP', flush=True)
hud.main()
'''
        blocked = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', blocked_child], cwd=installation,
                                 env=env, capture_output=True, text=True, timeout=20)
        assert blocked.returncode == 0 and 'RECOVERY_BLOCKED_STARTUP' in blocked.stdout, (blocked.returncode, blocked.stderr)
        assert (data / 'quests.json').read_bytes() == current_data
        marker.unlink()
        print('PASS: interrupted recovery blocks native startup without changing task data', flush=True)
print(json.dumps({'ok': True, 'baseline': 'working-tree' if options.working_tree else options.baseline, 'personalDataUsed': False}), flush=True)
