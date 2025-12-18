import asyncio
from bleak import BleakClient, BleakScanner
from .daly_bms import DalyBMS
from .logger import get_logger

# UUIDs for Daly BMS
# Based on common findings:
# Service: 0000ff00-0000-1000-8000-00805f9b34fb
# Write (TX for us): 0000fff2-0000-1000-8000-00805f9b34fb (was handle 15)
# Notify (RX for us): 0000fff1-0000-1000-8000-00805f9b34fb (was handle 17)

UUID_SERVICE = "0000fff0-0000-1000-8000-00805f9b34fb"
UUID_NOTIFY = "0000fff1-0000-1000-8000-00805f9b34fb"
UUID_WRITE = "0000fff2-0000-1000-8000-00805f9b34fb"

class DalyBMSBluetooth(DalyBMS):
    def __init__(self, mac_address, logger=None, adapter=None, request_retries=3):
        """
        :param request_retries: How often read requests should get repeated in case that they fail (Default: 3).
        :param logger: Python Logger object for output (Default: None)
        """
        self.logger = logger or get_logger()
        super().__init__(request_retries=request_retries, address=8, logger=self.logger)
        self.mac_address = mac_address
        self.adapter = adapter
        self.request_retries = request_retries
        # adapter arg is deprecated in newer bleak, removed usage
        self.client = BleakClient(mac_address)
        self.response_cache = {}
        self.status = None

    async def connect(self, timeout=20.0, retries=3):
        """
        Connect to the Bluetooth device using BleakClient and start notifications.
        """
        if not self.client or not self.client.is_connected:
            for attempt in range(retries):
                try:
                    self.logger.info(f"Scanning for {self.mac_address} (Attempt {attempt + 1}/{retries})...")
                    device = await BleakScanner.find_device_by_address(self.mac_address, timeout=20.0)
                    if not device:
                        self.logger.warning(f"Device {self.mac_address} not found during scan")
                        if attempt < retries - 1:
                            await asyncio.sleep(5.0)
                            continue
                        else:
                            raise RuntimeError(f"Device {self.mac_address} not found after {retries} scan attempts")

                    self.logger.info(f"Connecting to {self.mac_address}...")
                    # Re-initialize client with the found device object to ensure proper DBus path
                    self.client = BleakClient(device)
                    await self.client.connect(timeout=30.0)
                    self.logger.info(f"Bluetooth connected to {self.mac_address}")
                    
                    # Small delay to stabilize connection
                    await asyncio.sleep(1.0)

                    # Start notifications on the UUID
                    self.logger.debug(f"Starting notifications on {UUID_NOTIFY}...")
                    await self.client.start_notify(UUID_NOTIFY, self._notification_callback)
                    self.logger.info(f"Notifications started on {UUID_NOTIFY}")
                    return
                except Exception as e:
                    import traceback
                    self.logger.warning(f"Bluetooth connection attempt {attempt + 1} failed: {e}")
                    self.logger.debug(traceback.format_exc())
                    # Ensure we are disconnected before retrying
                    try:
                        if self.client:
                            await self.client.disconnect()
                    except:
                        pass
                    
                    if attempt < retries - 1:
                        await asyncio.sleep(2.0)
                    else:
                        self.logger.error(f"Bluetooth connection failed after {retries} attempts")
                        raise


    async def disconnect(self):
        """
        Disconnect from the Bluetooth device
        """
        self.logger.info("Bluetooth Disconnecting")
        await self.client.disconnect()
        self.logger.info("Bluetooth Disconnected")

    async def _read_request(self, command, extra="", max_responses=1, return_list=False, retries=5):
        self.logger.debug(f"Sending command {command} with max responses {max_responses}")
        for attempt in range(retries):
            try:
                responses = await self._read(command, extra=extra, max_responses=max_responses)
                if not responses:
                    self.logger.warning(f"No response received for command {command} (attempt {attempt + 1}/{retries})")
                    continue
                if isinstance(responses, list):
                    for response in responses:
                        self.logger.debug(f"Received response for command {command}: {response.hex()}")
                        if len(response) not in [13, 26]:
                            pass
                    return responses if return_list or max_responses > 1 else responses[-1] if responses else None
                else:
                    self.logger.debug(f"Received response for command {command}: {responses.hex()}")
                    if len(responses) not in [13, 26]:
                        pass
                    return [responses] if return_list or max_responses > 1 else responses
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout while waiting for {command} response (attempt {attempt + 1}/{retries})")
            except Exception as e:
                self.logger.error(f"Error for command {command}: {e}")
                break
        self.logger.error(f"{command} failed after {retries} tries")
        # After all retries failed, disconnect and raise to trigger restart
        try:
            await self.disconnect()
            self.logger.info("Bluetooth connection closed after repeated failures. Restarting main loop.")
        except Exception as e:
            self.logger.error(f"Error during forced disconnect: {e}")
        raise RuntimeError(f"No response for command {command} after {retries} attempts. Restarting.")

    async def _read(self, command, extra="", max_responses=1):
        self.logger.debug("-- %s ------------------------" % command)
        self.response_cache[command] = {"queue": [], "future": asyncio.Future(), "max_responses": max_responses,
                                        "done": False}
        message_bytes = self._format_message(command, extra=extra)
        result = await self._async_char_write(command, message_bytes)
        self.logger.debug("got %s" % result)
        if not result:
            return False
        return result

    def _notification_callback(self, sender, data):
        # NOTE: bleak 0.19+ callback signature is (sender: BleakGATTCharacteristic, data: bytearray)
        # Previous was (handle: int, data: bytearray)
        
        # Get handle from sender if possible, or just ignore it
        handle = sender.handle if hasattr(sender, 'handle') else sender
        
        self.logger.debug(f"[notification_callback] handle={handle}, data={data.hex()}, len={len(data)}")
        responses = []
        if len(data) == 13:
            crc_calc = int.from_bytes(self._calc_crc(data[:12]), 'little')
            self.logger.debug(f"[notification_callback] 13 bytes: CRC calc={crc_calc}, CRC recv={data[12]}")
            if crc_calc != data[12]:
                self.logger.info("Return from BMS: CRC wrong")
                return
            responses.append(data)
        elif len(data) == 26:
            crc1 = int.from_bytes(self._calc_crc(data[:12]), 'little')
            crc2 = int.from_bytes(self._calc_crc(data[13:25]), 'little')
            self.logger.debug(f"[notification_callback] 26 bytes: CRC1 calc={crc1}, CRC1 recv={data[12]}, CRC2 calc={crc2}, CRC2 recv={data[25]}")
            if (crc1 != data[12]) or (crc2 != data[25]):
                self.logger.info("Return from BMS: CRC wrong")
                return
            responses.append(data[:13])
            responses.append(data[13:])
        elif len(data) == 39:
            self.logger.debug("[notification_callback] 39 bytes: splitting into three 13-byte packets")
            for i in range(0, 39, 13):
                packet = data[i:i+13]
                if len(packet) == 13 and packet[0] == 0xA5 and packet[2] == 0x95:
                    crc_calc = int.from_bytes(self._calc_crc(packet[:12]), 'little')
                    self.logger.debug(f"[notification_callback] packet offset={i}, CRC calc={crc_calc}, CRC recv={packet[12]}, packet={packet.hex()}")
                    if crc_calc == packet[12]:
                        responses.append(packet)
                    else:
                        self.logger.info(f"CRC wrong for packet: {packet.hex()}")
                else:
                    self.logger.debug(f"Skipping invalid packet at offset {i}: {packet.hex()}")
        elif len(data) == 200:
            self.logger.debug("[notification_callback] 200 bytes: splitting into 13-byte packets")
            for i in range(0, len(data), 13):
                if i + 13 <= len(data) and data[i] == 0xA5 and data[i + 2] == 0x95:
                    packet = data[i:i + 13]
                    crc_calc = int.from_bytes(self._calc_crc(packet[:12]), 'little')
                    self.logger.debug(f"[notification_callback] packet offset={i}, CRC calc={crc_calc}, CRC recv={packet[12]}, packet={packet.hex()}")
                    if crc_calc == packet[12]:
                        responses.append(packet)
                    else:
                        self.logger.info(f"CRC wrong for packet: {packet.hex()}")
                else:
                    self.logger.debug(f"Skipping invalid packet at offset {i}: {data[i:i + 13].hex()}")
        else:
            self.logger.debug(f"[notification_callback] Unhandled data length: {len(data)}")
            return
            
        for response_bytes in responses:
            command = response_bytes[2:3].hex()
            self.logger.debug(f"[notification_callback] Parsed command: {command}, response_bytes={response_bytes.hex()}")
            if self.response_cache.get(command, {}).get("done", True):
                self.logger.debug(f"[notification_callback] Skipping response for {command}, done - received more data than expected")
                return
            self.response_cache[command]["queue"].append(response_bytes[4:-1])
            self.logger.debug(f"[notification_callback] Appended response_bytes[4:-1]={response_bytes[4:-1].hex()} to queue for command {command}")
            if len(self.response_cache[command]["queue"]) >= self.response_cache[command]["max_responses"]:
                self.response_cache[command]["done"] = True
                self.response_cache[command]["future"].set_result(self.response_cache[command]["queue"])
                self.logger.debug(f"[notification_callback] Set future result for command {command}")

    async def _async_char_write(self, command, value):
        if not self.client.is_connected:
            self.logger.info("Connecting...")
            await self.client.connect()
        
        # Write to the WRITE UUID
        await self.client.write_gatt_char(UUID_WRITE, value)
        
        self.logger.debug("Waiting...")
        try:
            result = await asyncio.wait_for(self.response_cache[command]["future"], 15)  # Increased to 15s
        except asyncio.TimeoutError:
            self.logger.warning("Timeout while waiting for %s response" % command)
            return False
        self.logger.debug("got %s" % result)
        return result

    # wrap all sync functions so that they can be awaited
    async def get_soc(self):
        response_data = await self._read_request("90")
        return super().get_soc(response_data=response_data)

    async def get_cell_voltage_range(self):
        response_data = await self._read_request("91")
        return super().get_cell_voltage_range(response_data=response_data)

    async def get_alarm_voltages(self, pack_cell=None):
        if pack_cell == "Cell":
            cmd = "59"
        elif pack_cell == "Pack":
            cmd = "5a"
        else:
            self.logger.error("Wrong Call to alarm_voltages, missing Pack or Cell")
            return None
        response_data = await self._read_request(cmd)
        return super().get_alarm_voltages(response_data=response_data, pack_cell=pack_cell)

    async def get_temperature_range(self):
        response_data = await self._read_request("92")
        return super().get_temperature_range(response_data=response_data)

    async def get_hw_sw_version(self, hard_soft):
        if hard_soft == "Hardware":
            cmd = "63"
        elif hard_soft == "Software":
            cmd = "62"
        else:
            self.logger.error("No Hard/Software selected for version query")
            return None
        response_data = await self._read_request(cmd, max_responses=2)
        return super().get_hw_sw_version(response_data=response_data, hard_soft=hard_soft)

    async def get_mosfet_status(self):
        response_data = await self._read_request("93")
        return super().get_mosfet_status(response_data=response_data)

    async def get_status(self):
        response_data = await self._read_request("94")
        return super().get_status(response_data=response_data)

    async def get_cell_voltages(self):
        if not self.status:
            await self.get_status()
        max_responses = self._calc_num_responses('cells', 3)
        self.logger.debug(f"[get_cell_voltages] Calculated max_responses: {max_responses}")
        if not max_responses:
            self.logger.warning("[get_cell_voltages] max_responses is None or 0, aborting.")
            return None
        self.logger.debug(f"[get_cell_voltages] Sending _read_request for command 95 with max_responses={max_responses}")
        response_data = await self._read_request("95", max_responses=max_responses)
        self.logger.debug(f"[get_cell_voltages] Response data for command 95: {response_data}")
        return super().get_cell_voltages(response_data=response_data)

    async def get_temperatures(self):
        if not self.status:
            await self.get_status()
        max_responses = self._calc_num_responses('temperature_sensors', 7)
        response_data = await self._read_request("96", max_responses=max_responses)
        return super().get_temperatures(response_data=response_data)

    async def get_balancing_status(self):
        response_data = await self._read_request("97")
        return super().get_balancing_status(response_data=response_data)

    async def get_alarms_diff_temp_volt(self):
        response_data = await self._read_request("5e")
        return super().get_alarms_diff_temp_volt(response_data=response_data)

    async def get_alarms_load_charge(self):
        response_data = await self._read_request("5b")
        return super().get_alarms_load_charge(response_data=response_data)

    async def get_rated_nominals(self):
        response_data = await self._read_request("50")
        return super().get_rated_nominals(response_data=response_data)

    async def get_balance_settings(self):
        response_data = await self._read_request("5f")
        return super().get_balance_settings(response_data=response_data)

    async def get_short_shutdownamp_ohm(self):
        response_data = await self._read_request("60")
        return super().get_short_shutdownamp_ohm(response_data=response_data)

    async def get_errors(self):
        response_data = await self._read_request("98")
        return super().get_errors(response_data=response_data)
