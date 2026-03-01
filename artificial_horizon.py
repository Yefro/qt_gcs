import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class ArtificialHorizon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pitch_deg = 0.0
        self._roll_deg = 0.0
        self._target_pitch_deg = 0.0
        self._target_roll_deg = 0.0
        self._last_update_ts = time.monotonic()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(120, 120)

        self._sky = QColor(70, 130, 180)
        self._ground = QColor(160, 100, 60)
        self._line = QColor(240, 240, 240)
        self._frame = QColor(30, 30, 30)
        self._accent = QColor(255, 200, 40)
        self._smoothing_timer = QTimer(self)
        self._smoothing_timer.setInterval(33)
        self._smoothing_timer.timeout.connect(self._step_smoothing)

    def pitch(self):
        return self._pitch_deg

    def roll(self):
        return self._roll_deg

    def setPitch(self, pitch_deg):
        pitch_deg = max(-90.0, min(90.0, float(pitch_deg)))
        if pitch_deg != self._pitch_deg:
            self._pitch_deg = pitch_deg
            self.update()

    def setRoll(self, roll_deg):
        roll_deg = max(-180.0, min(180.0, float(roll_deg)))
        if roll_deg != self._roll_deg:
            self._roll_deg = roll_deg
            self.update()

    def setPitchRoll(self, pitch_deg, roll_deg):
        self.setPitch(pitch_deg)
        self.setRoll(roll_deg)

    def setTargetPitchRoll(self, pitch_deg, roll_deg):
        self._target_pitch_deg = max(-90.0, min(90.0, float(pitch_deg)))
        self._target_roll_deg = max(-180.0, min(180.0, float(roll_deg)))
        if not self._smoothing_timer.isActive():
            self._last_update_ts = time.monotonic()
            self._smoothing_timer.start()

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        side = min(w, h)
        radius = side * 0.48
        center = QPointF(w * 0.5, h * 0.5)
        pixels_per_deg = radius / 30.0

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Clip to circular viewport
        circle_rect = QRectF(
            center.x() - radius,
            center.y() - radius,
            radius * 2.0,
            radius * 2.0,
        )
        painter.save()
        painter.setClipPath(self._circlePath(circle_rect))

        # Sky / ground with roll and pitch
        painter.translate(center)
        painter.rotate(-self._roll_deg)
        painter.translate(0.0, self._pitch_deg * pixels_per_deg)

        horizon_y = 0.0
        sky_rect = QRectF(-side, -side * 2.0, side * 2.0, side * 2.0)
        ground_rect = QRectF(-side, horizon_y, side * 2.0, side * 2.0)
        painter.fillRect(sky_rect, QBrush(self._sky))
        painter.fillRect(ground_rect, QBrush(self._ground))

        # Horizon line
        painter.setPen(QPen(self._line, 3))
        painter.drawLine(QPointF(-side, horizon_y), QPointF(side, horizon_y))

        # Pitch ladder
        painter.setPen(QPen(self._line, 2))
        font = painter.font()
        font.setPointSizeF(max(7.0, radius * 0.08))
        painter.setFont(font)

        for deg in range(-30, 31, 5):
            if deg == 0:
                continue
            y = -deg * pixels_per_deg
            length = radius * (0.55 if deg % 10 == 0 else 0.35)
            painter.drawLine(QPointF(-length, y), QPointF(length, y))
            if deg % 10 == 0:
                label = f"{abs(deg)}"
                painter.drawText(QPointF(-length - radius * 0.1, y + 4), label)
                painter.drawText(QPointF(length + radius * 0.03, y + 4), label)

        painter.restore()

        # Outer frame
        painter.setPen(QPen(self._frame, 4))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(circle_rect)

        # Roll scale
        painter.save()
        painter.translate(center)
        painter.setPen(QPen(self._line, 2))
        for deg in (-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60):
            angle = math.radians(deg - 90)
            inner = radius * 0.82
            outer = radius * (0.93 if deg % 30 == 0 else 0.88)
            p1 = QPointF(math.cos(angle) * inner, math.sin(angle) * inner)
            p2 = QPointF(math.cos(angle) * outer, math.sin(angle) * outer)
            painter.drawLine(p1, p2)
        painter.restore()

        # Fixed aircraft symbol
        painter.save()
        painter.translate(center)
        painter.setPen(QPen(self._accent, 3))
        wing = radius * 0.35
        painter.drawLine(QPointF(-wing, 0), QPointF(-radius * 0.1, 0))
        painter.drawLine(QPointF(wing, 0), QPointF(radius * 0.1, 0))
        painter.drawLine(QPointF(0, 0), QPointF(0, radius * 0.1))
        painter.restore()

    def _step_smoothing(self):
        now = time.monotonic()
        dt = max(0.0, now - self._last_update_ts)
        self._last_update_ts = now
        if dt <= 0.0:
            return

        tau = 0.12
        alpha = 1.0 - math.exp(-dt / tau)

        delta_roll = (self._target_roll_deg - self._roll_deg + 180.0) % 360.0 - 180.0
        new_roll = self._roll_deg + delta_roll * alpha
        new_pitch = self._pitch_deg + (self._target_pitch_deg - self._pitch_deg) * alpha

        new_pitch = max(-90.0, min(90.0, new_pitch))
        new_roll = max(-180.0, min(180.0, new_roll))

        if abs(new_pitch - self._pitch_deg) < 0.1 and abs(delta_roll) < 0.1:
            self._pitch_deg = self._target_pitch_deg
            self._roll_deg = self._target_roll_deg
            self.update()
            self._smoothing_timer.stop()
            return

        self._pitch_deg = new_pitch
        self._roll_deg = new_roll
        self.update()

    @staticmethod
    def _circlePath(rect):
        from PySide6.QtGui import QPainterPath

        path = QPainterPath()
        path.addEllipse(rect)
        return path
