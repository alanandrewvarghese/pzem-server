# Daly BMS Bluetooth Monitor

This project provides a robust, user-friendly Python tool for monitoring Daly BMS (Battery Management System) devices over Bluetooth. It features advanced logging, PostgreSQL database integration, and clear console output for both State of Charge (SOC) and individual cell voltages.

## Features
- Communicates with Daly BMS via Bluetooth (using `bleak`)
- Prints SOC and cell voltages in a clear, readable format
- Saves all BMS data to a PostgreSQL database
- Advanced logging with file rotation, compression, and retention
- Configurable via command-line arguments

## Requirements
- Python 3.7+
- Daly BMS with Bluetooth support
- PostgreSQL database
- Bluetooth adapter (e.g., hci0)

### Python Dependencies
Install all dependencies with:
```sh
pip install -r requirements.txt
```

## Setup
1. **Configure Database**
   - Edit the `DB_CONFIG` dictionary in `daly_bms_bt.py` to match your PostgreSQL credentials and database name.
2. **Connect Daly BMS**
   - Ensure your Daly BMS is powered on and Bluetooth is enabled.
3. **Run the Script**
   - Example usage:
     ```sh
     python daly_bms_bt.py --bt <BT_MAC_ADDRESS> --hci hci0 --loop 10
     ```
   - Replace `<BT_MAC_ADDRESS>` with your Daly BMS Bluetooth MAC address.

## Command-Line Arguments
| Argument      | Description                                                      |
|-------------- |------------------------------------------------------------------|
| `--bt`        | Bluetooth MAC address of Daly BMS (**required**)                 |
| `--hci`       | Bluetooth adapter to use (default: hci0)                         |
| `--loop`      | Loop interval in seconds (run continuously if set)               |
| `--keep`      | Keep BT connection open between loops                            |
| `--log-level` | Set log level (debug, info, warning, error, critical; default: info) |

## Output
- The script prints SOC data first, then cell voltages, for each data read.
- All data is also saved to the PostgreSQL database with a timestamp (IST, UTC+5:30).

## Logging
- Logs are saved in the `logs/` directory (created automatically).
- Log files are rotated daily, compressed, and retained per your configuration in `modules/logger.py`.

## Troubleshooting
- **No data received:**
  - Ensure the MAC address is correct and the BMS is powered on.
  - Check Bluetooth adapter and permissions.
- **Database errors:**
  - Verify PostgreSQL is running and credentials in `DB_CONFIG` are correct.
- **Missing dependencies:**
  - Run `pip install -r requirements.txt` again.

## Credits
- Inspired by the DIY Solar Forum and Daly BMS protocol documentation.
- Developed by the open-source community.

---
For advanced configuration, logging, or database schema changes, see the source code and comments.
