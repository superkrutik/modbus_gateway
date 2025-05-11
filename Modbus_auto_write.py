import time
import logging
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException

# Enable logging to see Modbus frames
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Modbus RTU settings
client = ModbusSerialClient(
    port='COM5',  # Set your correct COM port
    baudrate=19200,
    stopbits=2,
    parity='N',
    bytesize=8,
    timeout=1  # 1000ms timeout
)

# Initialize counter
value = 0  # Start from 0

if client.connect():
    print("Connected to Modbus RTU slave.")

    try:
        while True:  # Run continuously
            for reg in range(87, 91):  # Registers 87 to 90 (40087 to 40090)
                if value > 9999:
                    value = 0  # Reset to 0 after 9999

                try:
                    # Write a single register (Function Code 6)
                    response = client.write_register(reg, value, slave=1)

                    # Debug logging will capture sent request
                    logging.info(f"Writing {value} to register {reg} (400{reg})")

                    # Check response for errors or timeout
                    if response.isError():
                        logging.error(f"Error writing {value} to register {reg} (400{reg})")
                    else:
                        logging.info(f"Successfully wrote {value} to register {reg} (400{reg})")

                except ModbusIOException:
                    logging.warning(f"⚠ Timeout! No response from slave for register {reg} (400{reg})")

                time.sleep(0.5)  # 500ms delay between writes

            # Increment value
            value += 1

    except KeyboardInterrupt:
        print("Stopped by user.")

    finally:
        client.close()
        print("Connection closed.")
else:
    print("Failed to connect to Modbus RTU slave.")
