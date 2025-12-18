import psycopg2
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from power_data import get_power_data

db_params = {
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "host": os.getenv("POSTGRES_HOST"),
    "port": os.getenv("POSTGRES_PORT")
}

ist_tz = ZoneInfo("Asia/Kolkata")

def init_db():
    create_ac_table_sql = """
    CREATE TABLE IF NOT EXISTS ac_monitor(
        id SERIAL PRIMARY KEY,
        create_date TIMESTAMP,
        voltage DECIMAL(12, 4),
        current DECIMAL(12, 4),
        power DECIMAL(12, 4),
        energy DECIMAL(20, 4),
        frequency DECIMAL(12, 4),
        power_factor DECIMAL(12, 4)
    );
    """
    create_solar_table_sql = """
    CREATE TABLE IF NOT EXISTS solar_monitor(
        id SERIAL PRIMARY KEY,
        create_date TIMESTAMP,
        voltage DECIMAL(12, 4),
        current DECIMAL(12, 4),
        power DECIMAL(20, 4),
        energy DECIMAL(12, 4)
    );
    """
    
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cur:
                cur.execute(create_ac_table_sql)
                cur.execute(create_solar_table_sql)
    except psycopg2.Error as e:
        logging.error(f"Database operation (Table Creation) failed: {e}")
    except Exception as e:
        logging.error(f"Unexpected Error! Table Creation failed: {e}")

def save_to_database():
    """
    Fetches power data, connects to the PostgreSQL database,
    and securely saves the new data.
    """
    data = get_power_data()
    ac_data = data.get('AC')
    solar_data = data.get('SOLAR')
    current_timestamp_ist_fmt = datetime.now(ist_tz).strftime("%Y-%m-%d %H:%M:%S.%f")
    
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cur:
                if ac_data:
                    insert_ac_sql = """
                    INSERT INTO ac_monitor (create_date, voltage, current, power, energy, frequency, power_factor)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """
                    ac_values = (
                        current_timestamp_ist_fmt,
                        ac_data.get('voltage'),
                        ac_data.get('current'),
                        ac_data.get('power'),
                        ac_data.get('energy'),
                        ac_data.get('frequency'),
                        ac_data.get('power_factor')
                    )
                    cur.execute(insert_ac_sql, ac_values)
                else:
                    logging.warning("Failed to retrieve valid AC data.")
                    
                if solar_data and solar_data.get('power') != 0:
                    insert_solar_sql = """
                    INSERT INTO solar_monitor (create_date, voltage, current, power, energy)
                    VALUES (%s, %s, %s, %s, %s);
                    """
                    solar_values = (
                        current_timestamp_ist_fmt,
                        solar_data.get('voltage'),
                        solar_data.get('current'),
                        solar_data.get('power'),
                        solar_data.get('energy')
                    )
                    cur.execute(insert_solar_sql, solar_values)
                else:
                    logging.warning("Failed to retrieve valid Solar data.")
    except psycopg2.Error as e:
        logging.error(f"Database operation ( Data Insertion ) failed: {e}")
    except Exception as e:
        logging.error(f"Unexpected Error! Data Insertion failed: {e}")