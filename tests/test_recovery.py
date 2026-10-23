import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PySide6.QtCore import QCoreApplication
import recovery

app = QCoreApplication.instance() or QCoreApplication([])


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        test_root = recovery.BASE / 'data' / 'recovery-tests'
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        assert Path(self.temp.name).resolve().is_relative_to(test_root.resolve())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'
        self.data.mkdir()
        (self.root / 'hud.py').write_bytes(b'old application\n')
        (self.root / 'panel.html').write_bytes('متن آزمایشی\n'.encode())
        self.original = json.dumps({'version': 4, 'quests': [], 'completed': [], 'gold': 10}, indent=2).encode()
        self.newer = json.dumps({'version': 4, 'quests': [{'title': 'New work'}], 'completed': [], 'gold': 99}).encode()
        (self.data / 'quests.json').write_bytes(self.original)

    def create(self):
        return recovery.create_restore_point(self.root, self.data)

    def rewrite(self, source, mutate):
        with zipfile.ZipFile(source) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        mutate(entries)
        target = self.data / 'tampered.zip'
        with zipfile.ZipFile(target, 'w') as archive:
            for name, raw in entries.items():
                archive.writestr(name, raw)
        return target

    def test_verified_copy_is_byte_exact_and_excludes_private_folders(self):
        (self.data / 'secret.txt').write_text('private')
        (self.root / '.venv').mkdir()
        (self.root / '.venv' / 'secret.py').write_text('private')
        archive = self.create()
        manifest = recovery.verify_restore_point(archive, self.root)
        self.assertEqual(manifest['data']['sha256'], hashlib.sha256(self.original).hexdigest())
        with zipfile.ZipFile(archive) as copy:
            self.assertEqual(copy.read('save/quests.json'), self.original)
            self.assertNotIn('code/data/secret.txt', copy.namelist())
            self.assertNotIn('code/.venv/secret.py', copy.namelist())

    def test_code_rollback_keeps_newer_work_and_makes_its_own_safety_copy(self):
        archive = self.create()
        (self.root / 'hud.py').write_bytes(b'new code')
        (self.data / 'quests.json').write_bytes(self.newer)
        safety = recovery.restore(archive, self.root, self.data)
        self.assertEqual((self.root / 'hud.py').read_bytes(), b'old application\n')
        self.assertEqual((self.data / 'quests.json').read_bytes(), self.newer)
        with zipfile.ZipFile(safety) as copy:
            self.assertEqual(copy.read('code/hud.py'), b'new code')
            self.assertEqual(copy.read('save/quests.json'), self.newer)
        self.assertFalse((self.data / 'recovery-in-progress.json').exists())

    def test_data_recovery_is_explicit_and_preserves_pre_restore_data(self):
        archive = self.create()
        (self.data / 'quests.json').write_bytes(self.newer)
        safety = recovery.restore(archive, self.root, self.data, include_data=True)
        self.assertEqual((self.data / 'quests.json').read_bytes(), self.original)
        with zipfile.ZipFile(safety) as copy:
            self.assertEqual(copy.read('save/quests.json'), self.newer)

    def test_running_installation_blocks_rollback_before_any_writes(self):
        archive = self.create()
        (self.root / 'hud.py').write_bytes(b'new code')
        before = list((self.data / 'recovery').iterdir())
        with recovery.stopped_installation(self.data):
            with self.assertRaisesRegex(RuntimeError, 'running'):
                recovery.restore(archive, self.root, self.data)
        self.assertEqual((self.root / 'hud.py').read_bytes(), b'new code')
        self.assertEqual(list((self.data / 'recovery').iterdir()), before)

    def test_checksum_tampering_is_rejected_before_writes(self):
        archive = self.rewrite(self.create(), lambda entries: entries.update({'code/hud.py': b'tampered'}))
        with self.assertRaisesRegex(ValueError, 'Checksum'):
            recovery.restore(archive, self.root, self.data)
        self.assertEqual((self.root / 'hud.py').read_bytes(), b'old application\n')

    def test_traversal_private_folders_and_windows_device_paths_are_rejected(self):
        for name in ('../outside.py', '/outside.py', 'C:/outside.py', 'data/quests.py', '.git/hooks/x.py',
                     '.venv/site.py', 'NUL.py', 'folder./x.py', 'folder\\x.py'):
            with self.subTest(name=name), self.assertRaises((ValueError, OSError)):
                recovery.code_path(self.root, name)

    def test_unlisted_zip_entries_are_rejected(self):
        archive = self.rewrite(self.create(), lambda entries: entries.update({'unlisted.py': b'bad'}))
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            recovery.verify_restore_point(archive, self.root)

    def test_injected_write_failure_rolls_back_changed_files(self):
        archive = self.create()
        (self.root / 'hud.py').write_bytes(b'new code')
        (self.root / 'panel.html').write_bytes(b'new panel')
        write = recovery.atomic_write
        failed = [False]

        def fail_once(path, raw):
            if path.name == 'panel.html' and not failed[0]:
                failed[0] = True
                raise OSError('injected disk failure')
            return write(path, raw)

        with patch.object(recovery, 'atomic_write', side_effect=fail_once), self.assertRaises(OSError):
            recovery.restore(archive, self.root, self.data)
        self.assertTrue(failed[0])
        self.assertEqual((self.root / 'hud.py').read_bytes(), b'new code')
        self.assertEqual((self.root / 'panel.html').read_bytes(), b'new panel')
        self.assertEqual((self.data / 'quests.json').read_bytes(), self.original)
        self.assertFalse((self.data / 'recovery-in-progress.json').exists())

    def test_corrupt_current_data_is_preserved_when_restoring_a_valid_copy(self):
        archive = self.create()
        (self.data / 'quests.json').write_bytes(b'{broken save')
        safety = recovery.restore(archive, self.root, self.data, include_data=True)
        self.assertFalse(recovery.verify_restore_point(safety, self.root)['dataValid'])
        with zipfile.ZipFile(safety) as copy:
            self.assertEqual(copy.read('save/quests.json'), b'{broken save')
        self.assertEqual((self.data / 'quests.json').read_bytes(), self.original)
        with self.assertRaises(ValueError):
            recovery.restore(safety, self.root, self.data, include_data=True)
        self.assertEqual((self.data / 'quests.json').read_bytes(), self.original)

    def test_bad_or_unsupported_archive_is_rejected(self):
        target = self.data / 'bad.zip'
        target.write_bytes(b'not a zip file')
        with self.assertRaises(zipfile.BadZipFile):
            recovery.verify_restore_point(target, self.root)
        archive = self.rewrite(self.create(), lambda entries: entries.update({'manifest.json': b'{"format":99}'}))
        with self.assertRaises(ValueError):
            recovery.verify_restore_point(archive, self.root)
