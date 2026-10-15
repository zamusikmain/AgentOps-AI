from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

def test_v02_migration_preserves_single_agent_tables(tmp_path, monkeypatch):
    url=f'sqlite:///{(tmp_path/"migration.db").as_posix()}'
    monkeypatch.setenv('DATABASE_URL',url)
    cfg=Config('alembic.ini')
    command.upgrade(cfg,'001')
    engine=create_engine(url)
    before=set(inspect(engine).get_table_names())
    with engine.connect() as db:
        counts={name:db.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar() for name in before}
    command.upgrade(cfg,'head')
    after=set(inspect(engine).get_table_names())
    assert {'workflows','workflow_runs','workflow_steps','workflow_events'} <= after
    assert before <= after
    with engine.connect() as db:
        for name,count in counts.items():
            assert db.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()==count
        assert db.execute(text('SELECT version_num FROM alembic_version')).scalar()=='009'
    engine.dispose()
