import time
import logging
import threading
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException

# Enable logging to see Modbus frames and errors
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

# Initialize variables
value = 0  # Start from 0 for writing holding registers
holding_write_errors = 0  # Errors for holding register writes
coil_write_errors = 0  # Errors for coil writes
poll_delay = 0.25  # Fixed polling time 250 ms
start_time = time.time()
test_duration = 1 * 60  # Run for 3 minutes

# Function to write value to holding register 87 (40087)
def write_holding_register():
    global value, holding_write_errors
    try:
        while time.time() - start_time < test_duration:
            if value > 9999:
                value = 0  # Reset to 0 after 9999
            try:
                response = client.write_register(87, value, slave=1)
                logging.info(f"Writing {value} to register 87 (40087)")
                if response.isError():
                    logging.error(f"Error writing {value} to register 87 (40087)")
                    holding_write_errors += 1
            except ModbusIOException:
                logging.warning("⚠ Timeout! No response from slave for register 87 (40087)")
                holding_write_errors += 1
            
            time.sleep(poll_delay)
            value += 1
    except KeyboardInterrupt:
        print("Holding register write stopped by user.")

# Function to write ON/OFF states to coils (FC15 - Multiple Coil Write)
def write_coils():
    global coil_write_errors
    coils = [24, 25, 26, 27]  # Coil addresses
    try:
        while time.time() - start_time < test_duration:
            try:
                # Turn all coils ON for 1 second
                response = client.write_coils(coils[0], [True] * len(coils), slave=1)
                logging.info("Turning all coils ON [24-28]")
                if response.isError():
                    logging.error("Error writing coils ON [24-28]")
                    coil_write_errors += 1
                time.sleep(1)  # ON duration
                
                # Turn all coils OFF for 1 second
                response = client.write_coils(coils[0], [False] * len(coils), slave=1)
                logging.info("Turning all coils OFF [24-28]")
                if response.isError():
                    logging.error("Error writing coils OFF [24-28]")
                    coil_write_errors += 1
                time.sleep(1)  # OFF duration
            
            except ModbusIOException:
                logging.warning("⚠ Timeout! No response from slave for coils [24-28]")
                coil_write_errors += 1
    except KeyboardInterrupt:
        print("Coil write stopped by user.")

# Start both threads simultaneously
if client.connect():
    print("Connected to Modbus RTU slave.")
    thread1 = threading.Thread(target=write_holding_register)
    thread2 = threading.Thread(target=write_coils)
    
    thread1.start()
    thread2.start()
    
    thread1.join()
    thread2.join()
    
    client.close()
    
    print("\n===== TEST COMPLETED =====")
    print(f"Holding register write errors: {holding_write_errors}")
    print(f"Coil write errors: {coil_write_errors}")
    print(f"Final poll time: {poll_delay}s")
    print(f"Response timeout: {client.comm_params.timeout_connect}s")
    print("==========================")
else:
    print("Failed to connect to Modbus RTU slave.")