"""Tier List Maker — настольный редактор тирлистов.

Запуск: python main.py
"""

from __future__ import annotations

import os
import sys
import traceback

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from tierlist import theme
from tierlist.main_window import MainWindow


def _install_excepthook(app: QApplication) -> None:
    """Показываем ошибку в диалоге, а не молча роняем приложение."""

    def handler(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        sys.stderr.write(text)
        QMessageBox.critical(
            None,
            "Непредвиденная ошибка",
            f"Что-то пошло не так.\n\n{exc_value}\n\nПодробности записаны в консоль.",
        )

    sys.excepthook = handler


def main() -> int:
    QCoreApplication.setOrganizationName("Vlad")
    QCoreApplication.setApplicationName("TierListMaker")
    QCoreApplication.setApplicationVersion("1.0.0")

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationDisplayName("Tier List Maker")
    app.setWindowIcon(theme.make_app_icon())
    app.setFont(QFont("Segoe UI", 9))

    theme.apply_theme(app, theme.load_saved_name())
    _install_excepthook(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())