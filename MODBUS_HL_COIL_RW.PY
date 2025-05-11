import time
import logging
import random
import threading
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException

# Enable logging to see Modbus frames and errors
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Modbus RTU settings with response timeout of 1 second
client = ModbusSerialClient(
    port='COM5',  # Set your correct COM port
    baudrate=19200,
    stopbits=2,
    parity='N',
    bytesize=8,
    timeout=1  # Fixed response timeout of 1 second
)

# Initialize variables
value = 0  # Start from 0 for writing holding registers
error_count = 0  # Count of errors to monitor
poll_delay = 0.05  # Poll time set to 50 ms
start_time = time.time()  # Start time of the test
test_duration = 1 * 60  # Run for 10 minutes

# Function to write values to holding registers
def write_holding_registers():
    global value, error_count  
    try:
        while time.time() - start_time < test_duration:  # Run for 10 minutes
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
                        error_count += 1  # Increment error count
                    else:
                        logging.info(f"Successfully wrote {value} to register {reg} (400{reg})")

                except ModbusIOException:
                    logging.warning(f"⚠ Timeout! No response from slave for register {reg} (400{reg})")
                    error_count += 1  # Increment error count

                time.sleep(poll_delay)  # 50 ms delay between writes

            # Increment value
            value += 1

    except KeyboardInterrupt:
        print("Holding register write stopped by user.")

# Function to write random ON/OFF states to coils
def write_coils():
    global error_count  
    try:
        while time.time() - start_time < test_duration:  # Run for 10 minutes
            for coil in range(24, 29):  # Coils 24 to 28 (00024 to 00028)
                # Randomly choose ON (True) or OFF (False)
                coil_value = random.choice([True, False])

                try:
                    # Write a coil (Function Code 5)
                    response = client.write_coil(coil, coil_value, slave=1)

                    # Debug logging will capture sent request
                    logging.info(f"Writing {coil_value} to coil {coil} (000{coil})")

                    # Check response for errors or timeout
                    if response.isError():
                        logging.error(f"Error writing {coil_value} to coil {coil} (000{coil})")
                        error_count += 1  # Increment error count
                    else:
                        logging.info(f"Successfully wrote {coil_value} to coil {coil} (000{coil})")

                except ModbusIOException:
                    logging.warning(f"⚠ Timeout! No response from slave for coil {coil} (000{coil})")
                    error_count += 1  # Increment error count

                time.sleep(poll_delay)  # 50 ms delay between writes

    except KeyboardInterrupt:
        print("Coil write stopped by user.")

# Start both threads simultaneously
if client.connect():
    print("Connected to Modbus RTU slave.")

    # Create threads for coil and register writing
    thread1 = threading.Thread(target=write_holding_registers)
    thread2 = threading.Thread(target=write_coils)

    # Start both threads
    thread1.start()
    thread2.start()

    # Wait for both threads to complete (10 minutes)
    time.sleep(test_duration)

    # Stop threads after 10 minutes
    thread1.join()
    thread2.join()

    # Clean up after threads finish
    client.close()

    # Print test results
    print("\n===== TEST COMPLETED =====")
    print(f"Total errors occurred: {error_count}")
    print(f"Final poll time: {poll_delay}s")
    print(f"Final response timeout: {client.comm_params.timeout_connect}s")
    print("==========================")

else:
    print("Failed to connect to Modbus RTU slave.")
