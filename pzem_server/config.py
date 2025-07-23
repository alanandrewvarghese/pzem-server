import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

def get_device_config(device_prefix):
    """
    Returns a configuration for a specific device (e.g., 'AC' or 'SOLAR').
    
    Args:
        device_prefix (str): The prefix for the environment variables ('AC' or 'SOLAR').
    """
    # Set default serial port and slave address based on prefix
    default_port = '/dev/ttyUSB0' if device_prefix == 'AC' else '/dev/ttyUSB1'
    default_slave_address = '1' if device_prefix == 'AC' else '2'

    config = {
        'serial_port': os.getenv(f'{device_prefix}_SERIAL_PORT', default_port),
        'baud_rate': int(os.getenv(f'{device_prefix}_BAUD_RATE', 9600)),
        'serial_timeout': int(os.getenv(f'{device_prefix}_SERIAL_TIMEOUT', 1)),
        'slave_address': int(os.getenv(f'{device_prefix}_SLAVE_ADDRESS', default_slave_address), 16)
    }
    
    return config

# Precision for both systems
PRECISION = int(os.getenv('PRECISION', 4))

# --- How to use the new function ---
# ac_config = get_device_config('AC')
# solar_config = get_device_config('SOLAR')

# print("AC Config:", ac_config)
# print("Solar Config:", solar_config)