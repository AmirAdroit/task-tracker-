"""Configure the renderer before importing Qt WebEngine; no task-state settings."""
from __future__ import annotations

import argparse
import os


def configure_rendering(argv=(), environ=None):
    env = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--renderer', choices=('software', 'auto'))
    options, _ = parser.parse_known_args(argv)
    mode = options.renderer or env.get('QUESTHUD_RENDERER', 'software')
    if mode not in ('software', 'auto'):
        raise ValueError('QUESTHUD_RENDERER must be software or auto')
    flags = env.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
    if '--enable-transparent-visuals' not in flags.split():
        flags += ' --enable-transparent-visuals'
    if mode == 'software':
        # Keep Chromium sandboxing enabled. Use software for both Chromium and
        # Qt's scene graph, avoiding shared GPU textures in the Windows panel.
        for switch in ('--disable-gpu', '--disable-gpu-compositing'):
            if switch not in flags.split():
                flags += ' ' + switch
        env['QT_QUICK_BACKEND'] = 'software'
        # Full-frame raster updates avoid fractional-DPI stale/overlapping tiles.
        env['QSG_SOFTWARE_RENDERER_FORCE_PARTIAL_UPDATES'] = '0'
    env['QTWEBENGINE_CHROMIUM_FLAGS'] = flags.strip()
    return mode
