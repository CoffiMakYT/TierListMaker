"""Карточка изображения с поддержкой перетаскивания."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from . import theme
from .imagestore import ImageStore
from .model import ASPECTS
from .painting import MIME_ITEM, draw_image, rounded_path

CARD_HEIGHT = 104
RADIUS = 7


def card_width(aspect: str) -> int:
    return max(30, int(round(CARD_HEIGHT * ASPECTS.get(aspect, 0.75))))


def card_size(aspect: str) -> tuple[int, int]:
    return card_width(aspect), CARD_HEIGHT


class Card(QWidget):
    """Миниатюра изображения. Тянется мышью, имеет контекстное меню."""

    contextAction = Signal(str, str)

    def __init__(
        self,
        item_id: str,
        name: str,
        store: ImageStore,
        aspect: str = "3:4",
        fit: str = "cover",
        in_tier: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self.store = store
        self.aspect = aspect
        self.fit = fit
        self.in_tier = in_tier
        self._press: QPoint | None = None
        self._hover = False

        self.setFixedSize(*card_size(aspect))
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip(name)
        self.setAttribute(Qt.WA_Hover, True)

    # ------------------------------------------------------------------ вид
    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = rounded_path(rect, RADIUS)
        painter.setClipPath(path)
        painter.fillRect(self.rect(), QColor(theme.C["card_hover" if self._hover else "card"]))

        image = self.store.preview(self.item_id)
        if image is not None:
            draw_image(painter, image, rect, self.fit)

        painter.setClipping(False)
        pen_color = QColor(theme.C["accent"] if self._hover else theme.C["border"])
        painter.setPen(QPen(pen_color, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    # ------------------------------------------------------------------ мышь
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._press = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press = None
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._press is None or not (event.buttons() & Qt.LeftButton):
            return
        distance = (event.position().toPoint() - self._press).manhattanLength()
        if distance < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_ITEM, self.item_id.encode("utf-8"))
        mime.setText(self.toolTip())
        drag.setMimeData(mime)

        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(self._press)
        self._press = None
        self.setCursor(Qt.OpenHandCursor)
        drag.exec(Qt.MoveAction)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        act_pool = menu.addAction("Убрать в нераспределённые")
        act_pool.setEnabled(self.in_tier)
        menu.addSeparator()
        act_delete = menu.addAction("Удалить изображение")
        chosen = menu.exec(event.globalPos())
        if chosen is act_pool:
            self.contextAction.emit(self.item_id, "pool")
        elif chosen is act_delete:
            self.contextAction.emit(self.item_id, "delete")