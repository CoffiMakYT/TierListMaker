"""Тёмная и светлая темы оформления."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication
import os
import sys

DARK = {
    "name": "dark",
    "bg": "#0f0f13",
    "panel": "#15151c",
    "panel_alt": "#1c1c24",
    "card": "#23232d",
    "card_hover": "#2c2c38",
    "border": "#2b2b37",
    "text": "#e9e9f2",
    "text_dim": "#8b8b9e",
    "accent": "#4d8dff",
    "accent_hover": "#6ba0ff",
    "accent_text": "#ffffff",
    "hover": "#24242f",
    "drop": "#4d8dff",
    "danger": "#e05a5a",
    "preview_bg": "#0b0b0e",
}

LIGHT = {
    "name": "light",
    "bg": "#f4f5f8",
    "panel": "#ffffff",
    "panel_alt": "#eef0f5",
    "card": "#e3e6ed",
    "card_hover": "#d8dce5",
    "border": "#d6dae2",
    "text": "#1b1c22",
    "text_dim": "#6b7080",
    "accent": "#2f6feb",
    "accent_hover": "#1f5ed6",
    "accent_text": "#ffffff",
    "hover": "#e7eaf1",
    "drop": "#2f6feb",
    "danger": "#cf4444",
    "preview_bg": "#dfe3ea",
}

THEMES = {"dark": DARK, "light": LIGHT}

# Активная палитра. Изменяется на месте, чтобы все ссылки остались валидными.
C: dict = dict(DARK)


def current_name() -> str:
    return C["name"]


def apply_theme(app: QApplication, name: str) -> None:
    palette = THEMES.get(name, DARK)
    C.clear()
    C.update(palette)
    QSettings().setValue("ui/theme", C["name"])
    app.setStyleSheet(build_qss())


def load_saved_name() -> str:
    name = str(QSettings().value("ui/theme", "dark"))
    return name if name in THEMES else "dark"


def build_qss() -> str:
    return f"""
QWidget {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: {C['text']};
}}
QMainWindow, QDialog {{ background: {C['bg']}; }}
QToolTip {{
    background: {C['panel']};
    color: {C['text']};
    border: 1px solid {C['border']};
    padding: 5px 8px;
    border-radius: 6px;
}}

QFrame#TopBar, QFrame#OptionsBar {{ background: {C['panel']}; }}
QFrame#TopBar {{ border-bottom: 1px solid {C['border']}; }}
QFrame#OptionsBar {{ border-bottom: 1px solid {C['border']}; }}
QFrame#PoolPanel {{ background: {C['panel']}; border-top: 1px solid {C['border']}; }}
QFrame#Separator {{ background: {C['border']}; max-width: 1px; min-width: 1px; }}

QLabel#Brand {{
    font-size: 12px;
    font-weight: 700;
    color: {C['text_dim']};
}}
QLabel#Section {{ font-size: 14px; font-weight: 600; }}
QLabel#Hint, QLabel#Dim {{ color: {C['text_dim']}; }}
QLabel#Count {{
    color: {C['text_dim']};
    background: {C['panel_alt']};
    border-radius: 8px;
    padding: 1px 8px;
}}

QPushButton {{
    background: {C['panel_alt']};
    border: 1px solid {C['border']};
    border-radius: 7px;
    padding: 6px 13px;
}}
QPushButton:hover {{ background: {C['hover']}; }}
QPushButton:pressed {{ background: {C['border']}; }}
QPushButton:disabled {{ color: {C['text_dim']}; background: transparent; border-color: {C['border']}; }}

QPushButton#Accent {{
    background: {C['accent']};
    border: 1px solid {C['accent']};
    color: {C['accent_text']};
    font-weight: 600;
}}
QPushButton#Accent:hover {{ background: {C['accent_hover']}; border-color: {C['accent_hover']}; }}

QPushButton#Seg {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 11px;
    color: {C['text_dim']};
}}
QPushButton#Seg:hover {{ background: {C['hover']}; color: {C['text']}; }}
QPushButton#Seg:checked {{
    background: {C['accent']};
    border-color: {C['accent']};
    color: {C['accent_text']};
    font-weight: 600;
}}

QPushButton#Ghost {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: {C['text_dim']};
    padding: 0px;
    font-size: 13px;
}}
QPushButton#Ghost:hover {{ background: {C['hover']}; color: {C['text']}; }}
QPushButton#Ghost:disabled {{ color: {C['border']}; background: transparent; }}

QLineEdit {{
    background: {C['panel_alt']};
    border: 1px solid {C['border']};
    border-radius: 7px;
    padding: 6px 10px;
    selection-background-color: {C['accent']};
    selection-color: {C['accent_text']};
}}
QLineEdit:focus {{ border: 1px solid {C['accent']}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px 2px 2px 0px;
}}
QScrollBar::handle:vertical {{
    background: {C['border']};
    border-radius: 5px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['text_dim']}; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 0px 2px 2px 2px;
}}
QScrollBar::handle:horizontal {{
    background: {C['border']};
    border-radius: 5px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{ background: {C['text_dim']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QMenu {{
    background: {C['panel']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{ padding: 7px 26px 7px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {C['accent']}; color: {C['accent_text']}; }}
QMenu::separator {{ height: 1px; background: {C['border']}; margin: 5px 8px; }}
QMenu::indicator {{ width: 12px; height: 12px; margin-left: 6px; }}

QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {C['panel_alt']};
    border: 1px solid {C['border']};
    border-radius: 7px;
    padding: 5px 9px;
    min-height: 20px;
}}
QComboBox:hover, QSpinBox:hover {{ border-color: {C['text_dim']}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {C['panel']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    selection-background-color: {C['accent']};
    selection-color: {C['accent_text']};
    outline: 0;
}}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid {C['border']};
    background: {C['panel_alt']};
}}
QCheckBox::indicator:hover {{ border-color: {C['accent']}; }}
QCheckBox::indicator:checked {{
    background: {C['accent']};
    border-color: {C['accent']};
}}

QSplitter::handle {{ background: {C['border']}; }}
QSplitter::handle:vertical {{ height: 1px; }}

QStatusBar {{
    background: {C['panel']};
    border-top: 1px solid {C['border']};
    color: {C['text_dim']};
}}
QStatusBar::item {{ border: none; }}

QDialogButtonBox QPushButton {{ min-width: 96px; }}
"""


def make_app_icon() -> QIcon:
    """Загружает встроенную иконку (сборка) или PNG-иконку из assets/."""
    if getattr(sys, "frozen", False):
        bundled = os.path.join(sys._MEIPASS, "tierlist-icon.png")
        icon = QIcon(bundled)
        if not icon.isNull():
            return icon
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon = QIcon(os.path.join(root, "assets", "tierlist-icon.png"))
    if not icon.isNull():
        return icon

    # Fallback: простая иконка — несколько цветных полосок.
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pix = QPixmap(size, size)
        pix.fill(QColor("transparent"))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing, True)
        radius = max(2.0, size * 0.12)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#4d8dff"))
        painter.drawRoundedRect(1, 1, size - 2, size - 2, radius, radius)
        rows = [("#d9534f", 0.24), ("#dfc341", 0.46), ("#57a54f", 0.68)]
        pad = size * 0.18
        bar_h = size * 0.13
        for color, frac in rows:
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(
                pad, size * frac, size - 2 * pad, bar_h, bar_h * 0.35, bar_h * 0.35
            )
        painter.end()
        icon.addPixmap(pix)
    return icon
