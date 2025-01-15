from sqlalchemy import Table, Column, Integer, Boolean, MetaData
from sqlalchemy.inspection import inspect
from app import db

def get_or_create_table(user_name):
    """Dynamically create or get a table."""
    engine = db.engine
    metadata = MetaData()
    table_name = f"validity_{user_name}"

    inspector = inspect(engine)
    if table_name in inspector.get_table_names():
        table = Table(table_name, metadata, autoload_with=engine)
    else:
        table = Table(
            table_name,
            metadata,
            Column('exp_id', Integer, primary_key=True),
            Column('valid', Boolean),
            Column('invalid', Boolean),
            extend_existing=True,
        )
        table.create(engine)
    
    return table
