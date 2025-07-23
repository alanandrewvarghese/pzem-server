import os
import serial
import logging
from config import get_device_config
from modbus import read_holding_registers, parse_pzem_data

ac_config = get_device_config('AC')
solar_config = get_device_config('SOLAR')

ac_port = ac_config['serial_port']
solar_port = solar_config['serial_port']

def _read_sensor_data(port, register_count, sensor_type):
    """
    Opens a serial port, reads data from a sensor, and parses it.
    Returns parsed data or None if an error occurs.
    """
    try:
        with serial.Serial(port=port, baudrate=9600, timeout=1) as ser:
            registers = read_holding_registers(ser, 0x0000, register_count, sensor_type)
            if registers:
                return parse_pzem_data(registers, sensor_type)
            return None
    except serial.SerialException as e:
        logging.error(f"Could not open or read from {sensor_type} serial port ({port}): {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred with {sensor_type} sensor ({port}): {e}")
        return None

def get_power_data():
    """
    Fetches power data from both AC and Solar sensors.
    """
    data = {
        'AC': _read_sensor_data(ac_port, 9, 'AC'),
        'SOLAR': _read_sensor_data(solar_port, 6, 'SOLAR')
    }
    return data