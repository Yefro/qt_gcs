import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QSlider, QWidget

from artificial_horizon import ArtificialHorizon


class Demo(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Artificial Horizon Demo")

        layout = QGridLayout(self)
        self.horizon = ArtificialHorizon()

        pitch_slider = QSlider(Qt.Horizontal)
        pitch_slider.setRange(-30, 30)
        pitch_slider.setValue(0)
        roll_slider = QSlider(Qt.Horizontal)
        roll_slider.setRange(-60, 60)
        roll_slider.setValue(0)

        pitch_slider.valueChanged.connect(
            lambda v: self.horizon.setPitch(v)
        )
        roll_slider.valueChanged.connect(
            lambda v: self.horizon.setRoll(v)
        )

        layout.addWidget(self.horizon, 0, 0, 1, 2)
        layout.addWidget(QLabel("Pitch (deg)"), 1, 0)
        layout.addWidget(pitch_slider, 1, 1)
        layout.addWidget(QLabel("Roll (deg)"), 2, 0)
        layout.addWidget(roll_slider, 2, 1)

        layout.setRowStretch(0, 1)
        layout.setColumnStretch(1, 1)


def main():
    app = QApplication(sys.argv)
    demo = Demo()
    demo.resize(520, 520)
    demo.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
