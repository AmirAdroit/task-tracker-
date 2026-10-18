"""Logical-pixel geometry; never multiply QWidget coordinates by a monitor's DPR."""
from PySide6.QtCore import QRect, QSize, Qt

RESIZE_BORDER = 6
RESIZE_CORNER = 14
HUD_MINIMUM = QSize(240, 320)
HUD_DEFAULT = QSize(300, 560)


def fit_rect(rect, available, minimum=HUD_MINIMUM, margin=8):
    """Fit one real work area, including negative origins and gaps between displays."""
    bounds = available.adjusted(margin, margin, -margin, -margin)
    if bounds.width() < 1 or bounds.height() < 1:
        bounds = QRect(available)
    width = min(max(rect.width(), minimum.width()), bounds.width())
    height = min(max(rect.height(), minimum.height()), bounds.height())
    x = min(max(rect.x(), bounds.left()), bounds.right() - width + 1)
    y = min(max(rect.y(), bounds.top()), bounds.bottom() - height + 1)
    return QRect(x, y, width, height)


def best_screen(rect, screens, fallback=None):
    """Windows' logical desktop can contain gaps; do not assume adjacent coordinates."""
    for screen in screens:
        if screen.availableGeometry().contains(rect.center()):
            return screen
    ranked = sorted(screens, key=lambda s: intersection_area(rect, s.availableGeometry()), reverse=True)
    if ranked and intersection_area(rect, ranked[0].availableGeometry()):
        return ranked[0]
    return fallback or (screens[0] if screens else None)


def intersection_area(a, b):
    overlap = a.intersected(b)
    return max(0, overlap.width()) * max(0, overlap.height())


def resize_regions(width, height, border=RESIZE_BORDER, corner=RESIZE_CORNER):
    """Eight non-overlapping hit regions outside the embedded web view."""
    return [
        (Qt.LeftEdge | Qt.TopEdge, QRect(0, 0, corner, corner), Qt.SizeFDiagCursor),
        (Qt.TopEdge, QRect(corner, 0, max(0, width - 2 * corner), border), Qt.SizeVerCursor),
        (Qt.RightEdge | Qt.TopEdge, QRect(width - corner, 0, corner, corner), Qt.SizeBDiagCursor),
        (Qt.RightEdge, QRect(width - border, corner, border, max(0, height - 2 * corner)), Qt.SizeHorCursor),
        (Qt.RightEdge | Qt.BottomEdge, QRect(width - corner, height - corner, corner, corner), Qt.SizeFDiagCursor),
        (Qt.BottomEdge, QRect(corner, height - border, max(0, width - 2 * corner), border), Qt.SizeVerCursor),
        (Qt.LeftEdge | Qt.BottomEdge, QRect(0, height - corner, corner, corner), Qt.SizeBDiagCursor),
        (Qt.LeftEdge, QRect(0, corner, border, max(0, height - 2 * corner)), Qt.SizeHorCursor),
    ]
