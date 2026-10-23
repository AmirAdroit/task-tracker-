import unittest
from rendering import configure_rendering


class RenderingTests(unittest.TestCase):
    def test_stable_default_uses_software_and_full_frames_without_disabling_sandbox(self):
        env = {}
        self.assertEqual(configure_rendering([], env), 'software')
        self.assertEqual(env['QT_QUICK_BACKEND'], 'software')
        self.assertEqual(env['QSG_SOFTWARE_RENDERER_FORCE_PARTIAL_UPDATES'], '0')
        self.assertIn('--disable-gpu', env['QTWEBENGINE_CHROMIUM_FLAGS'].split())
        self.assertNotIn('--no-sandbox', env['QTWEBENGINE_CHROMIUM_FLAGS'].split())

    def test_configuration_is_idempotent_and_keeps_other_flags(self):
        env = {'QTWEBENGINE_CHROMIUM_FLAGS': '--enable-logging'}
        configure_rendering([], env); first = dict(env)
        configure_rendering([], env)
        self.assertEqual(env, first)
        self.assertIn('--enable-logging', env['QTWEBENGINE_CHROMIUM_FLAGS'])

    def test_auto_override_is_explicit_and_does_not_force_a_backend(self):
        env = {'QUESTHUD_RENDERER': 'software'}
        self.assertEqual(configure_rendering(['--renderer', 'auto'], env), 'auto')
        self.assertNotIn('QT_QUICK_BACKEND', env)
        self.assertNotIn('--disable-gpu', env['QTWEBENGINE_CHROMIUM_FLAGS'])

    def test_bad_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            configure_rendering([], {'QUESTHUD_RENDERER': 'typo'})
