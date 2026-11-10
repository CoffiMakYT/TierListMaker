"""Главное окно приложения."""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QActionGroup, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QColorDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from . import theme
from . import i18n
from .export_dialog import ExportDialog
from .flow import FlowArea
from .imagestore import ImageStore, file_ext, readable_size
from .model import ASPECTS, DEFAULT_TIER_COLORS, SUPPORTED_EXTS, Item, Project, new_id
from .project_io import PROJECT_EXT, ProjectError, load_project, save_project
from .tierrow import TierRow
from .workshop import WorkshopDialog, apply_import

POOL_MIN_HEIGHT = 120


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project = Project.default()
        self.store = ImageStore()
        self._undo: list[dict] = []
        self._redo: list[dict] = []
        self._settings = QSettings()
        self._workshop_dialog = None
        self._workshop_stream_count = 0
        self._workshop_drawn = 0
        self._workshop_flush = QTimer(self)
        self._workshop_flush.setSingleShot(True)
        self._workshop_flush.setInterval(150)
        self._workshop_flush.timeout.connect(self._flush_workshop_batch)
        i18n.load_language()

        self.setWindowIcon(theme.make_app_icon())
        self.resize(1300, 860)
        self.setMinimumSize(940, 620)

        self._build_ui()
        self._build_menu()
        self._install_shortcuts()
        self.refresh()

    # ================================================================== интерфейс
    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------------------------------------------------------- верхняя панель
        top = QFrame(central)
        top.setObjectName("TopBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(14, 10, 14, 10)
        top_layout.setSpacing(8)

        brand = QLabel("TIER LIST MAKER", top)
        brand.setObjectName("Brand")
        top_layout.addWidget(brand)
        top_layout.addWidget(self._separator(top))

        self.ed_name = QLineEdit(self.project.name, top)
        self.ed_name.setPlaceholderText(i18n.tr("project_name"))
        self.ed_name.setFixedWidth(250)
        self.ed_name.setToolTip(i18n.tr("rename_tip"))
        self.ed_name.editingFinished.connect(self._on_name_edited)
        top_layout.addWidget(self.ed_name)

        top_layout.addStretch(1)

        btn_new = self._button(i18n.tr("new"), self._new_project, tip="Ctrl+N")
        btn_open = self._button(i18n.tr("open"), self._open_project, tip="Ctrl+O")
        btn_save = self._button(i18n.tr("save"), self._save_project, tip="Ctrl+S")
        btn_save_as = self._button(
            i18n.tr("save_as"), lambda: self._save_project(True), tip="Ctrl+Shift+S"
        )
        for button in (btn_new, btn_open, btn_save, btn_save_as):
            top_layout.addWidget(button)

        top_layout.addWidget(self._separator(top))

        btn_import = self._button(
            i18n.tr("import"), self._import_dialog, "Accent", "Ctrl+I"
        )
        btn_export = self._button(i18n.tr("export"), self._export, tip="Ctrl+E")
        top_layout.addWidget(btn_import)
        top_layout.addWidget(btn_export)

        top_layout.addWidget(self._separator(top))

        self.btn_theme = QPushButton(i18n.tr("theme") + " ▾", top)
        self.btn_theme.setToolTip(i18n.tr("Оформление приложения") if i18n.language() == "ru" else "Appearance")
        top_layout.addWidget(self.btn_theme)

        self.btn_language = QPushButton("EN" if i18n.language() == "ru" else "RU", top)
        self.btn_language.setToolTip("Switch language / Сменить язык")
        self.btn_language.clicked.connect(self._toggle_language)
        top_layout.addWidget(self.btn_language)

        self.btn_workshop = QPushButton(i18n.tr("workshop"), top)
        self.btn_workshop.setToolTip("Public TierMaker templates")
        self.btn_workshop.clicked.connect(self._open_workshop)
        top_layout.addWidget(self.btn_workshop)

        root.addWidget(top)

        # ---------------------------------------------------------- панель опций
        options = QFrame(central)
        options.setObjectName("OptionsBar")
        options_layout = QHBoxLayout(options)
        options_layout.setContentsMargins(14, 8, 14, 8)
        options_layout.setSpacing(6)

        options_layout.addWidget(self._dim_label(i18n.tr("aspect"), options))
        self._shape_group = QButtonGroup(self)
        self._shape_buttons: dict[str, QPushButton] = {}
        for key, title in (("3:4", "3:4 · " + i18n.tr("aspect_card")), ("1:1", "1:1 · " + i18n.tr("aspect_square")), ("4:3", "4:3 · " + i18n.tr("aspect_landscape"))):
            button = QPushButton(title, options)
            button.setObjectName("Seg")
            button.setCheckable(True)
            button.setToolTip(i18n.tr("card_shape_tip", key=key))
            button.clicked.connect(lambda _=False, k=key: self._set_aspect(k))
            self._shape_group.addButton(button)
            self._shape_buttons[key] = button
            options_layout.addWidget(button)

        options_layout.addWidget(self._separator(options))
        options_layout.addWidget(self._dim_label(i18n.tr("fit"), options))
        self._fit_group = QButtonGroup(self)
        self._fit_buttons: dict[str, QPushButton] = {}
        for key, title in (("cover", i18n.tr("cover")), ("contain", i18n.tr("contain"))):
            button = QPushButton(title, options)
            button.setObjectName("Seg")
            button.setCheckable(True)
            button.setToolTip(i18n.tr("cover_tip" if key == "cover" else "contain_tip"))
            button.clicked.connect(lambda _=False, k=key: self._set_fit(k))
            self._fit_group.addButton(button)
            self._fit_buttons[key] = button
            options_layout.addWidget(button)

        options_layout.addWidget(self._separator(options))
        btn_add = self._button(i18n.tr("add_tier"), self._add_tier, tip="Add tier / Добавить уровень")
        options_layout.addWidget(btn_add)

        options_layout.addStretch(1)
        self.lb_hint = self._dim_label(i18n.tr("drag_hint"), options)
        options_layout.addWidget(self.lb_hint)

        root.addWidget(options)

        # ---------------------------------------------------------- центральная часть
        splitter = QSplitter(Qt.Vertical, central)
        splitter.setChildrenCollapsible(False)

        self.tiers_scroll = QScrollArea(splitter)
        self.tiers_scroll.setWidgetResizable(True)
        self.tiers_scroll.setFrameShape(QFrame.NoFrame)
        self.tiers_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tiers_host = QWidget(self.tiers_scroll)
        self.tiers_layout = QVBoxLayout(self.tiers_host)
        self.tiers_layout.setContentsMargins(14, 14, 14, 16)
        self.tiers_layout.setSpacing(10)
        self.tiers_scroll.setWidget(self.tiers_host)
        splitter.addWidget(self.tiers_scroll)

        pool_panel = QFrame(splitter)
        pool_panel.setObjectName("PoolPanel")
        pool_layout = QVBoxLayout(pool_panel)
        pool_layout.setContentsMargins(14, 10, 14, 12)
        pool_layout.setSpacing(8)

        pool_head = QHBoxLayout()
        pool_head.setSpacing(8)
        pool_title = QLabel(i18n.tr("pool"), pool_panel)
        pool_title.setObjectName("Section")
        pool_head.addWidget(pool_title)
        self.lb_pool_count = QLabel("0", pool_panel)
        self.lb_pool_count.setObjectName("Count")
        pool_head.addWidget(self.lb_pool_count)
        pool_head.addStretch(1)
        self.pool_hint = self._dim_label(i18n.tr("pool_hint"), pool_panel)
        pool_head.addWidget(self.pool_hint)
        pool_layout.addLayout(pool_head)

        self.pool_scroll = QScrollArea(pool_panel)
        self.pool_scroll.setWidgetResizable(True)
        self.pool_scroll.setFrameShape(QFrame.NoFrame)
        self.pool_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pool_host = QWidget(self.pool_scroll)
        pool_host_layout = QVBoxLayout(self.pool_host)
        pool_host_layout.setContentsMargins(0, 0, 0, 0)
        self.pool_flow = FlowArea(
            self.pool_host,
            empty_height=POOL_MIN_HEIGHT,
            hint=i18n.tr("pool_empty"),
        )
        pool_host_layout.addWidget(self.pool_flow)
        pool_host_layout.addStretch(1)
        self.pool_scroll.setWidget(self.pool_host)
        pool_layout.addWidget(self.pool_scroll, 1)

        splitter.addWidget(pool_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([580, 300])
        root.addWidget(splitter, 1)

        # ---------------------------------------------------------- статусбар
        status = QStatusBar(self)
        self.setStatusBar(status)
        self.lb_status = QLabel("", status)
        status.addWidget(self.lb_status)

        # ---------------------------------------------------------- сигналы
        self.pool_flow.itemsDropped.connect(lambda ids, index: self._on_items_dropped(None, ids, index))
        self.pool_flow.filesDropped.connect(lambda paths, index: self._on_files_dropped(None, paths, index))
        self.pool_flow.contextAction.connect(self._on_card_action)

    def _build_menu(self) -> None:
        menu = QMenu(self)
        group = QActionGroup(self)
        group.setExclusive(True)
        self._theme_actions = {}
        for name, title in (("dark", i18n.tr("theme_dark")), ("light", i18n.tr("theme_light"))):
            action = menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(theme.current_name() == name)
            action.triggered.connect(lambda _=False, n=name: self._set_theme(n))
            group.addAction(action)
            self._theme_actions[name] = action
        self.btn_theme.setMenu(menu)

    def _toggle_language(self) -> None:
        i18n.set_language("en" if i18n.language() == "ru" else "ru")
        # Recreate static UI so every label and menu is translated consistently.
        self._rebuild_ui()

    def _rebuild_ui(self) -> None:
        old = self.centralWidget()
        for shortcut in getattr(self, "_shortcuts", []):
            shortcut.setParent(None)
            shortcut.deleteLater()
        self._shortcuts = []
        self._theme_actions = {}
        self._build_ui()
        self._build_menu()
        self._install_shortcuts()
        self.refresh(keep_scroll=False)
        old.deleteLater()

    def _open_workshop(self) -> None:
        dialog = WorkshopDialog(i18n.language(), self)
        dialog.confirm_import = lambda: self._prepare_workshop_import(dialog)
        dialog.importBatch.connect(self._on_workshop_batch)
        dialog.imported.connect(self._import_workshop_template)
        dialog.importFailed.connect(self._on_workshop_import_failed)
        self._workshop_dialog = dialog
        try:
            dialog.exec()
        finally:
            self._workshop_dialog = None

    def _prepare_workshop_import(self, parent=None) -> bool:
        """Ask before replacing the current tier list, then clear it for streaming."""
        if self.project.items or self.project.dirty:
            answer = QMessageBox.question(
                parent or self,
                i18n.tr("workshop"),
                i18n.tr("replace_template"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False
        self._push_undo()
        for item_id in list(self.project.items):
            self.store.remove(item_id)
        self.project.items.clear()
        self.project.pool.clear()
        for tier in self.project.tiers:
            tier.items.clear()
        self._workshop_stream_count = 0
        self._workshop_drawn = 0
        self._mark_dirty()
        self.refresh(keep_scroll=False)
        return True

    def _on_workshop_batch(self, images: list) -> None:
        """Append a streamed batch of downloaded template images to the project."""
        added = 0
        for _source_id, name, payload in images:
            item_id = new_id()
            if not self.store.add_bytes(item_id, payload):
                continue
            ext = ".webp" if name.lower().endswith(".webp") else ".jpg" if name.lower().endswith((".jpg", ".jpeg")) else ".png"
            self.project.items[item_id] = Item(item_id, name, ext)
            self.project.pool.append(item_id)
            added += 1
        if not added:
            return
        self._workshop_stream_count += added
        self.project.dirty = True
        self._update_title()
        if not self._workshop_flush.isActive():
            self._workshop_flush.start()

    def _flush_workshop_batch(self) -> None:
        pending = self.project.pool[self._workshop_drawn:]
        if not pending:
            return
        cards = [
            (item_id, self.project.items[item_id].name if item_id in self.project.items else "?", False)
            for item_id in pending
        ]
        self.pool_flow.append_items(
            cards, self.store, self.project.card_aspect, self.project.image_fit
        )
        self._workshop_drawn = len(self.project.pool)
        self.lb_pool_count.setText(str(len(self.project.pool)))
        self._update_status()

    def _import_workshop_template(self, result: dict) -> None:
        self._workshop_flush.stop()
        self._flush_workshop_batch()
        apply_import(result, self.project, self.store, include_images=False)
        self._mark_dirty()
        self.refresh(keep_scroll=False, refresh_pool=False)
        added = int(result.get("count") or self._workshop_stream_count)
        self.statusBar().showMessage(
            f"{i18n.tr('workshop')}: {added} {i18n.tr('pool')}", 6000
        )
        self._workshop_stream_count = added
        self._workshop_drawn = len(self.project.pool)

    def _on_workshop_import_failed(self, _message: str) -> None:
        self._workshop_flush.stop()
        self._flush_workshop_batch()
        # Nothing was downloaded: put the previous project back.
        if self._workshop_stream_count <= 0 and self._undo:
            self._undo_action()

    def _install_shortcuts(self) -> None:
        if not hasattr(self, "_shortcuts"):
            self._shortcuts = []
        bindings = {
            "Ctrl+N": self._new_project,
            "Ctrl+O": self._open_project,
            "Ctrl+S": self._save_project,
            "Ctrl+Shift+S": lambda: self._save_project(True),
            "Ctrl+I": self._import_dialog,
            "Ctrl+E": self._export,
            "Ctrl+Z": self._undo_action,
            "Ctrl+Y": self._redo_action,
            "Ctrl+Shift+Z": self._redo_action,
        }
        for sequence, handler in bindings.items():
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    # ------------------------------------------------------------------ мелочи UI
    def _button(self, text: str, slot, object_name: str = "", tip: str = "") -> QPushButton:
        button = QPushButton(text, self)
        if object_name:
            button.setObjectName(object_name)
        if tip:
            button.setToolTip(tip)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda _=False: slot())
        return button

    def _separator(self, parent: QWidget) -> QFrame:
        frame = QFrame(parent)
        frame.setObjectName("Separator")
        frame.setFixedWidth(1)
        return frame

    def _dim_label(self, text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setObjectName("Hint")
        return label

    # ================================================================== обновление
    def refresh(self, keep_scroll: bool = True, refresh_pool: bool = True) -> None:
        scroll_value = self.tiers_scroll.verticalScrollBar().value() if keep_scroll else 0

        # --- уровни
        while self.tiers_layout.count():
            entry = self.tiers_layout.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()

        total = len(self.project.tiers)
        for index, tier in enumerate(self.project.tiers):
            items = [
                (item_id, self.project.items[item_id].name if item_id in self.project.items else "?")
                for item_id in tier.items
            ]
            row = TierRow(
                tier,
                [(item_id, name, True) for item_id, name in items],
                self.store,
                self.project.card_aspect,
                self.project.image_fit,
                can_up=index > 0,
                can_down=index < total - 1,
                parent=self.tiers_host,
            )
            row.renameRequested.connect(self._rename_tier)
            row.colorRequested.connect(self._color_tier)
            row.moveRequested.connect(self._move_tier)
            row.deleteRequested.connect(self._delete_tier)
            row.contextAction.connect(self._on_card_action)
            row.itemsDropped.connect(lambda ids, pos, tid=tier.id: self._on_items_dropped(tid, ids, pos))
            row.filesDropped.connect(lambda paths, pos, tid=tier.id: self._on_files_dropped(tid, paths, pos))
            row.show()
            self.tiers_layout.addWidget(row)

        self.tiers_layout.addStretch(1)

        # --- корзина
        pool_items = [
            (item_id, self.project.items[item_id].name if item_id in self.project.items else "?", False)
            for item_id in self.project.pool
        ]
        if refresh_pool:
            self.pool_flow.set_items(pool_items, self.store, self.project.card_aspect, self.project.image_fit)
        self.lb_pool_count.setText(str(len(pool_items)))

        # --- состояние элементов управления
        self._sync_controls()
        self._update_title()
        self._update_status()

        QTimer.singleShot(0, lambda: self.tiers_scroll.verticalScrollBar().setValue(scroll_value))

    def _sync_controls(self) -> None:
        for key, button in self._shape_buttons.items():
            button.setChecked(self.project.card_aspect == key)
        for key, button in self._fit_buttons.items():
            button.setChecked(self.project.image_fit == key)
        if self.ed_name.text() != self.project.name:
            self.ed_name.setText(self.project.name)

    def _update_title(self) -> None:
        mark = " •" if self.project.dirty else ""
        self.setWindowTitle(f"{self.project.name or i18n.tr('untitled')}{mark} — Tier List Maker")

    def _update_status(self) -> None:
        total, assigned, free = self.project.counts()
        size = readable_size(self.store.total_bytes())
        self.lb_status.setText(i18n.tr("status", total=total, assigned=assigned, free=free, size=size))

    # ================================================================== действия с моделью
    def _mark_dirty(self) -> None:
        self.project.dirty = True
        self._update_title()

    def _push_undo(self) -> None:
        self._undo.append(self.project.snapshot())
        if len(self._undo) > 60:
            self._undo.pop(0)
        self._redo.clear()

    def _undo_action(self) -> None:
        if not self._undo:
            return
        self._redo.append(self.project.snapshot())
        self.project.restore(self._undo.pop())
        self.project.dirty = True
        self.refresh()
        self.statusBar().showMessage(i18n.tr("reset_action"), 2000)

    def _redo_action(self) -> None:
        if not self._redo:
            return
        self._undo.append(self.project.snapshot())
        self.project.restore(self._redo.pop())
        self.project.dirty = True
        self.refresh()
        self.statusBar().showMessage(i18n.tr("redo_action"), 2000)

    # ------------------------------------------------------------------ карточки
    def _on_items_dropped(self, tier_id: str | None, ids: list[str], index: int) -> None:
        self._push_undo()
        self.project.move(list(ids), tier_id, index)
        self._mark_dirty()
        self.refresh()

    def _on_files_dropped(self, tier_id: str | None, paths: list[str], index: int) -> None:
        self._import_paths(paths, tier_id, index)

    def _on_card_action(self, item_id: str, action: str) -> None:
        if action == "pool":
            if self.project.locate(item_id)[0] is None:
                return
            self._push_undo()
            self.project.move([item_id], None, len(self.project.pool))
            self._mark_dirty()
            self.refresh()
        elif action == "delete":
            self._push_undo()
            self.project.remove_item(item_id)
            self._mark_dirty()
            self.refresh()
            self.statusBar().showMessage("Изображение удалено (Ctrl+Z — вернуть)", 3000)

    # ------------------------------------------------------------------ импорт
    def _import_dialog(self) -> None:
        start_dir = str(self._settings.value("paths/last", "") or "")
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            i18n.tr("import_dialog"),
            start_dir,
            i18n.tr("image_filter"),
        )
        if paths:
            self._settings.setValue("paths/last", os.path.dirname(paths[0]))
            self._import_paths(paths, None, None)

    def _import_paths(self, paths: list[str], tier_id: str | None, index: int | None) -> None:
        files = [p for p in paths if os.path.isfile(p)]
        if not files:
            return
        before_import = self.project.snapshot()
        added: list[str] = []
        failed: list[str] = []
        for path in files:
            ext = file_ext(path)
            if ext not in SUPPORTED_EXTS:
                failed.append(os.path.basename(path))
                continue
            item_id = new_id()
            if not self.store.add_file(item_id, path):
                failed.append(os.path.basename(path))
                continue
            self.project.items[item_id] = Item(id=item_id, name=os.path.basename(path), ext=ext)
            added.append(item_id)

        if added:
            self._undo.append(before_import)
            self._undo = self._undo[-60:]
            self._redo.clear()
            self.project.move(added, tier_id, index)
            self._mark_dirty()
            self.refresh()
            self.statusBar().showMessage(i18n.tr("added_count", count=len(added)), 4000)

        if failed:
            preview = "\n".join(failed[:8])
            if len(failed) > 8:
                preview += f"\n…и ещё {len(failed) - 8}"
            QMessageBox.warning(
                self,
                i18n.tr("import_error_title"),
                i18n.tr("import_error_body", names=preview),
            )

    # ------------------------------------------------------------------ уровни
    def _add_tier(self) -> None:
        self._push_undo()
        self.project.add_tier()
        self._mark_dirty()
        self.refresh()
        QTimer.singleShot(
            0,
            lambda: self.tiers_scroll.verticalScrollBar().setValue(
                self.tiers_scroll.verticalScrollBar().maximum()
            ),
        )

    def _rename_tier(self, tier_id: str) -> None:
        tier = self.project.tier_by_id(tier_id)
        if tier is None:
            return
        text, ok = QInputDialog.getText(self, i18n.tr("tier_name_title"), i18n.tr("name_label"), text=tier.label)
        if not ok:
            return
        new_label = text.strip()
        if not new_label or new_label == tier.label:
            return
        self._push_undo()
        tier.label = new_label
        self._mark_dirty()
        self.refresh()

    def _color_tier(self, tier_id: str) -> None:
        tier = self.project.tier_by_id(tier_id)
        if tier is None:
            return
        color = QColorDialog.getColor(QColor(tier.color), self, i18n.tr("tier_color_title"))
        if not color.isValid():
            return
        self._push_undo()
        tier.color = color.name()
        self._mark_dirty()
        self.refresh()

    def _move_tier(self, tier_id: str, direction: int) -> None:
        self._push_undo()
        if self.project.move_tier(tier_id, direction):
            self._mark_dirty()
            self.refresh()
        else:
            self._undo.pop()

    def _delete_tier(self, tier_id: str) -> None:
        tier = self.project.tier_by_id(tier_id)
        if tier is None:
            return
        if len(self.project.tiers) <= 1:
            QMessageBox.information(self, i18n.tr("Удаление уровня") if i18n.language() == "ru" else "Delete tier", i18n.tr("one_tier_min"))
            return
        if tier.items:
            answer = QMessageBox.question(
                self,
                i18n.tr("delete_tier_title"),
                i18n.tr("tier_delete_confirm", label=tier.label, count=len(tier.items)),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return
        self._push_undo()
        self.project.remove_tier(tier_id)
        self._mark_dirty()
        self.refresh()

    # ------------------------------------------------------------------ вид
    def _set_aspect(self, key: str) -> None:
        if key not in ASPECTS or key == self.project.card_aspect:
            return
        self._push_undo()
        self.project.card_aspect = key
        self._mark_dirty()
        self.refresh()

    def _set_fit(self, key: str) -> None:
        if key == self.project.image_fit:
            return
        self._push_undo()
        self.project.image_fit = key
        self._mark_dirty()
        self.refresh()

    def _set_theme(self, name: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        theme.apply_theme(app, name)
        for key, action in self._theme_actions.items():
            action.setChecked(key == name)
        self.refresh()
        self.update()

    def _on_name_edited(self) -> None:
        name = self.ed_name.text().strip()
        if not name or name == self.project.name:
            self.ed_name.setText(self.project.name)
            return
        self._push_undo()
        self.project.name = name
        self._mark_dirty()
        self.refresh()
        self._update_status()

    # ================================================================== файлы
    def _default_dir(self) -> str:
        directory = str(self._settings.value("paths/last", "") or "")
        if directory and os.path.isdir(directory):
            return directory
        return os.path.join(os.path.expanduser("~"), "Documents")

    def _safe_name(self) -> str:
        base = "".join(ch for ch in self.project.name if ch not in '\\/:*?"<>|').strip()
        return base or "tierlist"

    def _confirm_discard(self) -> bool:
        if not self.project.dirty:
            return True
        answer = QMessageBox.question(
            self,
            i18n.tr("discard_title"),
            i18n.tr("save_changes"),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if answer == QMessageBox.Cancel:
            return False
        if answer == QMessageBox.Save:
            return bool(self._save_project())
        return True

    def _new_project(self) -> None:
        if not self._confirm_discard():
            return
        name, ok = QInputDialog.getText(self, i18n.tr("new_project"), i18n.tr("project_title_prompt"), text="My tier list" if i18n.language() == "en" else "Мой тирлист")
        if not ok:
            return
        self.project = Project.default((name or "Мой тирлист").strip() or "Мой тирлист")
        self.store.clear()
        self._undo.clear()
        self._redo.clear()
        self.refresh(keep_scroll=False)
        self.statusBar().showMessage(i18n.tr("new_created"), 3000)

    def _open_project(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            i18n.tr("open_project_title"),
            self._default_dir(),
            f"Проект Tier List (*{PROJECT_EXT})",
        )
        if not path:
            return
        try:
            project, store = load_project(path)
        except ProjectError as error:
            QMessageBox.critical(self, i18n.tr("open_error"), str(error))
            return

        self.project = project
        self.store = store
        self._undo.clear()
        self._redo.clear()
        self._settings.setValue("paths/last", os.path.dirname(path))

        missing = getattr(project, "missing_images", [])
        # Хранилище сменилось — пересобираем карточки заново.
        self.refresh(keep_scroll=False)
        self.statusBar().showMessage(i18n.tr("opened_project", path=path), 5000)
        if missing:
            QMessageBox.warning(
                self,
                i18n.tr("incomplete_archive"),
                i18n.tr("missing_images", names="\n".join(missing[:8])),
            )

    def _save_project(self, save_as: bool = False) -> bool:
        path = None if save_as else self.project.path
        if not path:
            suggested = os.path.join(self._default_dir(), self._safe_name() + PROJECT_EXT)
            path, _ = QFileDialog.getSaveFileName(
                self,
                i18n.tr("save_project_title"),
                suggested,
                i18n.tr("project_filter", ext=PROJECT_EXT),
            )
            if not path:
                return False
            if not path.lower().endswith(PROJECT_EXT):
                path += PROJECT_EXT

        try:
            save_project(self.project, path, self.store)
        except ProjectError as error:
            QMessageBox.critical(self, i18n.tr("save_error"), str(error))
            return False
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, i18n.tr("save_error"), i18n.tr("save_error_body", error=error))
            return False

        self.project.path = path
        self.project.dirty = False
        self._settings.setValue("paths/last", os.path.dirname(path))
        self._update_title()
        self._update_status()
        self.statusBar().showMessage(i18n.tr("saved_path", path=path), 6000)
        return True

    def _export(self) -> None:
        if not self.project.items:
            QMessageBox.information(
                self,
                i18n.tr("export_empty"),
                i18n.tr("empty_project"),
            )
            return
        dialog = ExportDialog(self.project, self.store, self)
        dialog.exported.connect(
            lambda path: self.statusBar().showMessage(i18n.tr("exported_path", path=path), 8000)
        )
        dialog.exec()

    # ================================================================== события
    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
