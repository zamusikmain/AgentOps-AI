"""Explicit local-only bootstrap, interactive password, no existing-account reset."""
import argparse,getpass,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.config import Settings
from app.main import create_app
from app.authentication import CreateUser
from app.llm_reliability import Scope

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--email',required=True);args=parser.parse_args()
    settings=Settings()
    from sqlalchemy.engine import make_url
    url=make_url(settings.database_url)
    if settings.environment_id!='local' or url.drivername!='sqlite' or not url.database or not Path(url.database).resolve().is_relative_to((root/'backend/data').resolve()):
        raise SystemExit('Only a project-local development database is permitted. Run from backend.')
    password=getpass.getpass('New local admin password (12+ characters): ')
    if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match.')
    app=None
    try:
        body=CreateUser(email=args.email,password=password,role='admin')
        app=create_app(settings)
        app.state.authentication.create(Scope('workspace','local-bootstrap','admin'),body)
    except Exception:
        raise SystemExit('Local bootstrap failed. Check email, password policy and migrated database; existing accounts are not reset.') from None
    finally:
        if app:app.state.engine.dispose()
    print('Local administrator created. No existing password was changed. Sign in at http://127.0.0.1:3000/login')

if __name__=='__main__':main()
