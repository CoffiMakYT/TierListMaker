"""Общие помощники рисования: вписывание картинки, скругления, цвета."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainterPath


def contrast_text(color) -> QColor:
    """Тёмный или светлый текст в зависимости от яркости фона."""
    c = QColor(color)
    if not c.isValid():
        return QColor("#ffffff")
    lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    return QColor("#15161a") if lum >= 150 else QColor("#ffffff")


def is_light(color) -> bool:
    c = QColor(color)
    if not c.isValid():
        return False
    lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    return lum >= 150


def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    r = min(radius, rect.width() / 2, rect.height() / 2)
    path.addRoundedRect(rect, r, r)
    return path


def draw_image(painter, image: QImage | None, rect: QRectF, fit: str) -> None:
    """Рисует изображение в rect без искажения пропорций.

    fit == "cover"   — заполнить область, лишнее обрезать;
    fit == "contain" — вписать целиком, свободные места остаются фоном.
    """
    if image is None or image.isNull() or rect.width() <= 0 or rect.height() <= 0:
        return

    iw, ih = image.width(), image.height()
    if iw <= 0 or ih <= 0:
        return

    if fit == "contain":
        scale = min(rect.width() / iw, rect.height() / ih)
        w, h = iw * scale, ih * scale
        target = QRectF(
            rect.x() + (rect.width() - w) / 2.0,
            rect.y() + (rect.height() - h) / 2.0,
            w,
            h,
        )
        painter.drawImage(target, image)
        return

    ta = rect.width() / rect.height()
    ia = iw / ih
    if ia > ta:
        sw, sh = ih * ta, ih
        sx, sy = (iw - sw) / 2.0, 0.0
    else:
        sw, sh = iw, iw / ta
        sx, sy = 0.0, (ih - sh) / 2.0
    painter.drawImage(rect, image, QRectF(sx, sy, sw, sh))


def fitted_font(text: str, max_width: float, start_px: int, min_px: int = 9, bold: bool = True) -> QFont:
    """Подбирает размер шрифта так, чтобы текст влез в max_width по одной строке."""
    font = QFont("Segoe UI")
    font.setBold(bold)
    px = int(start_px)
    while px > min_px:
        font.setPixelSize(px)
        if QFontMetrics(font).horizontalAdvance(text) <= max_width:
            break
        px -= 1
    font.setPixelSize(max(px, min_px))
    return font


def shade(color, factor: float) -> QColor:
    """Осветляет (factor > 1) или затемняет (factor < 1) цвет."""
    c = QColor(color)
    if not c.isValid():
        return QColor("#000000")
    if factor >= 1.0:
        return c.lighter(int(round(100 * factor)))
    return c.darker(int(round(100 / max(factor, 0.01))))


MIME_ITEM = "application/x-tierlist-item"
MIME_MARK = "text/x-tierlist-mark"

ALIGN_LEFT_V = Qt.AlignLeft | Qt.AlignVCenter