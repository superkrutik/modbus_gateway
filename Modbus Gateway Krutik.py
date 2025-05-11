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
RTU_SLAVE_ID = 1
SERIAL_PORT = "COM5"  
BAUD_RATE = 9600
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
                    logging.info("Successfully wrote values to RTU device")

            except ModbusException as e:
                logging.error(f"Modbus exception writing to RTU device: {e}")
            except Exception as e:
                logging.error(f"General error writing to RTU device: {e}")

# --- Create Modbus TCP Slave Context ---
store = GatewaySlaveContext(
    di=ModbusSequentialDataBlock(0, [0] * 100),
    co=ModbusSequentialDataBlock(0, [0] * 100),
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
            logging.debug("Sending Modbus RTU Request...")  # Debug level for frequent logs
            rr = rtu_client.read_holding_registers(
                address=0,
                count=HOLDING_REGISTERS_COUNT,
                slave=RTU_SLAVE_ID
            )

            # Check for various error conditions
            if rr is None:
                logging.error("No response received from RTU slave (None returned)")
                continue  # Go to the next iteration

            if rr.isError():
                logging.error(f"Modbus error response from RTU slave: {rr}")
                continue

            if not hasattr(rr, 'registers'):
                logging.error(f"Invalid response format: {rr}")
                continue

            # Update the TCP server's data store
            store.setValues(3, 0, rr.registers)
            logging.info(f"Holding Registers Updated: {rr.registers}")

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