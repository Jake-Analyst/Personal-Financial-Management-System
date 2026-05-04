from sqlalchemy import create_engine, MetaData, Table, Column, Float, String, DateTime, Integer, inspect
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DB_URL = f'sqlite:///{os.path.join(DATA_DIR, "user_data.db")}'
engine = create_engine(DB_URL)
metadata = MetaData()

user_table = None

def create_dynamic_table(df, table_name='user_data'):
    """Drop existing table and create a fresh one based on DataFrame columns."""
    global user_table, metadata
    
    # Drop the table if it exists
    with engine.connect() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS {table_name}'))
        conn.commit()
    
    # Create new metadata and table
    metadata = MetaData()
    columns = [Column('id', Integer, primary_key=True)]
    for col in df.columns:
        dtype = df[col].dtype
        if dtype == 'int64' or dtype == 'float64':
            columns.append(Column(col, Float))
        elif dtype == 'datetime64[ns]':
            columns.append(Column(col, DateTime))
        else:
            columns.append(Column(col, String))
    
    user_table = Table(table_name, metadata, *columns)
    metadata.create_all(engine)

from sqlalchemy import text  # ensure import

def insert_data(df):
    """Insert DataFrame rows into the dynamic table."""
    global user_table
    # Convert DataFrame to list of dicts, replace NaN with None
    data = df.where(df.notnull(), None).to_dict('records')
    with engine.connect() as conn:
        conn.execute(user_table.delete())  # clear old data
        conn.execute(user_table.insert(), data)
        conn.commit()
