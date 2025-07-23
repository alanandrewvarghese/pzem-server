import time
from database import save_to_database

while True:
    save_to_database()
    time.sleep(1)