"""Область с карточками: автоматический перенос строк, приём drag & drop."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import theme
from .card import Card, card_size
from .imagestore import ImageStore, file_ext
from .model import SUPPORTED_EXTS
from .painting import MIME_ITEM

GAP = 8


class FlowArea(QWidget):
    """Виджет-«поток»: карточки идут слева направо и переносятся на новую строку.

    Сигналы:
      itemsDropped(list ids, int index) — перетащили карточки (в т.ч. из другой области);
      filesDropped(list paths, int index) — перетащили файлы из Проводника;
      contextAction(str, str) — действие из контекстного меню карточки.
    """

    itemsDropped = Signal(list, int)
    filesDropped = Signal(list, int)
    contextAction = Signal(str, str)

    def __init__(self, parent: QWidget | None = None, empty_height: int = 110, hint: str = "") -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self._cards: list[Card] = []
        self._indicator: QRect | None = None
        self._empty_height = empty_height
        self._hint = hint
        self._busy = False
        self.setMinimumHeight(empty_height)

    # ------------------------------------------------------------------ содержимое
    def set_items(
        self,
        items: list[tuple[str, str, bool]],
        store: ImageStore,
        aspect: str,
        fit: str,
    ) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        for item_id, name, in_tier in items:
            card = Card(item_id, name, store, aspect, fit, in_tier, self)
            card.contextAction.connect(self.contextAction)
            card.show()
            self._cards.append(card)
        self._relayout(invalidate=True)

    def append_items(
        self,
        items: list[tuple[str, str, bool]],
        store: ImageStore,
        aspect: str,
        fit: str,
    ) -> None:
        """Добавить карточки без пересоздания уже показанных."""
        if not items:
            return
        for item_id, name, in_tier in items:
            card = Card(item_id, name, store, aspect, fit, in_tier, self)
            card.contextAction.connect(self.contextAction)
            card.show()
            self._cards.append(card)
        self._relayout(invalidate=True)

    def card_count(self) -> int:
        return len(self._cards)

    def set_hint(self, text: str) -> None:
        self._hint = text
        self.update()

    # ------------------------------------------------------------------ раскладка
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout(invalidate=True)

    def _relayout(self, invalidate: bool = False) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            width = max(self.width(), 1)
            x = y = row_height = 0
            for card in self._cards:
                cw, ch = card.width(), card.height()
                if x > 0 and x + cw > width:
                    x = 0
                    y += row_height + GAP
                    row_height = 0
                card.move(x, y)
                x += cw + GAP
                row_height = max(row_height, ch)

            if self._cards:
                height = y + row_height
            else:
                height = self._empty_height
            height = max(height, self._empty_height)
            if self.height() != height or self.minimumHeight() != height:
                self.setFixedHeight(height)
            if invalidate:
                self.update()
        finally:
            self._busy = False

    # ------------------------------------------------------------------ помощники
    def _rows(self) -> list[tuple[int, list[int]]]:
        rows: list[tuple[int, list[int]]] = []
        for index, card in enumerate(self._cards):
            top = card.geometry().top()
            if rows and abs(top - rows[-1][0]) <= 2:
                rows[-1][1].append(index)
            else:
                rows.append((top, [index]))
        return rows

    def _index_at(self, pos: QPoint) -> int:
        rows = self._rows()
        if not rows:
            return 0
        for top, indexes in rows:
            first = self._cards[indexes[0]].geometry()
            if pos.y() < first.top() + first.height():
                for index in indexes:
                    geometry = self._cards[index].geometry()
                    if pos.x() < geometry.center().x():
                        return index
                return indexes[-1] + 1
        return len(self._cards)

    def _indicator_geometry(self, index: int) -> QRect:
        if not self._cards:
            return QRect(2, 4, 3, max(self.height() - 8, 24))
        if index >= len(self._cards):
            geometry = self._cards[-1].geometry()
            return QRect(geometry.right() + 2, geometry.top(), 3, geometry.height())
        geometry = self._cards[max(index, 0)].geometry()
        return QRect(max(geometry.left() - 4, 0), geometry.top(), 3, geometry.height())

    def _set_indicator(self, index: int | None) -> None:
        new_rect = None if index is None else self._indicator_geometry(index)
        if new_rect != self._indicator:
            self._indicator = new_rect
            self.update()

    # ------------------------------------------------------------------ отрисовка
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if not self._cards and self._hint:
            painter.setPen(QColor(theme.C["text_dim"]))
            font = painter.font()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(
                QRectF(0, 0, self.width(), self.height()),
                Qt.AlignCenter,
                self._hint,
            )

        if self._indicator is not None:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.C["drop"]))
            painter.drawRoundedRect(QRectF(self._indicator), 2, 2)

    # ------------------------------------------------------------------ drag & drop
    def _has_our_items(self, mime) -> bool:
        return mime is not None and mime.hasFormat(MIME_ITEM)

    def _local_files(self, mime) -> list[str]:
        if mime is None or not mime.hasUrls():
            return []
        paths = []
        for url in mime.urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if file_ext(path) in SUPPORTED_EXTS:
                    paths.append(path)
        return paths

    def dragEnterEvent(self, event) -> None:
        mime = event.mimeData()
        if self._has_our_items(mime) or self._local_files(mime):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        mime = event.mimeData()
        if not (self._has_our_items(mime) or self._local_files(mime)):
            event.ignore()
            return
        self._set_indicator(self._index_at(event.position().toPoint()))
        event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self._set_indicator(None)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        index = self._index_at(event.position().toPoint())
        self._set_indicator(None)

        if self._has_our_items(mime):
            raw = bytes(mime.data(MIME_ITEM)).decode("utf-8")
            ids = [i for i in raw.split("\n") if i]
            if ids:
                event.acceptProposedAction()
                self.itemsDropped.emit(ids, index)
                return
        files = self._local_files(mime)
        if files:
            event.acceptProposedAction()
            self.filesDropped.emit(files, index)
            return
        event.ignore()