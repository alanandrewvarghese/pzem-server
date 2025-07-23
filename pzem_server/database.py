import psycopg2
import os
import logging
from datetime import datetime
from power_data import get_power_data

db_params = {
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "host": os.getenv("POSTGRES_HOST"),
    "port": os.getenv("POSTGRES_PORT")
}

def save_to_database():
    """
    Fetches power data, connects to the PostgreSQL database,
    and securely saves the new data.
    """
    # Get the data from your source
    data = get_power_data()
    ac_data = data.get('AC')
    solar_data = data.get('SOLAR')

    # If data is missing, log an error and exit the function.
    if not ac_data or not solar_data:
        logging.error("Failed to retrieve valid AC or SOLAR data.")
        return

    # Capture the timestamp once to ensure it's the same for both records
    current_timestamp = datetime.now()

    # SQL statements are defined once for clarity.
    # Note the use of 'CREATE TABLE IF NOT EXISTS' to prevent errors on subsequent runs.
    create_ac_table_sql = """
    CREATE TABLE IF NOT EXISTS ac_monitor(
        id SERIAL PRIMARY KEY,
        create_date TIMESTAMP,
        voltage DECIMAL(12, 4),
        current DECIMAL(12, 4),
        power DECIMAL(12, 4),
        energy DECIMAL(12, 4),
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
        power DECIMAL(12, 4),
        energy DECIMAL(12, 4)
    );
    """

    # IMPORTANT: Use placeholders (%s) for values to prevent SQL injection.
    # The database driver will safely substitute the values.
    insert_ac_sql = """
    INSERT INTO ac_monitor (create_date, voltage, current, power, energy, frequency, power_factor)
    VALUES (%s, %s, %s, %s, %s, %s, %s);
    """

    insert_solar_sql = """
    INSERT INTO solar_monitor (create_date, voltage, current, power, energy)
    VALUES (%s, %s, %s, %s, %s);
    """

    try:
        # Using 'with' for the connection and cursor ensures that resources are
        # automatically managed (committed on success, rolled back on error, and closed).
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cur:
                # Execute table creation
                cur.execute(create_ac_table_sql)
                cur.execute(create_solar_table_sql)

                # Prepare data tuples for insertion
                ac_values = (
                    current_timestamp,
                    ac_data.get('voltage'),
                    ac_data.get('current'),
                    ac_data.get('power'),
                    ac_data.get('energy'),
                    ac_data.get('frequency'),
                    ac_data.get('power_factor')
                )

                # BUG FIX: Using 'solar_data' here instead of 'ac_data'
                solar_values = (
                    current_timestamp,
                    solar_data.get('voltage'),
                    solar_data.get('current'),
                    solar_data.get('power'),
                    solar_data.get('energy')
                )

                # Execute the inserts with the safe, parameterized query method
                cur.execute(insert_ac_sql, ac_values)
                cur.execute(insert_solar_sql, solar_values)
                
                logging.info("Successfully saved power data to the database.")

    except psycopg2.Error as e:
        # It's good practice to catch specific database errors.
        logging.error(f"Database operation failed: {e}")
    except Exception as e:
        # Catch any other potential errors.
        logging.error(f"An unexpected error occurred: {e}")