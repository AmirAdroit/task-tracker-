"""Geometry-only tests run without a GUI or physical monitor dependency."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QRect, QSize, Qt
from window_geometry import fit_rect, best_screen, resize_regions


class Screen:
    def __init__(self, rect): self.rect = rect
    def availableGeometry(self): return self.rect


class GeometryTests(unittest.TestCase):
    def test_fits_oversized_window_and_keeps_header_inside_work_area(self):
        work = QRect(2560, 0, 1920, 1032)
        rect = fit_rect(QRect(2492, -200, 1013, 1890), work)
        self.assertTrue(work.contains(rect))
        self.assertEqual(rect.height(), 1016)

    def test_negative_origins_and_taskbar_offsets(self):
        work = QRect(-1920, 40, 1920, 1000)
        rect = fit_rect(QRect(0, -100, 300, 560), work)
        self.assertTrue(work.contains(rect))
        self.assertEqual(rect.top(), 48)

    def test_removed_monitor_recovers_to_fallback(self):
        primary = Screen(QRect(0, 0, 1707, 912))
        self.assertIs(best_screen(QRect(2700, 100, 300, 560), [primary], primary), primary)

    def test_gap_between_mixed_dpi_displays_is_not_treated_as_a_screen(self):
        primary, second = Screen(QRect(0, 0, 1707, 912)), Screen(QRect(2560, 0, 1920, 1032))
        self.assertIs(best_screen(QRect(2400, 100, 450, 560), [primary, second], primary), second)

    def test_minimum_adapts_to_smaller_available_work_area(self):
        work = QRect(100, 100, 200, 200)
        rect = fit_rect(QRect(0, 0, 10, 10), work, QSize(240, 320))
        self.assertTrue(work.contains(rect))

    def test_all_four_edges_and_four_corners_are_resizable(self):
        regions = resize_regions(300, 560)
        self.assertEqual(len(regions), 8)
        self.assertEqual(len(set(int(edges.value) for edges, _, _ in regions)), 8)
        self.assertTrue(any(edges == Qt.TopEdge for edges, _, _ in regions))
        self.assertTrue(any(edges == Qt.LeftEdge for edges, _, _ in regions))
        self.assertTrue(all(QRect(0, 0, 300, 560).contains(rect) for _, rect, _ in regions))


if __name__ == '__main__': unittest.main()
