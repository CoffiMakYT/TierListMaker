"""Хранилище изображений: исходные байты + декодированные QImage с кэшем."""

from __future__ import annotations

import os

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage, QImageReader


def decode_image(data: bytes) -> QImage | None:
    """Декодирует PNG/JPG/WEBP с учётом EXIF-ориентации."""
    if not data:
        return None
    buf = QBuffer()
    buf.setData(QByteArray(data))
    if not buf.open(QIODevice.ReadOnly):
        return None
    reader = QImageReader(buf)
    reader.setAutoTransform(True)
    image = reader.read()
    buf.close()
    if image.isNull():
        return None
    return image


class ImageStore:
    """Держит оригиналы всех картинок проекта в памяти.

    * ``data(id)`` — исходные байты (ровно то, что было в файле);
    * ``image(id)`` — полное декодированное изображение (для экспорта);
    * ``preview(id)`` — уменьшенная копия для быстрой отрисовки в интерфейсе.
    """

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}
        self._images: dict[str, QImage] = {}
        self._previews: dict[str, QImage] = {}

    # ------------------------------------------------------------------ добавление
    def add_bytes(self, item_id: str, data: bytes) -> bool:
        image = decode_image(data)
        if image is None:
            return False
        self.remove(item_id)
        self._data[item_id] = bytes(data)
        self._images[item_id] = image
        return True

    def add_file(self, item_id: str, path: str) -> bool:
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            return False
        return self.add_bytes(item_id, data)

    # ------------------------------------------------------------------ доступ
    def has(self, item_id: str) -> bool:
        return item_id in self._data

    def data(self, item_id: str) -> bytes | None:
        return self._data.get(item_id)

    def image(self, item_id: str) -> QImage | None:
        if item_id in self._images:
            return self._images[item_id]
        data = self._data.get(item_id)
        if data is None:
            return None
        image = decode_image(data)
        if image is not None:
            self._images[item_id] = image
        return image

    def preview(self, item_id: str, max_side: int = 420) -> QImage | None:
        cached = self._previews.get(item_id)
        if cached is not None:
            return cached
        image = self.image(item_id)
        if image is None:
            return None
        preview = image.scaled(
            max_side,
            max_side,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._previews[item_id] = preview
        return preview

    # ------------------------------------------------------------------ удаление
    def remove(self, item_id: str) -> None:
        self._data.pop(item_id, None)
        self._images.pop(item_id, None)
        self._previews.pop(item_id, None)

    def clear(self) -> None:
        self._data.clear()
        self._images.clear()
        self._previews.clear()

    def total_bytes(self) -> int:
        return sum(len(d) for d in self._data.values())

    def ids(self):
        return list(self._data)

    def __len__(self) -> int:
        return len(self._data)


def readable_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if size < 1024 or unit == "ГБ":
            return f"{size:.0f} {unit}" if unit == "Б" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} ГБ"


def file_ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()