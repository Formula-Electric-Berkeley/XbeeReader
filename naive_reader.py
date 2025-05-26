import serial
def read_frame(ser):
    # Wait for start delimiter
    while ser.read(1) != b'\x7E':
        pass
    # Read length (2 bytes)
    length_bytes = ser.read(2)
    if len(length_bytes) < 2:
        return None
    frame_length = (length_bytes[0] << 8) + length_bytes[1]
    # Read the frame data
    frame_data = ser.read(frame_length)
    if len(frame_data) < frame_length:
        return None
    # Read checksum (1 byte)
    checksum = ser.read(1)
    # Return the entire frame (excluding start delimiter and length)
    return frame_data
def extract_rf_data(frame):
    # Frame type 0x91 = Explicit RX Indicator
    if frame[0] != 0x91:
        return None
    # RF data starts at byte 18 (index 17 since Python is 0-based)
    rf_data = frame[18:-1]  # Exclude checksum if included
    return rf_data
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
                    try:
                        print("RF Data (HEX):", rf_data.hex())
                    except Exception as e:
                        print("Error decoding RF data:", e)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        ser.close()
if __name__ == "__main__":
    main()
