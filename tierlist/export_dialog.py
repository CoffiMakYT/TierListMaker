"""Окно предпросмотра и настроек экспорта готового тирлиста."""

from __future__ import annotations

import os
import re

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import theme, i18n
from .imagestore import ImageStore
from .model import DEFAULT_BACKGROUND, Project
from .render import (
    BASE_WIDTH,
    ExportOptions,
    build_layout,
    default_options,
    estimate_size,
    render_project,
    save_image,
)

PREVIEW_W = 600
PREVIEW_H = 470


class PreviewArea(QLabel):
    """Показывает готовое изображение по центру, масштабируя под размер."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(PREVIEW_W, PREVIEW_H)
        self._image: QImage | None = None
        self.setObjectName("Preview")

    def set_image(self, image: QImage) -> None:
        self._image = image
        self._refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        if self._image is None:
            self.setText(i18n.tr("preview_none"))
            return
        pixmap = QPixmap.fromImage(self._image)
        target = self.size() - QSize(24, 24)
        if target.width() > 0 and target.height() > 0:
            pixmap = pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(pixmap)


class ExportDialog(QDialog):
    exported = Signal(str)

    def __init__(self, project: Project, store: ImageStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.store = store
        self.options = default_options(project)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._update_preview)

        self.setWindowTitle(i18n.tr("export_title"))
        self.resize(1010, 660)
        self._build_ui()
        self._sync_controls()
        self._schedule()

    # ------------------------------------------------------------------ интерфейс
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        body = QHBoxLayout()
        body.setSpacing(14)

        preview_frame = QFrame(self)
        preview_frame.setObjectName("PreviewFrame")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview = PreviewArea(preview_frame)
        preview_layout.addWidget(self.preview)
        body.addWidget(preview_frame, 1)

        panel = QWidget(self)
        panel.setFixedWidth(300)
        form = QVBoxLayout(panel)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        title = QLabel(i18n.tr("export_settings"), panel)
        title.setObjectName("Section")
        form.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(9)

        self.cb_format = QComboBox(panel)
        self.cb_format.addItems(["PNG", "JPG"])
        grid.addWidget(QLabel(i18n.tr("format"), panel), 0, 0)
        grid.addWidget(self.cb_format, 0, 1)

        self.cb_quality = QComboBox(panel)
        self.cb_quality.addItems([i18n.tr("normal"), i18n.tr("high")])
        self.cb_quality.setCurrentIndex(1)
        grid.addWidget(QLabel(i18n.tr("quality"), panel), 1, 0)
        grid.addWidget(self.cb_quality, 1, 1)

        self.cb_resolution = QComboBox(panel)
        self.cb_resolution.addItems(["1x (1400 px)", "2x (2800 px)", i18n.tr("custom")])
        self.cb_resolution.setCurrentIndex(1)
        grid.addWidget(QLabel(i18n.tr("resolution"), panel), 2, 0)
        grid.addWidget(self.cb_resolution, 2, 1)

        self.sp_custom = QSpinBox(panel)
        self.sp_custom.setRange(600, 8000)
        self.sp_custom.setSingleStep(100)
        self.sp_custom.setValue(2800)
        self.sp_custom.setSuffix(" px")
        grid.addWidget(self.sp_custom, 3, 1)
        form.addLayout(grid)

        self.chk_title = QCheckBox(i18n.tr("show_title"), panel)
        self.chk_title.setChecked(True)
        form.addWidget(self.chk_title)

        self.ed_title = QLineEdit(panel)
        self.ed_title.setPlaceholderText(i18n.tr("title_text"))
        form.addWidget(self.ed_title)

        bg_row = QHBoxLayout()
        bg_row.setSpacing(8)
        self.btn_bg = QPushButton(i18n.tr("background_button"), panel)
        self.lb_bg = QLabel(panel)
        self.lb_bg.setFixedSize(26, 26)
        bg_row.addWidget(self.btn_bg)
        bg_row.addWidget(self.lb_bg)
        bg_row.addStretch(1)
        form.addLayout(bg_row)

        self.chk_pool = QCheckBox(i18n.tr("include_unranked"), panel)
        form.addWidget(self.chk_pool)

        self.chk_empty = QCheckBox(i18n.tr("show_empty"), panel)
        form.addWidget(self.chk_empty)

        form.addStretch(1)

        self.lb_info = QLabel("", panel)
        self.lb_info.setObjectName("Hint")
        self.lb_info.setWordWrap(True)
        form.addWidget(self.lb_info)

        body.addWidget(panel)
        root.addLayout(body, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.btn_cancel = QPushButton(i18n.tr("cancel"), self)
        self.btn_export = QPushButton(i18n.tr("export_button"), self)
        self.btn_export.setObjectName("Accent")
        self.btn_export.setDefault(True)
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_export)
        root.addLayout(buttons)

        self.ed_title.setText(self.project.name)
        self._update_bg_swatch()

        # --- сигналы
        self.cb_format.currentIndexChanged.connect(self._on_format)
        self.cb_quality.currentIndexChanged.connect(self._schedule)
        self.cb_resolution.currentIndexChanged.connect(self._on_resolution)
        self.sp_custom.valueChanged.connect(self._schedule)
        self.chk_title.toggled.connect(self._on_title_toggle)
        self.ed_title.textChanged.connect(self._schedule)
        self.btn_bg.clicked.connect(self._pick_bg)
        self.chk_pool.toggled.connect(self._schedule)
        self.chk_empty.toggled.connect(self._schedule)
        self.btn_export.clicked.connect(self._do_export)
        self.btn_cancel.clicked.connect(self.reject)

    # ------------------------------------------------------------------ состояние
    def _sync_controls(self) -> None:
        self.cb_format.setCurrentIndex(0)
        self.cb_resolution.setCurrentIndex(1)
        self.sp_custom.setValue(2800)
        self.sp_custom.setEnabled(False)
        self.chk_pool.setChecked(self.options.include_pool)
        self.chk_empty.setChecked(self.options.include_empty)
        self._on_format()

    def _scale(self) -> float:
        index = self.cb_resolution.currentIndex()
        if index == 0:
            return 1.0
        if index == 1:
            return 2.0
        return max(0.2, self.sp_custom.value() / float(BASE_WIDTH))

    def _collect(self) -> ExportOptions:
        self.options = ExportOptions(
            include_title=self.chk_title.isChecked(),
            title=self.ed_title.text(),
            background=self.options.background,
            include_pool=self.chk_pool.isChecked(),
            include_empty=self.chk_empty.isChecked(),
            scale=self._scale(),
        )
        return self.options

    def _schedule(self) -> None:
        self._timer.start()

    def _on_format(self) -> None:
        self.cb_quality.setEnabled(self.cb_format.currentText() == "JPG")
        self._schedule()

    def _on_resolution(self) -> None:
        self.sp_custom.setEnabled(self.cb_resolution.currentIndex() == 2)
        self._schedule()

    def _on_title_toggle(self, checked: bool) -> None:
        self.ed_title.setEnabled(checked)
        self._schedule()

    def _update_bg_swatch(self) -> None:
        color = QColor(self.options.background)
        if not color.isValid():
            color = QColor(DEFAULT_BACKGROUND)
        self.lb_bg.setStyleSheet(
            f"background: {color.name()}; border: 1px solid {theme.C['border']}; border-radius: 6px;"
        )

    def _pick_bg(self) -> None:
        color = QColorDialog.getColor(QColor(self.options.background), self, i18n.tr("choose_bg"))
        if color.isValid():
            self.options.background = color.name()
            self._update_bg_swatch()
            self._schedule()

    # ------------------------------------------------------------------ предпросмотр
    def _preview_scale(self, logical_height: float) -> float:
        avail_w = max(self.preview.width() - 24, 200)
        avail_h = max(self.preview.height() - 24, 200)
        return max(0.05, min(avail_w / BASE_WIDTH, avail_h / max(logical_height, 1.0)))

    def _update_preview(self) -> None:
        options = self._collect()
        try:
            layout = build_layout(self.project, options)
            preview_scale = self._preview_scale(layout.height)
            preview_options = ExportOptions(
                include_title=options.include_title,
                title=options.title,
                background=options.background,
                include_pool=options.include_pool,
                include_empty=options.include_empty,
                scale=preview_scale,
            )
            image = render_project(self.project, self.store, preview_options)
            self.preview.set_image(image)
        except Exception as error:  # noqa: BLE001 — предпросмотр не должен падать
            self.preview.setText(i18n.tr("preview_error", error=error))

        width, height = estimate_size(self.project, options)
        fmt = self.cb_format.currentText()
        self.lb_info.setText(i18n.tr("export_info", width=width, height=height, fmt=fmt))

    # ------------------------------------------------------------------ экспорт
    def _suggested_name(self) -> str:
        base = re.sub(r"[\\/:*?\"<>|]+", " ", self.project.name or "").strip()
        base = re.sub(r"\s+", " ", base) or "tierlist"
        ext = "png" if self.cb_format.currentText() == "PNG" else "jpg"
        return f"{base}.{ext}"

    def _do_export(self) -> None:
        options = self._collect()
        fmt = self.cb_format.currentText()
        suffix = "*.png" if fmt == "PNG" else "*.jpg"
        start_dir = os.path.dirname(self.project.path) if self.project.path else ""
        path, _ = QFileDialog.getSaveFileName(
            self,
            i18n.tr("save_export"),
            os.path.join(start_dir, self._suggested_name()) if start_dir else self._suggested_name(),
            f"Изображение ({suffix})",
        )
        if not path:
            return
        ext = ".png" if fmt == "PNG" else ".jpg"
        if not path.lower().endswith((".png", ".jpg", ".jpeg")):
            path += ext

        try:
            image = render_project(self.project, self.store, options)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, i18n.tr("export_error"), str(error))
            return

        quality = 85 if self.cb_quality.currentIndex() == 0 else 96
        try:
            ok = save_image(image, path, fmt, quality)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, i18n.tr("export_error"), str(error))
            return

        if not ok:
            QMessageBox.critical(
                self, i18n.tr("export_error"), f"Could not save file:\n{path}"
            )
            return

        self.exported.emit(path)
        self.accept()
