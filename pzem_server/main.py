import os
import time
import logging
from dotenv import load_dotenv
from database import save_to_database, init_db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

init_db()

while True:
    try:
        save_to_database()
        time.sleep(int(os.getenv("LOG_INTERVAL",1)))
    except TypeError:
        logging.error("LOG_INTERVAL environment variable is not a valid integer. Defaulting to 1 seconds.")
        time.sleep(5)
    except Exception as e:
        logging.error(f"Unexpected error, skipping save_to_db operation: {e}")