import sys
import serial
import cantools
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QTabWidget, QHeaderView, QPushButton, QHBoxLayout
)
class SerialCANReceiver(QObject):
    new_message = Signal(int, int, bytes)  # msg_id, timestamp, raw_data

    def __init__(self, port):
        super().__init__()
        self.port = port
        self.serial = None
        self.initialize_serial()

        self.timer = QTimer()
        self.timer.setInterval(1)  # Fast polling (1ms)
        self.timer.timeout.connect(self.read_serial_data)
        self.timer.start()

    def initialize_serial(self):
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=230400,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            print(f"Connected to {self.port}")
        except Exception as e:
            print(f"Serial error: {e}")
            self.serial = None

    def read_frame(self):
        if not self.serial or not self.serial.in_waiting:
            return None

        if self.serial.read(1) != b'\x7E':
            return None

        length_bytes = self.serial.read(2)
        if len(length_bytes) < 2:
            return None
        length = int.from_bytes(length_bytes, byteorder='big')

        frame_data = self.serial.read(length)
        if len(frame_data) < length:
            return None

        return frame_data

    def parse_xbee_frame(self, frame_data):
        if not frame_data or frame_data[0] != 0x91:
            return None
        return frame_data[18:].decode('utf-8', errors='ignore')

    def parse_can_message(self, message_str):
        try:
            parts = [p.strip() for p in message_str.split(',')]
            if len(parts) < 3:
                return None

            timestamp = int(parts[0].split('Time(ms):')[1])
            msg_id = int(parts[1].split('ID:')[1])
            hex_data = parts[2].split('Data:')[1].strip().split()
            raw_data = bytes(int(b, 16) for b in hex_data if b)

            return msg_id, timestamp, raw_data
        except Exception as e:
            print(f"Parse error: {e}")
            return None

    def read_serial_data(self):
        if not self.serial:
            return

        frame = self.read_frame()
        if not frame:
            return
        
        print("FRAME: ", frame)
        message_str = self.parse_xbee_frame(frame)
        if not message_str:
            return

        can_data = self.parse_can_message(message_str)
        if can_data:
            self.new_message.emit(*can_data)
class TestReceiver(QObject):
    def __init__(self):
        super().__init__()
        # Replace with the actual path to your serial port
        port = '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10NKEFQ-if00-port0'
        self.receiver = SerialCANReceiver(port)
        self.receiver.new_message.connect(self.handle_new_message)

    def handle_new_message(self, msg_id, timestamp, raw_data):
        print(f"Received: ID={msg_id}, Time={timestamp}, Data={raw_data.hex()}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    test = TestReceiver()
    sys.exit(app.exec())