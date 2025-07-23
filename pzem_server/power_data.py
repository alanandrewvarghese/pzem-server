import os
import serial
import logging
from modbus import read_holding_registers, parse_pzem_data


ac_port = os.getenv('AC_PORT', '/dev/ttyUSB1')
solar_port = os.getenv('SOLAR_PORT', '/dev/ttyUSB0')

def get_power_data():
    data = {}

    try:
        ser_ac = serial.Serial(port=ac_port, baudrate=9600, timeout=1)
        ac_registers = read_holding_registers(ser_ac, 0x0000, 9, 'AC')
        if ac_registers:
            ac_data = parse_pzem_data(ac_registers, 'AC')
            data['AC'] = ac_data
        ser_ac.close()
    except serial.SerialException as e:
        data['AC'] = "Error: Could not open AC serial port"
        logging.error(f"Could not open AC serial port: {e}")


    try:
        ser_solar = serial.Serial(port=solar_port, baudrate=9600, timeout=1)
        solar_registers = read_holding_registers(ser_solar, 0x0000, 6, 'SOLAR')
        if solar_registers:
            solar_data = parse_pzem_data(solar_registers, 'SOLAR')
            data['SOLAR'] = solar_data
        ser_solar.close()
    except serial.SerialException as e:
        data['SOLAR'] = "Error: Could not open Solar serial port"
        logging.error(f"Could not open Solar serial port: {e}")

    return data
