import sys
import serial
import time
import cantools
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QTabWidget
)

try:
    dbc = cantools.database.load_file('FEB_CAN.dbc')
    print("Loaded DBC file with messages:")
    for msg in dbc.messages:
        print(f"ID: 0x{msg.frame_id:X}, Name: {msg.name}")
except Exception as e:
    print(f"Error loading DBC file: {e}")
    dbc = None

class SerialCANReceiver(QObject):
    # Message has format of: 
    # id, timestamp(idfk the units), raw_data
    new_message = Signal(int, int, bytes)

    def __init__(self, port):
        super().__init__()
        self.port = port
        self.serial = None
        self.initialize_serial()

        self.timer = QTimer()
        self.timer.setInterval(10)  # Arbitrary speed of 10ms, feel free to make faster
        self.timer.timeout.connect(self.read_serial_data)
        self.timer.start()

    def initialize_serial(self):
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=115200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            print(f"Successfully connected to {self.port}")
        except Exception as e:
            print(f"Serial connection error: {e}")
            self.serial = None

    def read_frame(self):
        if not self.serial or not self.serial.in_waiting:
            return None

        # this is just randomly what I got working 
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
        if not frame_data or frame_data[0] != 0x91: # Make sure it's from our XBee and not random junk 
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
            raw_data = bytes(int(b, 16) for b in hex_data)

            return msg_id, timestamp, raw_data
        except Exception as e:
            print(f"Message parsing error: {e}")
            return None

    def read_serial_data(self):
        if not self.serial:
            return

        frame = self.read_frame()
        if not frame:
            return

        message_str = self.parse_xbee_frame(frame)
        if not message_str:
            return

        can_data = self.parse_can_message(message_str)
        if can_data:
            self.new_message.emit(*can_data)

class BaseMessageView(QWidget):
    def __init__(self):
        super().__init__()
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Timestamp (ms)", "Latest Data"])
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        
        # Font can be whatever you want, it just needs to be monospace
        font = self.table.font()
        font.setFamily("Courier New")
        font.setPointSize(font.pointSize() + 1) 
        self.table.setFont(font)
        
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #c0c0c0;
            }
            QTableWidget::item {
                padding-top: 4px;
                padding-bottom: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        self.data = {}

    def update_message(self, msg_id, timestamp, display_data):
        self.data[msg_id] = (timestamp, display_data)
        self.refresh_table()

    def refresh_table(self):
        self.table.setRowCount(len(self.data))
        for row, (msg_id, (timestamp, display_data)) in enumerate(sorted(self.data.items())):
            # Get message name from dbc if its there
            msg_name = ""
            if dbc:
                try:
                    msg = dbc.get_message_by_frame_id(msg_id)
                    if msg:
                        msg_name = msg.name
                except KeyError:
                    pass 

            id_text = f"0x{msg_id:X}"
            if msg_name:
                id_text += f"\n({msg_name})"


            id_item = QTableWidgetItem(id_text)
            id_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            
            time_item = QTableWidgetItem(str(timestamp))
            time_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            
            data_item = QTableWidgetItem(display_data)
            data_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            self.table.setItem(row, 0, id_item)
            self.table.setItem(row, 1, time_item)
            self.table.setItem(row, 2, data_item)

            self.table.setRowHeight(row, self.fontMetrics().height() * (display_data.count('\n') + 2))

        self.table.resizeColumnToContents(0)
        self.table.resizeColumnToContents(1)
        self.table.horizontalHeader().setStretchLastSection(True)

class RawMessageView(BaseMessageView):
    def process_message(self, msg_id, timestamp, raw_data):
        display_data = " ".join(f"{b:02X}" for b in raw_data)
        self.update_message(msg_id, timestamp, display_data)

class InterpretedMessageView(BaseMessageView):
    def __init__(self):
        super().__init__()
        if dbc is None:
            print("Warning: DBC file not loaded. Interpreted messages will show raw hex.")

    def process_message(self, msg_id, timestamp, raw_data):
        if dbc:
            try:
                message = dbc.get_message_by_frame_id(msg_id)
                if message:
                    decoded = message.decode(raw_data)
                    
                    decoded_str = {k: str(v) for k, v in decoded.items()}
                    
                    max_name_len = max(len(k) for k in decoded_str.keys())
                    max_value_len = max(len(v) for v in decoded_str.values())
                    
                    formatted_lines = []
                    for name, value in decoded_str.items():
                        line = f"{name.ljust(max_name_len)} : {value.rjust(max_value_len)}"
                        formatted_lines.append(line)
                    
                    display_data = "\n".join(formatted_lines)
                else:
                    display_data = " ".join(f"{b:02X}" for b in raw_data)
            except Exception as e:
                display_data = f"Decode error: {e}"
        else:
            display_data = " ".join(f"{b:02X}" for b in raw_data)

        self.update_message(msg_id, timestamp, display_data)

class MainWindow(QMainWindow):
    def __init__(self, serial_port):
        super().__init__()
        self.setWindowTitle("CAN Message Viewer")
        self.resize(1000, 700)

        # Create tab interface
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create message views
        self.raw_view = RawMessageView()
        self.interpreted_view = InterpretedMessageView()
        self.tabs.addTab(self.raw_view, "Raw Messages")
        self.tabs.addTab(self.interpreted_view, "Interpreted Messages")

        # Setup serial receiver
        self.receiver = SerialCANReceiver(serial_port)
        self.receiver.new_message.connect(self.raw_view.process_message)
        self.receiver.new_message.connect(self.interpreted_view.process_message)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # skill issue if this serial port doesnt work on your computer 
    # Idk how to do it for mac or windows 
    # Ubuntu >>
    serial_port = '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10NKEFQ-if00-port0'
    if len(sys.argv) > 1:
        serial_port = sys.argv[1]

    window = MainWindow(serial_port)
    window.show()
    sys.exit(app.exec())