from PySide6.QtCore import QObject, Signal, Slot


class Bridge(QObject):
    coordinatesChanged = Signal(float, float)

    @Slot(float, float)
    def sendCoordinates(self, lat, lng):
        self.coordinatesChanged.emit(lat, lng)
