import serial

def read_frame(ser):
    while ser.read(1) != b'\x7E':
        pass
    length_bytes = ser.read(2)
    if len(length_bytes) < 2:
        return None
    frame_length = (length_bytes[0] << 8) + length_bytes[1]
    frame_data = ser.read(frame_length)
    if len(frame_data) < frame_length:
        return None
    _ = ser.read(1)  # Discard the checksum
    return frame_data

def extract_rf_data(frame):
    if frame[0] != 0x91:
        return None
    rf_data = frame[18:-1]  # Skip everything before RF data, discard frame checksum
    return rf_data

def parse_rf_data(rf_data):
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


def main():
    ser = serial.Serial(
        port='/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10NKEFQ-if00-port0',
        baudrate=230400,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1
    )
    try:
        print("Listening for frames...")
        while True:
            frame = read_frame(ser)
            if frame:
                rf_data = extract_rf_data(frame)
                if rf_data:
                    result = parse_rf_data(rf_data)
                    if result:
                        print(f"Timestamp: {result['timestamp']} | CAN ID: 0x{result['can_id']:08X} | Data: {result['data_bytes'].hex()}")

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
