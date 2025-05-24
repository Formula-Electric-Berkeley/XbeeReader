import serial


ser = serial.Serial(
    port='/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10NKEFQ-if00-port0',
    baudrate=115200,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1
)

def read_frame(ser):
    if ser.read(1) != b'\x7E':
        return None
    length_bytes = ser.read(2)
    length = int.from_bytes(length_bytes, byteorder='big')
    frame_data = ser.read(length)
    if len(frame_data) < length:
        return None
    return frame_data

def parse_explicit_rx(frame_data):
    if frame_data[0] != 0x91:
        return None
    rf_data = frame_data[18:]
    return rf_data.decode('utf-8', errors='replace')


print("Serial initialized")

while True:
    frame = read_frame(ser)
    if frame:
        rf_data = parse_explicit_rx(frame)
        if rf_data:
            print(f"RF Data: {rf_data}")
