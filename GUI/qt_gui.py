# xbee_gui.py
import sys
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)
from PyQt6.QtCore import QTimer
from serial_reader import start_serial_thread, message_queue


class XBeeViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XBee Data Viewer")

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Latest Data", "Timestamp (ms)"])
        self.table.horizontalHeader().setStretchLastSection(True)

        layout = QVBoxLayout()
        layout.addWidget(self.table)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.id_to_row = {}       # Maps ID to table row index
        self.latest_data = {}     # Maps ID to (data, timestamp)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_from_queue)
        self.timer.start(100)

    def update_from_queue(self):
        while not message_queue.empty():
            msg = message_queue.get()
            self.process_message(msg)

        self.refresh_table()

    def process_message(self, message):
        # Match the format using regex
        match = re.search(r"Time\(ms\):\s*(\d+),\s*ID:\s*(\d+),\s*Data:\s*(.*)", message)
        if match:
            timestamp = int(match.group(1))
            msg_id = int(match.group(2))
            data = match.group(3).strip()
            self.latest_data[msg_id] = (data, timestamp)

    def refresh_table(self):
        for msg_id, (data, timestamp) in self.latest_data.items():
            if msg_id in self.id_to_row:
                row = self.id_to_row[msg_id]
            else:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.id_to_row[msg_id] = row

            self.table.setItem(row, 0, QTableWidgetItem(str(msg_id)))
            self.table.setItem(row, 1, QTableWidgetItem(data))
            self.table.setItem(row, 2, QTableWidgetItem(str(timestamp)))


if __name__ == "__main__":
    start_serial_thread()
    app = QApplication(sys.argv)
    viewer = XBeeViewer()
    viewer.resize(600, 400)
    viewer.show()
    sys.exit(app.exec())
