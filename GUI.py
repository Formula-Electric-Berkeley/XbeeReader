import sys
import serial
import cantools
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QTabWidget, QHeaderView, QPushButton, QHBoxLayout
)


# Load DBC file
try:
    dbc = cantools.database.load_file('FEB_CAN.dbc')
    print("Loaded DBC file with messages:")
    for msg in dbc.messages:
        print(f"ID: 0x{msg.frame_id:03X}, Name: {msg.name}")
except Exception as e:
    print(f"Error loading DBC file: {e}")
    dbc = None

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

        message_str = self.parse_xbee_frame(frame)
        if not message_str:
            return

        can_data = self.parse_can_message(message_str)
        if can_data:
            self.new_message.emit(*can_data)

class BaseMessageView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.data = {}  # msg_id: (timestamp, display_data)
        self.sorted_ids = []  # Maintain our own sorted list

    def setup_ui(self):
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        
        # Create button layout
        button_layout = QHBoxLayout()
        self.sort_button = QPushButton("Sort by CAN ID")
        self.sort_button.clicked.connect(self.sort_by_id)
        button_layout.addWidget(self.sort_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Create table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Timestamp (ms)", "Latest Data"])
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        
        # Enable drag and drop for rows
        self.table.setDragEnabled(True)
        self.table.setDragDropMode(QTableWidget.InternalMove)
        self.table.setDropIndicatorShown(True)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Configure font and appearance
        font = self.table.font()
        font.setFamily("Courier New")
        font.setPointSize(10)
        self.table.setFont(font)
        
        # Configure table behavior
        self.table.setTextElideMode(Qt.ElideNone)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        
        # Configure header
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setStretchLastSection(True)
        
        # Style
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #c0c0c0;
            }
            QTableWidget::item {
                padding-top: 8px;
                padding-bottom: 8px;
                border: none;
            }
        """)
        
        main_layout.addWidget(self.table)

    def update_message(self, msg_id, timestamp, display_data):
        # If this is a new message, add it to our sorted list
        if msg_id not in self.data:
            self.sorted_ids.append(msg_id)
            self.sorted_ids.sort()
        
        self.data[msg_id] = (timestamp, display_data)
        self.refresh_table()

    def refresh_table(self):
        # Disable sorting temporarily to allow manual rearrangement
        self.table.setSortingEnabled(False)
        
        self.table.setRowCount(len(self.sorted_ids))
        
        for row, msg_id in enumerate(self.sorted_ids):
            timestamp, display_data = self.data[msg_id]
            
            # Format ID with name (if available)
            id_text = f"0x{msg_id:03X}"
            if dbc:
                try:
                    msg = dbc.get_message_by_frame_id(msg_id)
                    if msg:
                        id_text += f"\n{msg.name}"
                except KeyError:
                    pass

            # Create items
            id_item = QTableWidgetItem(id_text)
            time_item = QTableWidgetItem(str(timestamp))
            data_item = QTableWidgetItem(display_data)
            
            # Configure items
            for item in (id_item, time_item, data_item):
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setToolTip(item.text())
                item.setData(Qt.UserRole, msg_id)  # Store CAN ID for sorting

            # Add to table
            self.table.setItem(row, 0, id_item)
            self.table.setItem(row, 1, time_item)
            self.table.setItem(row, 2, data_item)

            # Calculate row height
            line_count = max(1, display_data.count('\n') + 1, id_text.count('\n') + 1)
            self.table.setRowHeight(row, self.fontMetrics().height() * line_count + 12)

        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

    def sort_by_id(self):
        """Sort messages by CAN ID and refresh the table"""
        self.sorted_ids.sort()
        self.refresh_table()

    def get_current_order(self):
        """Get current order of message IDs based on table rows"""
        current_order = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                msg_id = item.data(Qt.UserRole)
                current_order.append(msg_id)
        return current_order

    def dropEvent(self, event):
        """Handle row reordering"""
        super().dropEvent(event)
        # Update our sorted_ids to match the new order
        self.sorted_ids = self.get_current_order()

class RawMessageView(BaseMessageView):
    def process_message(self, msg_id, timestamp, raw_data):
        display_data = " ".join(f"{b:02X}" for b in raw_data)
        self.update_message(msg_id, timestamp, display_data)

class InterpretedMessageView(BaseMessageView):
    def __init__(self):
        super().__init__()
        if dbc is None:
            print("Warning: No DBC file - showing raw data")

    def process_message(self, msg_id, timestamp, raw_data):
        if not dbc:
            display_data = " ".join(f"{b:02X}" for b in raw_data)
        else:
            try:
                msg = dbc.get_message_by_frame_id(msg_id)
                if msg:
                    decoded = msg.decode(raw_data)
                    max_name_len = max(len(k) for k in decoded.keys())
                    formatted = []
                    for name, value in decoded.items():
                        line = f"{name.ljust(max_name_len)} : {value}"
                        formatted.append(line)
                    display_data = "\n".join(formatted)
                else:
                    display_data = " ".join(f"{b:02X}" for b in raw_data)
            except Exception as e:
                display_data = f"Decode error: {e}"

        self.update_message(msg_id, timestamp, display_data)

class MainWindow(QMainWindow):
    def __init__(self, serial_port):
        super().__init__()
        self.setWindowTitle("CAN Message Viewer")
        self.resize(1200, 800)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.raw_view = RawMessageView()
        self.interpreted_view = InterpretedMessageView()
        self.tabs.addTab(self.raw_view, "Raw Messages")
        self.tabs.addTab(self.interpreted_view, "Interpreted Messages")

        self.receiver = SerialCANReceiver(serial_port)
        self.receiver.new_message.connect(self.raw_view.process_message)
        self.receiver.new_message.connect(self.interpreted_view.process_message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    serial_port = '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10NKEFQ-if00-port0'
    if len(sys.argv) > 1:
        serial_port = sys.argv[1]

    window = MainWindow(serial_port)
    window.show()
    sys.exit(app.exec())
