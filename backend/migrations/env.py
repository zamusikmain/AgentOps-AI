from alembic import context
from app.config import Settings, ROOT
from app.db import Base, database

(ROOT / 'data').mkdir(exist_ok=True)
engine, _ = database(Settings().database_url)
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
