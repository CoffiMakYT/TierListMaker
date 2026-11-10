"""Строка уровня: цветной бейдж + перетаскиваемые карточки + служебные кнопки."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from . import i18n
from .flow import FlowArea
from .imagestore import ImageStore
from .model import Tier
from .painting import contrast_text, fitted_font, rounded_path

BADGE_WIDTH = 92
BADGE_RADIUS = 8


class TierBadge(QWidget):
    """Цветная плашка с названием уровня. Клик — цвет, двойной клик — название."""

    clicked = Signal()
    doubleClicked = Signal()

    def __init__(self, label: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._color = color
        self.setFixedWidth(BADGE_WIDTH)
        self.setMinimumHeight(56)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(i18n.tr("badge_tip"))

    def set_data(self, label: str, color: str) -> None:
        self._label = label
        self._color = color
        self.update()

    def sizeHint(self):
        from PySide6.QtCore import QSize

        return QSize(BADGE_WIDTH, 64)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawPath(rounded_path(rect, BADGE_RADIUS))

        text = self._label.strip() or "?"
        painter.setPen(contrast_text(self._color))
        painter.setFont(fitted_font(text, self.width() - 22, 26, 10, bold=True))
        painter.drawText(rect, Qt.AlignCenter, text)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        elif event.button() == Qt.RightButton:
            self.doubleClicked.emit()
        super().mouseReleaseEvent(event)


class TierRow(QWidget):
    renameRequested = Signal(str)
    colorRequested = Signal(str)
    moveRequested = Signal(str, int)
    deleteRequested = Signal(str)
    itemsDropped = Signal(list, int)
    filesDropped = Signal(list, int)
    contextAction = Signal(str, str)

    def __init__(
        self,
        tier: Tier,
        items: list[tuple[str, str, bool]],
        store: ImageStore,
        aspect: str,
        fit: str,
        can_up: bool,
        can_down: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tier_id = tier.id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.badge = TierBadge(tier.label, tier.color, self)
        self.badge.clicked.connect(lambda: self.colorRequested.emit(self.tier_id))
        self.badge.doubleClicked.connect(lambda: self.renameRequested.emit(self.tier_id))
        layout.addWidget(self.badge)

        self.flow = FlowArea(self, empty_height=104, hint=i18n.tr("row_drop"))
        self.flow.set_items(items, store, aspect, fit)
        self.flow.itemsDropped.connect(self.itemsDropped)
        self.flow.filesDropped.connect(self.filesDropped)
        self.flow.contextAction.connect(self.contextAction)
        layout.addWidget(self.flow, 1)

        buttons = QVBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(2)
        self.btn_up = self._small_button("↑", i18n.tr("move_up"))
        self.btn_down = self._small_button("↓", i18n.tr("move_down"))
        self.btn_del = self._small_button("✕", i18n.tr("delete_tier"))
        self.btn_up.setEnabled(can_up)
        self.btn_down.setEnabled(can_down)
        self.btn_up.clicked.connect(lambda: self.moveRequested.emit(self.tier_id, -1))
        self.btn_down.clicked.connect(lambda: self.moveRequested.emit(self.tier_id, 1))
        self.btn_del.clicked.connect(lambda: self.deleteRequested.emit(self.tier_id))
        for button in (self.btn_up, self.btn_down, self.btn_del):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def _small_button(self, text: str, tip: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName("Ghost")
        button.setFixedSize(22, 22)
        button.setToolTip(tip)
        button.setCursor(Qt.PointingHandCursor)
        return button
