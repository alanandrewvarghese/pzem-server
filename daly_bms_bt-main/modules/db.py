import psycopg2
import logging

class PostgresDB:

    @staticmethod
    def get_create_bms_table_sql(table_name='bms_data'):
        return f'''
        CREATE TABLE IF NOT EXISTS {table_name} (
            id BIGSERIAL PRIMARY KEY,
            create_date TIMESTAMPTZ NOT NULL,
            total_voltage REAL,
            current REAL,
            soc_percent REAL,
            cell_1 SMALLINT,
            cell_2 SMALLINT,
            cell_3 SMALLINT,
            cell_4 SMALLINT,
            cell_5 SMALLINT,
            cell_6 SMALLINT,
            cell_7 SMALLINT,
            cell_8 SMALLINT
        );
        '''

    def insert_bms_data(self, table_name, create_date, total_voltage, current, soc_percent, cell_voltages):
        # cell_voltages: list or tuple of values (store as int mV)
        # Adapt to old structure: ensure exactly 8 values (pad with 0 if fewer, truncate if more)
        cell_voltages_int = [0] * 8
        for i, v in enumerate(cell_voltages[:8]):
            cell_voltages_int[i] = int(round(v * 1000))

        insert_sql = f'''
            INSERT INTO {table_name} (create_date, total_voltage, current, soc_percent, cell_1, cell_2, cell_3, cell_4, cell_5, cell_6, cell_7, cell_8)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        params = (create_date, total_voltage, current, soc_percent, *cell_voltages_int)
        self.insert(insert_sql, params)
        self.logger.info('BMS data inserted successfully.')

    def insert_bms_data_safe(self, table_name, create_date, total_voltage, current, soc_percent, cell_voltages):
        """Open a short-lived connection for inserts to avoid blocking the event loop thread."""
        cell_voltages_int = [0] * 8
        for i, v in enumerate(cell_voltages[:8]):
            cell_voltages_int[i] = int(round(v * 1000))

        insert_sql = f'''
            INSERT INTO {table_name} (create_date, total_voltage, current, soc_percent, cell_1, cell_2, cell_3, cell_4, cell_5, cell_6, cell_7, cell_8)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        params = (create_date, total_voltage, current, soc_percent, *cell_voltages_int)
        try:
            with psycopg2.connect(**self.config) as conn:
                with conn.cursor() as cur:
                    cur.execute(insert_sql, params)
                conn.commit()
            self.logger.info('BMS data inserted successfully.')
        except Exception as e:
            self.logger.error(f'Error inserting data (safe): {e}')
        
    def __init__(self, host, port, dbname, user, password, logger=None):
        self.logger = logger or logging.getLogger('daly_bms')
        self.conn = None
        self.config = {
            'host': host,
            'port': port,
            'dbname': dbname,
            'user': user,
            'password': password
        }

    def connect(self):
        try:
            self.conn = psycopg2.connect(**self.config)
            self.logger.info('Connected to PostgreSQL database.')
        except Exception as e:
            self.logger.error(f'Failed to connect to PostgreSQL: {e}')
            raise

    def close(self):
        if self.conn:
            self.conn.close()
            self.logger.info('PostgreSQL connection closed.')

    def execute(self, query, params=None, commit=False):
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params)
                if commit:
                    self.conn.commit()
                try:
                    return cur.fetchall()
                except psycopg2.ProgrammingError:
                    return None
        except Exception as e:
            self.logger.error(f'Error executing query: {e}')
            if commit:
                self.conn.rollback()
            raise

    def create_table(self, table_sql):
        self.execute(table_sql, commit=True)
        self.logger.info('Table created or already exists.')

    def insert(self, insert_sql, params):
        self.execute(insert_sql, params, commit=True)
        self.logger.info('Insert successful.')

    def fetch(self, select_sql, params=None):
        return self.execute(select_sql, params)
