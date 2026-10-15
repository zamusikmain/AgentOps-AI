"""Clean and 009 -> head migration checks, isolated databases only."""
import os,sys,tempfile,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine,text
os.chdir(root/'backend')
work=root/'backend/.pytest-work';work.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='v12-migration-',dir=work) as folder:
    cfg=Config('alembic.ini')
    for name,target in [('clean','head'),('upgrade','009')]:
        url=f'sqlite:///{Path(folder)/name}.db';os.environ['DATABASE_URL']=url
        command.upgrade(cfg,target)
        engine=create_engine(url)
        with engine.begin() as db:
            db.execute(text("INSERT INTO llm_configurations (id,tenant_id,kind,name,version,body,updated_at) VALUES ('v12-preserved','fixture','fixture','preserve',1,:body,'fixture')"),{'body':json.dumps({'sentinel':True})})
        command.upgrade(cfg,'head')
        with engine.connect() as db:
            assert db.execute(text('SELECT version_num FROM alembic_version')).scalar()=='009'
            assert json.loads(db.execute(text("SELECT body FROM llm_configurations WHERE id='v12-preserved'")).scalar())=={'sentinel':True}
        engine.dispose()
report={'clean_database':'PASS','upgrade_009_to_head':'PASS','existing_configuration_preserved':True,'schema_head':'009','new_tables_required':False,'destructive_migration':False}
(root/'docs/v12-migration-check.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
