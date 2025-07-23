import struct
import serial
import logging
from config import get_device_config, PRECISION

# This single module replaces both ac_modbus.py and solar_modbus.py.
# It uses a 'device_prefix' ('AC' or 'SOLAR') to determine which configuration
# and parsing logic to apply.

# --- Modbus Constants ---
READ_HOLDING_REGISTERS = 0x04

# --- CRC Calculation ---
# Precomputed CRC16 table for faster calculation.
# This logic is preserved exactly from your original files.
CRC16_TABLE = [0x0000, 0xA001] + [0] * 254
for i in range(1, 256):
    crc = i
    for _ in range(8):
        if crc & 0x0001:
            crc = (crc >> 1) ^ 0xA001
        else:
            crc >>= 1
    CRC16_TABLE[i] = crc

def calculate_crc(data):
    """Calculates the CRC16 for a given Modbus data frame."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        crc = (crc >> 8) ^ CRC16_TABLE[crc & 0xFF]
    return struct.pack('<H', crc)

# --- Unified Modbus Communication ---

def send_modbus_request(ser, function_code, register_address, num_registers, device_prefix):
    """
    Sends a Modbus request to the specified device and reads the response.

    Args:
        ser (serial.Serial): The serial connection object.
        function_code (int): The Modbus function code.
        register_address (int): The starting register address.
        num_registers (int): The number of registers to read.
        device_prefix (str): The device identifier ('AC' or 'SOLAR').

    Returns:
        bytes: The data portion of the response, or None on failure.
    """
    config = get_device_config(device_prefix)
    try:
        # Pack command: Slave Address, Function Code, Start Address, Num Registers
        command = struct.pack('>BBHH', config['slave_address'], function_code, register_address, num_registers)
        command += calculate_crc(command)
        
        ser.write(command)
        
        # Expected response length: Address(1) + Func(1) + ByteCount(1) + Data(2*N) + CRC(2)
        response_length = 5 + 2 * num_registers
        response = ser.read(response_length)
        
        if len(response) < response_length:
            logging.warning(f"[{device_prefix}] Incomplete response received")
            return None
            
        if calculate_crc(response[:-2]) != response[-2:]:
            logging.warning(f"[{device_prefix}] CRC mismatch in response")
            return None
            
        return response[3:-2]  # Extract just the data bytes
    except serial.SerialException as e:
        logging.error(f"[{device_prefix}] Serial communication error: {e}")
        return None
    except Exception as e:
        logging.error(f"[{device_prefix}] Unexpected error in Modbus communication: {e}")
        return None

def read_holding_registers(ser, register_address, num_registers, device_prefix):
    """
    Reads multiple holding registers from a device in a single request.

    Args:
        ser (serial.Serial): The serial connection object.
        register_address (int): The starting register address.
        num_registers (int): The number of registers to read.
        device_prefix (str): The device identifier ('AC' or 'SOLAR').

    Returns:
        tuple: A tuple of unpacked register values, or None on failure.
    """
    try:
        data = send_modbus_request(ser, READ_HOLDING_REGISTERS, register_address, num_registers, device_prefix)
        if not data:
            logging.warning(
                f"[{device_prefix}] Failed to read registers from address "
                f"{register_address} to {register_address + num_registers - 1}"
            )
            return None
        # Unpack the 16-bit values from the response data
        return struct.unpack(f'>{num_registers}H', data)
    except Exception as e:
        logging.error(f"[{device_prefix}] Error reading holding registers: {e}")
        return None

# --- Unified Data Parsing ---

def parse_pzem_data(registers, device_prefix):
    """
    Parses register data into meaningful parameters based on the device type.

    Args:
        registers (tuple): The tuple of register values from read_holding_registers.
        device_prefix (str): The device identifier ('AC' or 'SOLAR').

    Returns:
        dict: A dictionary of the parsed data, or None on failure.
    """
    if not registers:
        logging.warning(f"[{device_prefix}] Cannot parse empty register data.")
        return None

    try:
        if device_prefix == 'AC':
            voltage = round(registers[0] * 0.1, PRECISION)
            # Combine two registers for a 32-bit value
            current = round((registers[2] << 16 | registers[1]) * 0.001, PRECISION)
            power = round((registers[4] << 16 | registers[3]) * 0.1, PRECISION)
            energy = round((registers[6] << 16 | registers[5]), PRECISION)
            frequency = round(registers[7] * 0.1, PRECISION)
            power_factor = round(registers[8] * 0.01, PRECISION)
            
            # Sanity check for AC data
            if power_factor > 1 or frequency > 65: # Allow a small margin for frequency
                logging.warning(f"[{device_prefix}] Invalid data: PF={power_factor}, Freq={frequency}")
                return None
                
            return {
                'voltage': voltage,
                'current': current,
                'power': power,
                'energy': energy,
                'frequency': frequency,
                'power_factor': power_factor
            }

        elif device_prefix == 'SOLAR':
            voltage = round(registers[0] * 0.01, PRECISION)
            current = round(registers[1] * 0.01, PRECISION)
            power = round((registers[3] << 16 | registers[2]) * 0.1, PRECISION)
            energy = round((registers[5] << 16 | registers[4]), PRECISION)
            
            # Sanity check for Solar data
            if power == 0 and current > 0:
                 logging.warning(f"[{device_prefix}] Invalid data: Power is zero but current is not.")
                 # This might be a valid state at night, depending on the device.
                 # Modify this check if needed.
            
            return {
                'voltage': voltage,
                'current': current,
                'power': power,
                'energy': energy
            }
        else:
            logging.error(f"Unknown device prefix for parsing: {device_prefix}")
            return None

    except IndexError:
        logging.error(f"[{device_prefix}] Error parsing data: not enough registers provided.")
        return None
    except Exception as e:
        logging.error(f"[{device_prefix}] An unexpected error occurred during data parsing: {e}")
        return None
