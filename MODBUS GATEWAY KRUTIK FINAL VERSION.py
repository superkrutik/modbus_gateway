import sys
import time
import threading
import logging
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException, ModbusIOException


# Configuration
HOLDING_REGISTERS_COUNT = 94
INPUT_REGISTERS_COUNT = 5  # Example value, adjust as needed
COIL_COUNT = 28 # Add a coil count
RTU_SLAVE_ID = 1
SERIAL_PORT = "COM5"
BAUD_RATE = 19200
STOP_BITS = 2
PARITY = 'N'
TCP_SERVER_ADDRESS = "192.168.1.212"  # Krutik gateway's IP address
TCP_SERVER_PORT = 502
POLLING_INTERVAL = 0.5
RTU_TIMEOUT = 2.0


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.DEBUG
)

# --- Initialize RTU Client ---
rtu_client = ModbusSerialClient(
    port=SERIAL_PORT,
    baudrate=BAUD_RATE,
    parity=PARITY,
    stopbits=STOP_BITS,
    bytesize=8,
    timeout=RTU_TIMEOUT,
)

if not rtu_client.connect():
    logging.error(f"Error: Could not connect to Modbus RTU Slave on {SERIAL_PORT}.")
    sys.exit(1)

logging.info(f"Connected to Modbus RTU Slave on {SERIAL_PORT} (ID {RTU_SLAVE_ID})")

# --- Custom Modbus Slave Context ---
class GatewaySlaveContext(ModbusSlaveContext):
    def __init__(self, di=None, co=None, hr=None, ir=None, rtu_client=None):
        super().__init__(di=di, co=co, hr=hr, ir=ir)
        self.rtu_client = rtu_client

    def setValues(self, fx, address, values):
        super().setValues(fx, address, values)

        # Handle writes to holding registers (function code 3 is read holding, 6 is single write, 16 is multiple write)
        if (fx == 6 or fx == 16) and self.rtu_client:
            try:
                logging.info(f"Forwarding write to RTU device: address={address}, values={values}, function code = {fx}")
                if fx == 6: #Single Register
                    result = self.rtu_client.write_register(
                        address=address,
                        value=values[0],  # write_register takes a single value
                        slave=RTU_SLAVE_ID
                    )
                if fx == 16: #Multiple Register
                    result = self.rtu_client.write_registers(
                        address=address,
                        values=values,
                        slave=RTU_SLAVE_ID
                    )
                # Check for Modbus exception responses
                if result.isError():
                    logging.error(f"Modbus error response from RTU device: {result}")
                else:
                    logging.info("Successfully wrote holding register(s) to RTU device")

            except ModbusException as e:
                logging.error(f"Modbus exception writing to RTU device: {e}")
            except Exception as e:
                logging.error(f"General error writing to RTU device: {e}")

        # Handle writes to coils (function code 5 is single coil write)
        if fx == 5 and self.rtu_client:
            try:
                logging.info(f"Forwarding single coil write to RTU device: address={address}, value={values[0]}")
                result = self.rtu_client.write_coil(
                    address=address,
                    value=values[0],  # write_coil takes a single boolean value
                    slave=RTU_SLAVE_ID
                )
                if result.isError():
                    logging.error(f"Modbus error response writing coil to RTU device: {result}")
                else:
                    logging.info("Successfully wrote coil to RTU device")
            except ModbusException as e:
                logging.error(f"Modbus exception writing coil to RTU device: {e}")
            except Exception as e:
                logging.error(f"General error writing coil to RTU device: {e}")

        #Handle multiple coil writes (function code 15)
        if fx == 15 and self.rtu_client:
            try:
                logging.info(f"Forwarding multiple coil write to RTU device: address={address}, values={values}")
                result = self.rtu_client.write_coils(  # Note: write_coils, plural
                    address = address,
                    values = values,
                    slave = RTU_SLAVE_ID
                )
                if result.isError():
                    logging.error(f"Modbus error response from RTU device when writing coils: {result}")
                else:
                    logging.info(f"Successfully wrote coils to RTU device")
            except ModbusException as e:
                logging.error(f"Modbus Exception while writing coils to RTU Device {e}")
            except Exception as e:
                logging.error(f"General error when writing coils to RTU Device: {e}")

# --- Create Modbus TCP Slave Context ---
store = GatewaySlaveContext(
    di=ModbusSequentialDataBlock(0, [0] * 100),
    co=ModbusSequentialDataBlock(0, [0] * COIL_COUNT),  # Initialize coils
    hr=ModbusSequentialDataBlock(0, [0] * 100),
    ir=ModbusSequentialDataBlock(0, [0] * 100),
    rtu_client=rtu_client
)
context = ModbusServerContext(slaves={1: store}, single=False)

# --- Modbus Gateway (Polling Loop) ---
def modbus_gateway():
    while True:
        try:
            # Read holding registers from RTU slave
            logging.debug("Sending Modbus RTU Request for Holding Registers...")
            rr_holding = rtu_client.read_holding_registers(
                address=0,
                count=HOLDING_REGISTERS_COUNT,
                slave=RTU_SLAVE_ID
            )

            # Read input registers from RTU slave
            logging.debug("Sending Modbus RTU Request for Input Registers...")
            rr_input = rtu_client.read_input_registers(
                address=0,
                count=INPUT_REGISTERS_COUNT,
                slave=RTU_SLAVE_ID
            )

            # Read coils from RTU slave
            logging.debug("Sending Modbus RTU Request for Coils...")
            rr_coils = rtu_client.read_coils(
                address=0,
                count=COIL_COUNT,  # Read all the coils we have defined
                slave=RTU_SLAVE_ID
            )


            # --- Error Handling and Updating for Holding Registers ---
            if rr_holding is None:
                logging.error("No response received from RTU slave for Holding Registers (None returned)")
            elif rr_holding.isError():
                logging.error(f"Modbus error response from RTU slave for Holding Registers: {rr_holding}")
            elif not hasattr(rr_holding, 'registers'):
                logging.error(f"Invalid response format for Holding Registers: {rr_holding}")
            else:
                # Update the TCP server's data store for holding registers
                store.setValues(3, 0, rr_holding.registers)
                logging.info(f"Holding Registers Updated: {rr_holding.registers}")


            # --- Error Handling and Updating for Input Registers ---
            if rr_input is None:
                logging.error("No response received from RTU slave for Input Registers (None returned)")
            elif rr_input.isError():
                logging.error(f"Modbus error response from RTU slave for Input Registers: {rr_input}")
            elif not hasattr(rr_input, 'registers'):
                logging.error(f"Invalid response format for Input Registers: {rr_input}")
            else:
                # Update the TCP server's data store for input registers
                store.setValues(4, 0, rr_input.registers)
                logging.info(f"Input Registers Updated: {rr_input.registers}")


            # --- Error Handling and Updating for Coils ---
            if rr_coils is None:
                logging.error("No response received from RTU slave for Coils (None returned)")
            elif rr_coils.isError():
                logging.error(f"Modbus error response from RTU slave for Coils: {rr_coils}")
            elif not hasattr(rr_coils, 'bits'):  # Corrected attribute name
                logging.error(f"Invalid response format for Coils: {rr_coils}")
            else:
                # Update the TCP server's data store for coils
                store.setValues(1, 0, rr_coils.bits)  # Function code 1 for Coils
                logging.info(f"Coils Updated: {rr_coils.bits}")


        except ModbusIOException as e:
            logging.error(f"Modbus I/O error: {e}")
        except ModbusException as e:
            logging.error(f"Modbus exception during read: {e}")
        except Exception as e:
            logging.error(f"General error in gateway loop: {e}")

        time.sleep(POLLING_INTERVAL)

# --- Start Threads ---
gateway_thread = threading.Thread(target=modbus_gateway, daemon=True)
gateway_thread.start()

# --- Start Modbus TCP Server ---
logging.info(f"Starting Modbus TCP Server on {TCP_SERVER_ADDRESS}:{TCP_SERVER_PORT}...")
StartTcpServer(context=context, address=(TCP_SERVER_ADDRESS, TCP_SERVER_PORT))
# The StartTcpServer function blocks, so no need for an infinite loop here.