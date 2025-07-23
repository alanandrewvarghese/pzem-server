import struct
import serial
import logging
from config import get_device_config, PRECISION

"""
This module provides functions for Modbus RTU communication to interact with 
PZEM series energy meters. It includes functionalities for calculating CRC, 
sending Modbus requests, reading holding registers, and parsing the received data 
for both AC and DC (SOLAR) meters.
"""

# Modbus function code for reading holding registers
READ_HOLDING_REGISTERS = 0x04

# Pre-computed CRC-16 lookup table for efficient checksum calculation.
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
    """
    Calculates the Modbus CRC-16 checksum for the given data.

    Args:
        data (bytes): The data for which to calculate the CRC.

    Returns:
        bytes: A 2-byte CRC value in little-endian format.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        crc = (crc >> 8) ^ CRC16_TABLE[crc & 0xFF]
    return struct.pack('<H', crc)

def send_modbus_request(ser, function_code, register_address, num_registers, device_prefix):
    """
    Constructs, sends, and validates a Modbus request over a serial connection.

    Args:
        ser (serial.Serial): The initialized serial port object.
        function_code (int): The Modbus function code (e.g., 0x04).
        register_address (int): The starting register address.
        num_registers (int): The number of registers to read.
        device_prefix (str): The device identifier ('AC' or 'SOLAR') to fetch configuration.

    Returns:
        bytes: The raw data payload from the response if successful, otherwise None.
    """
    config = get_device_config(device_prefix)
    try:
        # Pack the command: Slave Address, Function Code, Start Address, Num Registers
        command = struct.pack('>BBHH', config['slave_address'], function_code, register_address, num_registers)
        command += calculate_crc(command)
        
        ser.write(command)
        
        # Calculate expected response length: Address(1) + Func(1) + ByteCount(1) + Data(2*N) + CRC(2)
        response_length = 5 + 2 * num_registers
        response = ser.read(response_length)
        
        if len(response) < response_length:
            logging.warning(f"[{device_prefix}] Incomplete response received")
            return None
            
        if calculate_crc(response[:-2]) != response[-2:]:
            logging.warning(f"[{device_prefix}] CRC mismatch in response")
            return None
            
        # Return only the data payload (removes slave address, func code, and byte count)
        return response[3:-2]
    except serial.SerialException as e:
        logging.error(f"[{device_prefix}] Serial communication error: {e}")
        return None
    except Exception as e:
        logging.error(f"[{device_prefix}] Unexpected error in Modbus communication: {e}")
        return None

def read_holding_registers(ser, register_address, num_registers, device_prefix):
    """
    Reads one or more holding registers from a Modbus device.

    This is a specific implementation of a Modbus read operation using the
    send_modbus_request function.

    Args:
        ser (serial.Serial): The initialized serial port object.
        register_address (int): The starting register address to read from.
        num_registers (int): The number of registers to read.
        device_prefix (str): The device identifier ('AC' or 'SOLAR').

    Returns:
        tuple: A tuple of integers representing the read register values, or None on failure.
    """
    try:
        data = send_modbus_request(ser, READ_HOLDING_REGISTERS, register_address, num_registers, device_prefix)
        if not data:
            logging.warning(
                f"[{device_prefix}] Failed to read registers from address "
                f"{register_address} to {register_address + num_registers - 1}"
            )
            return None
        # Unpack the raw byte data into a tuple of unsigned short integers (H)
        return struct.unpack(f'>{num_registers}H', data)
    except Exception as e:
        logging.error(f"[{device_prefix}] Error reading holding registers: {e}")
        return None

def parse_pzem_data(registers, device_prefix):
    """
    Parses raw register data from PZEM energy meters into a structured dictionary.

    It applies the correct scaling factors based on the device type (AC or SOLAR)
    and performs basic validation on the parsed values.

    Args:
        registers (tuple): A tuple of register values read from the device.
        device_prefix (str): The device identifier ('AC' or 'SOLAR') to determine
                             the parsing logic.

    Returns:
        dict: A dictionary containing the parsed electrical measurements 
              (e.g., voltage, current, power) or None if parsing fails.
    """
    if not registers:
        logging.warning(f"[{device_prefix}] Cannot parse empty register data.")
        return None

    try:
        if device_prefix == 'AC':
            # Data mapping for AC PZEM meter
            voltage = round(registers[0] * 0.1, PRECISION)
            current = round((registers[2] << 16 | registers[1]) * 0.001, PRECISION) # 32-bit value
            power = round((registers[4] << 16 | registers[3]) * 0.1, PRECISION) # 32-bit value
            energy = round((registers[6] << 16 | registers[5]), PRECISION) # 32-bit value
            frequency = round(registers[7] * 0.1, PRECISION)
            power_factor = round(registers[8] * 0.01, PRECISION)
            
            # Basic validation for AC data
            if power_factor > 1 or frequency > 65:
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
            # Data mapping for DC/Solar PZEM meter
            voltage = round(registers[0] * 0.01, PRECISION)
            current = round(registers[1] * 0.01, PRECISION)
            power = round((registers[3] << 16 | registers[2]) * 0.1, PRECISION) # 32-bit value
            energy = round((registers[5] << 16 | registers[4]), PRECISION) # 32-bit value
            
            # Basic validation for DC data
            if power == 0 and current > 0:
                 logging.warning(f"[{device_prefix}] Invalid data: Power is zero but current is not.")
            
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