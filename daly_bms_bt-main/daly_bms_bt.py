#!/usr/bin/python3
# Added some data points as of this link
# https://diysolarforum.com/threads/decoding-the-daly-smartbms-protocol.21898/

import time
import argparse
import asyncio
import os
import signal
from modules import DalyBMSBluetooth
from modules import get_logger
from modules.db import PostgresDB
import datetime



parser = argparse.ArgumentParser()
parser.add_argument(
    "--bt",
    help="Use BT mac address [default provided]",
    type=str,
    default="C6:6C:09:03:0A:13",
)
parser.add_argument(
    "--hci",
    help="Adapter to use for connection [default hci0]",
    type=str,
    default="hci0",
)
parser.add_argument(
    "--loop",
    help="Continious running, pause between loop runs in s, single run without argument",
    type=int,
)
parser.add_argument(
    "--keep",
    help="Keep BT connection, instead of closing and reopening the BT connection with each run",
    action="store_true",
)
parser.add_argument(
    "--log-level",
    help="Set log level (debug, info [default], warning, error, critical)",
    type=str,
    default="info",
)
parser.add_argument("--no-db", help="Disable database logging", action="store_true")

args = parser.parse_args()


logger = get_logger(level=args.log_level)


# Configure your database connection here
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "power_monitor"),
    "user": os.getenv("DB_USER", "odoo"),
    "password": os.getenv("DB_PASSWORD", "odoo"),
}
TABLE_NAME = "bms_data"


class DalyBMSConnection:
    def __init__(self, mac_address, logger, adapter="hci0", db=None):
        self.logger = logger
        self.adapter = adapter
        self.mac_address = mac_address
        self.db = db
        self.last_data_received = None
        self.bt_bms = DalyBMSBluetooth(self.mac_address, self.logger, self.adapter)

    async def connect(self):
        if not self.bt_bms.client.is_connected:
            await self.bt_bms.connect()

    async def disconnect(self):
        try:
            await self.bt_bms.disconnect()
        except Exception as e:
            self.logger.debug(f"Disconnect error (ignored): {e}")

    async def get_full_data_and_save(self):
        # Gather both SOC and CellVoltages, then save to DB in one call
        soc_data = await self.bt_bms.get_soc()
        cell_voltages_data = await self.bt_bms.get_cell_voltages()
        self.logger.debug({"SOC": soc_data, "CellVoltages": cell_voltages_data})
        if not soc_data or not cell_voltages_data:
            self.logger.warning("Missing data: SOC or CellVoltages not received")
            return
        # Prepare cell voltages as list, handling variable number of cells
        cell_voltages = [
            cell_voltages_data[k] for k in sorted(cell_voltages_data.keys())
        ]

        # Print SOC data first, then cell voltages on next line
        print(soc_data)
        print(cell_voltages)
        point = [
            "BMS",
            self.mac_address,
            time.time(),
            {"soc": soc_data, "cell_voltages": cell_voltages},
        ]
        self.last_data_received = time.time()

        # --- Save to DB ---
        if self.db is not None:
            # Use UTC for database storage.
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self.db.insert_bms_data_safe,
                TABLE_NAME,
                utc_now,
                soc_data.get("total_voltage"),
                soc_data.get("current"),
                soc_data.get("soc_percent"),
                cell_voltages,
            )
        return point


async def main_loop(args, logger):
    db = None
    con = None
    try:
        # --- Setup DB ---
        if not args.no_db:
            try:
                db = PostgresDB(**DB_CONFIG, logger=logger)
                db.connect()
                db.create_table(PostgresDB.get_create_bms_table_sql(TABLE_NAME))
            except Exception as e:
                logger.error(f"Database setup failed: {e}")
                db = None

        if args.bt:
            mac_address = args.bt
        else:
            logger.error("No BT MAC address provided.")
            return

        con = DalyBMSConnection(mac_address, logger, args.hci, db=db)
        received_data = False

        if args.loop:
            logger.debug("Starting loop")
        else:
            logger.debug("Starting oneshot")

        while args.loop or not received_data:
            try:
                await con.connect()
            except Exception as e:
                logger.warning(f"Connection failed: {e}. Retrying in 5s...")
                try:
                    await con.disconnect()
                except:
                    pass
                # Recreate connection object to ensure fresh state
                con = DalyBMSConnection(mac_address, logger, args.hci, db=db)
                await asyncio.sleep(5)
                continue

            if con.bt_bms.client.is_connected:
                try:
                    await con.get_full_data_and_save()
                    print()
                    if con.last_data_received is None:
                        logger.warning("Failed receive data")
                        await asyncio.sleep(10)
                        continue
                    time_diff = time.time() - con.last_data_received
                    if time_diff > 30:
                        logger.error(
                            "BMS thread didn't receive data for %0.1f seconds"
                            % time_diff
                        )
                    else:
                        if not received_data:
                            logger.info("First received data")
                            received_data = True
                    logger.debug("run done")
                except Exception as e:
                    logger.error(f"Error during data collection: {e}")
                    try:
                        await con.disconnect()
                    except:
                        pass
            else:
                logger.info("No connection made, waiting and retry")

            if not args.keep:
                await con.disconnect()

            if args.loop:
                await asyncio.sleep(args.loop)
            else:
                await asyncio.sleep(1)
    finally:
        if con:
            try:
                await con.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting BT: {e}")
        if db:
            db.close()

    if args.loop:
        logger.info("Loop ended")
    else:
        logger.debug("Oneshot finished")


def main_entry():
    # Register signal handler for graceful shutdown on SIGTERM
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, exiting...")
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, signal_handler)
    # SIGINT is handled by KeyboardInterrupt automatically

    time.sleep(1)
    while True:
        try:
            asyncio.run(main_loop(args, logger))
            if not args.loop:
                break
        except KeyboardInterrupt:
            logger.info("Keyboard break")
            break
        except RuntimeError as e:
            logger.error(f"Restarting due to error: {e}")
            # Simulate a full restart (like Ctrl+C and rerun)
            time.sleep(5)
            continue
        except Exception as e:
            logger.error(f"Unhandled exception: {e}")
            time.sleep(5)
            continue

    logger.info("Final End")


if __name__ == "__main__":
    main_entry()
