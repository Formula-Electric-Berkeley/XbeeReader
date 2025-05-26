import serial
from PySide6.QtCore import QObject, Signal, QThread

class SerialCANReceiver(QObject):
    new_message = Signal(int, int, bytes)  # can_id, timestamp, data_bytes
    
    def __init__(self, serial_port):
        super().__init__()
        self.serial_port = serial_port
        self.serial = None
        self.running = False
        self.thread = QThread()
        self.moveToThread(self.thread)
        self.thread.started.connect(self.run)

    def start(self):
        try:
            self.serial = serial.Serial(
                port=self.serial_port,
                baudrate=230400,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            self.running = True
            self.thread.start()
        except Exception as e:
            print(f"Error opening serial port: {e}")

    def stop(self):
        self.running = False
        if self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()
        if self.serial and self.serial.is_open:
            self.serial.close()

    def run(self):
        print("SerialCANReceiver started")
        while self.running:
            try:
                frame = self.read_frame()
                if frame:
                    rf_data = self.extract_rf_data(frame)
                    if rf_data:
                        result = self.parse_rf_data(rf_data)
                        if result:
                            self.new_message.emit(
                                result['can_id'],
                                result['timestamp'],
                                result['data_bytes']
                            )
            except Exception as e:
                print(f"Error in serial receiver: {e}")
                # Continue running unless it's a critical error

    def read_frame(self):
        """Read a complete frame from the serial port"""
        while self.running:
            # Find frame start
            while self.running:
                byte = self.serial.read(1)
                if byte == b'\x7E':
                    break
            
            # Read length
            length_bytes = self.serial.read(2)
            if len(length_bytes) < 2:
                return None
            
            frame_length = (length_bytes[0] << 8) + length_bytes[1]
            frame_data = self.serial.read(frame_length)
            if len(frame_data) < frame_length:
                return None
            
            _ = self.serial.read(1)  # Discard checksum
            return frame_data

    @staticmethod
    def extract_rf_data(frame):
        """Extract RF data from frame"""
        if len(frame) < 1 or frame[0] != 0x91:
            return None
        if len(frame) < 19:  # Need at least 18 bytes to skip + 1 for checksum
            return None
        return frame[18:-1]  # Skip everything before RF data, discard frame checksum

    @staticmethod
    def parse_rf_data(rf_data):
        """Parse RF data into timestamp, CAN ID, and data bytes"""
        if len(rf_data) != 16:
            return None

        # Extract timestamp (bytes 0-3)
        timestamp = int.from_bytes(rf_data[0:4], byteorder='big')

        # Extract CAN ID (bytes 4-7)
        can_id = int.from_bytes(rf_data[4:8], byteorder='big')

        # Extract data (bytes 8-15)
        data_bytes = rf_data[8:16]

        return {
            "timestamp": timestamp,
            "can_id": can_id,
            "data_bytes": data_bytes
        }