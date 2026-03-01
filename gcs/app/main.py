import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gcs.ui.main_window import MainWindow
from gcs.viewmodels.main_viewmodel import MainViewModel


def main():
    # Mitiga parpadeos en QWebEngine (Windows) forzando software compositing.
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing"
    )
    QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
    app = QApplication(sys.argv)
    viewmodel = MainViewModel()
    window = MainWindow(viewmodel)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
