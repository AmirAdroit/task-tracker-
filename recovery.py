"""Private, verified restore points. Code rollback preserves current task data by default."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile

BASE = Path(__file__).resolve().parent
EXCLUDED = {'.git', '.venv', 'venv', 'env', 'data', '__pycache__', '.codex', '.agents'}
SUFFIXES = {'.py', '.js', '.cjs', '.html', '.css', '.md', '.txt', '.bat', '.vbs', '.wav', '.yml', '.yaml'}
SPECIAL_FILES = {'LICENSE', '.gitignore', '.gitattributes'}
MAX_BYTES = 128 * 1024 * 1024


def digest(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def code_path(root, name):
    if not isinstance(name, str):
        raise ValueError('Invalid restore-point path')
    path = PurePosixPath(name)
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {kind + str(i) for kind in ('COM', 'LPT') for i in range(1, 10)}
    if (not name or '\\' in name or ':' in name or path.is_absolute() or '..' in path.parts
            or any(part.casefold() in EXCLUDED or part.startswith('.') and part not in ('.github', '.gitignore', '.gitattributes')
                   or part.rstrip(' .') != part or part.split('.')[0].upper() in reserved
                   for part in path.parts) or path.as_posix() != name
            or (path.suffix.lower() not in SUFFIXES and name not in SPECIAL_FILES)):
        raise ValueError('Unsafe restore-point path: ' + name)
    target = (Path(root) / name).resolve()
    target.relative_to(Path(root).resolve())
    return target


def source_files(root):
    for directory, folders, files in os.walk(root):
        folders[:] = [name for name in folders if name.casefold() not in EXCLUDED
                      and (not name.startswith('.') or name == '.github')
                      and not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                continue
            if path.suffix.lower() in SUFFIXES or relative in SPECIAL_FILES:
                code_path(root, relative)
                yield relative, path


def create_restore_point(root=BASE, data_dir=None, label='Manual recovery copy'):
    root = Path(root).resolve()
    data_dir = Path(data_dir or root / 'data').resolve()
    # Always exclude an alternate/private data folder, even when it is nested in root.
    files = {name: path.read_bytes() for name, path in source_files(root)
             if not path.resolve().is_relative_to(data_dir)}
    data_file = data_dir / 'quests.json'
    raw = data_file.read_bytes() if data_file.exists() else None
    data_valid = True
    if raw is not None:
        try:
            validate_data(raw)
        except (ValueError, TypeError):
            data_valid = False  # Preserve corrupt originals too; never restore them as task data.
    if sum(map(len, files.values())) + len(raw or b'') > MAX_BYTES:
        raise ValueError('Restore point exceeds the size limit')
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root,
                                        stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    manifest = {'format': 1, 'created': datetime.now(timezone.utc).isoformat(),
                'gitCommit': commit, 'label': label, 'files': {name: digest(body) for name, body in files.items()},
                'data': digest(raw) if raw is not None else None, 'dataValid': data_valid}
    folder = data_dir / 'recovery'
    folder.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='restore-', suffix='.zip.tmp', dir=folder)
    os.close(fd)
    target = folder / (Path(temporary).name.removesuffix('.tmp'))
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, body in files.items():
                archive.writestr('code/' + name, body)
            if raw is not None:
                archive.writestr('save/quests.json', raw)
            archive.writestr('manifest.json', json.dumps(manifest, indent=2))
        verify_restore_point(temporary, root)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def validate_data(raw):
    state = json.loads(raw)
    if (not isinstance(state, dict) or not isinstance(state.get('quests'), list)
            or not isinstance(state.get('completed'), list) or type(state.get('version', 0)) is not int
            or state.get('version', 0) > 4):
        raise ValueError('Invalid or newer task data in restore point')


def verify_restore_point(filename, root=BASE):
    with zipfile.ZipFile(filename) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) > 2000 or len(names) != len(set(names)) or sum(entry.file_size for entry in entries) > MAX_BYTES:
            raise ValueError('Duplicate entries or oversized restore point')
        manifest = json.loads(archive.read('manifest.json'))
        if not isinstance(manifest, dict) or manifest.get('format') != 1 or not isinstance(manifest.get('files'), dict) or not manifest['files']:
            raise ValueError('Unsupported or empty restore point')
        expected = {'manifest.json'}
        for name, metadata in manifest['files'].items():
            code_path(root, name)
            entry = 'code/' + name
            expected.add(entry)
            if digest(archive.read(entry)) != metadata:
                raise ValueError('Checksum mismatch: ' + name)
        if manifest.get('data') is not None:
            expected.add('save/quests.json')
            raw = archive.read('save/quests.json')
            if digest(raw) != manifest['data']:
                raise ValueError('Task-data checksum mismatch')
            if manifest.get('dataValid', True):
                validate_data(raw)
        if set(names) != expected:
            raise ValueError('Unexpected files in restore point')
        return manifest


@contextmanager
def stopped_installation(data_dir):
    """Claim the same IPC lock as old/current QuestHUD before replacing any files."""
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    application = QCoreApplication.instance() or QCoreApplication([])
    identity = 'questhud-' + hashlib.sha256(os.path.abspath(data_dir).lower().encode()).hexdigest()[:20]
    socket = QLocalSocket()
    socket.connectToServer(identity)
    if socket.waitForConnected(400):
        socket.disconnectFromServer()
        raise RuntimeError('QuestHUD is running. Quit from its tray menu before restoring.')
    server = QLocalServer()
    if not server.listen(identity):
        raise RuntimeError('Cannot acquire the installation lock. No files were restored.')
    try:
        yield
    finally:
        server.close()
        # Keep the QCoreApplication alive throughout the operation.
        assert application is not None


def atomic_write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='restore-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restore(filename, root=BASE, data_dir=None, include_data=False):
    root = Path(root).resolve()
    data_dir = Path(data_dir or root / 'data').resolve()
    manifest = verify_restore_point(filename, root)
    with stopped_installation(data_dir):
        safety = create_restore_point(root, data_dir, 'Before rollback')
        with zipfile.ZipFile(filename) as archive:
            changes = {code_path(root, name): archive.read('code/' + name) for name in manifest['files']}
            if include_data:
                if manifest.get('data') is None:
                    raise ValueError('This restore point contains no task data')
                raw = archive.read('save/quests.json')
                validate_data(raw)
                changes[data_dir / 'quests.json'] = raw
        previous = {path: path.read_bytes() if path.exists() else None for path in changes}
        marker = data_dir / 'recovery-in-progress.json'
        atomic_write(marker, json.dumps({'restorePoint': str(Path(filename).resolve()), 'safetyCopy': str(safety)}).encode())
        written = []
        try:
            for path, raw in changes.items():
                atomic_write(path, raw)
                written.append(path)
        except Exception:
            for path in reversed(written):
                if previous[path] is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, previous[path])
            marker.unlink(missing_ok=True)
            raise
        marker.unlink(missing_ok=True)
        return safety


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('create', 'verify', 'list', 'restore'))
    parser.add_argument('archive', nargs='?')
    parser.add_argument('--root', type=Path, default=BASE)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--include-data', action='store_true', help='Explicitly restore old task data too; default is code only')
    args = parser.parse_args()
    data_dir = args.data_dir or Path(os.environ.get('QUESTHUD_DATA_DIR', args.root / 'data'))
    try:
        if args.action == 'create':
            print(create_restore_point(args.root, data_dir))
        elif args.action == 'list':
            for path in sorted((data_dir / 'recovery').glob('*.zip')):
                manifest = verify_restore_point(path, args.root)
                print(path.name, manifest.get('created'), manifest.get('label'), manifest.get('gitCommit'))
        elif not args.archive:
            parser.error('archive is required for verify/restore')
        elif args.action == 'verify':
            print(json.dumps(verify_restore_point(args.archive, args.root), indent=2))
        else:
            print('Restored. Pre-rollback safety copy:', restore(args.archive, args.root, data_dir, args.include_data))
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
