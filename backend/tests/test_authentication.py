import time,json,concurrent.futures
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import create_app
from app.config import Settings
from app.db import Base,User,UserSession,AuthAudit,PasswordReset
from app.authentication import CreateUser,COOKIE,CSRF
from app.llm_reliability import Scope
from app.password_security import hash_password,verify_password
PASS='V7!secure-test.Raven_984'
NEXT='Q9!different-test.Oak_761'
@pytest.fixture
def env(tmp_path):
 s=Settings(_env_file=None,api_token='api-only-test',database_url=f'sqlite:///{tmp_path/"auth.db"}',checkpoint_database_path=tmp_path/'cp.db',knowledge_storage_path=tmp_path/'docs',local_mcp_enabled=False,auth_allowed_origins=['http://testserver'])
 app=create_app(s);Base.metadata.create_all(app.state.engine)
 a=app.state.authentication
 admin=a.create(Scope(),CreateUser(email='admin@local.test',password=PASS,role='admin'),'owner')
 viewer=a.create(Scope(),CreateUser(email='viewer@local.test',password=PASS,role='viewer'))
 foreign=a.create(Scope('foreign','founder','admin'),CreateUser(email='foreign@local.test',password=PASS,role='admin'))
 with TestClient(app) as c:yield c,admin,viewer,foreign

def headers(c):return {'Origin':str(c.base_url).rstrip('/'),'X-CSRF-Token':c.cookies.get(CSRF,'')}
def login(c,email='admin@local.test',password=PASS):
 c.get('/api/auth/csrf');return c.post('/api/auth/login',json={'email':email,'password':password},headers=headers(c))
def test_hash_salts_and_password_limits():
 a=hash_password(PASS);b=hash_password(PASS);assert a!=b;assert PASS not in a;assert a.startswith('scrypt$32768');assert verify_password(PASS,a);assert not verify_password('wrong',a)
@pytest.mark.parametrize('email,password',[('missing@local.test',PASS),('admin@local.test','wrong'),('viewer@local.test','wrong')])
def test_neutral_failed_login(env,email,password):
 c,*_=env;r=login(c,email,password);assert r.status_code==401;assert r.json()=={'error':{'code':'invalid_credentials'}}
def test_login_cookie_me_logout_and_bearer(env):
 c,admin,*_=env;r=login(c);assert r.status_code==200;assert r.json()['user']['id']=='owner';assert 'password_hash' not in r.text and PASS not in r.text
 cookie=r.headers.get_list('set-cookie');assert any('HttpOnly' in s and 'SameSite=lax' in s for s in cookie)
 assert c.get('/api/auth/me').json()['user']['role']=='admin'
 token=c.cookies.get(COOKIE)
 assert c.post('/api/auth/logout',headers=headers(c)).status_code==200
 assert c.get('/api/dashboard').status_code==401
 c.cookies.set(COOKIE,token);assert c.get('/api/dashboard').status_code==401
 assert c.get('/api/dashboard',headers={'Authorization':'Bearer api-only-test'}).status_code==200
 assert c.post('/api/agents',headers={'Authorization':'Bearer api-only-test'},json={}).status_code==422

def test_csrf_missing_forged_origin_and_no_auth(env):
 c,*_=env;assert c.get('/api/users').status_code==401
 c.get('/api/auth/csrf');assert c.post('/api/auth/login',json={'email':'admin@local.test','password':PASS}).status_code==403
 assert c.post('/api/auth/login',json={'email':'admin@local.test','password':PASS},headers={**headers(c),'Origin':'http://evil.test'}).status_code==403
 assert login(c).status_code==200
 assert c.post('/api/auth/logout').status_code==403
 assert c.post('/api/auth/logout',headers={**headers(c),'X-CSRF-Token':'forged'}).status_code==403

def test_expired_revoked_and_disabled(env):
 c,admin,viewer,_=env;assert login(c).status_code==200
 with c.app.state.sessions() as db:s=db.scalar(select(UserSession));s.expires_at=time.time()-1;db.commit()
 assert c.get('/api/auth/me').status_code==401
 assert login(c).status_code==200
 assert c.patch('/api/users/'+viewer['id'],json={'status':'disabled'},headers=headers(c)).status_code==200
 assert login(c,'viewer@local.test').status_code==401
 assert login(c).status_code==200
 assert c.patch('/api/users/'+viewer['id'],json={'status':'active'},headers=headers(c)).status_code==200
 assert login(c,'viewer@local.test').status_code==200

def test_password_change_revokes_only_own_and_stores_hash(env):
 c,admin,viewer,_=env;assert login(c,'viewer@local.test').status_code==200
 user_token=c.cookies.get(COOKIE);c.cookies.clear()
 assert login(c).status_code==200
 assert c.post('/api/auth/password',json={'current_password':PASS,'new_password':NEXT},headers=headers(c)).status_code==200
 assert c.get('/api/auth/me').status_code==401
 assert login(c,password=PASS).status_code==401
 assert login(c,password=NEXT).status_code==200
 c.cookies.clear();c.cookies.set(COOKIE,user_token,domain='testserver.local',path='/')
 assert c.get('/api/auth/me').status_code==200
 with c.app.state.sessions() as db:
  u=db.get(User,'owner');assert verify_password(NEXT,u.password_hash);assert NEXT not in u.password_hash
  assert all(PASS not in json.dumps({'action':a.action}) and NEXT not in a.action for a in db.scalars(select(AuthAudit)))

def test_rbac_cross_tenant_self_escalation(env):
 c,admin,viewer,foreign=env;assert login(c,'viewer@local.test').status_code==200
 assert c.get('/api/users').status_code==403
 assert c.patch('/api/users/'+viewer['id'],json={'role':'admin'},headers=headers(c)).status_code==403
 assert c.post('/api/tasks',json={},headers=headers(c)).status_code==403
 assert login(c).status_code==200
 assert c.patch('/api/users/owner',json={'role':'viewer'},headers=headers(c)).status_code==403
 assert c.patch('/api/users/'+foreign['id'],json={'status':'disabled'},headers=headers(c)).status_code==404
 assert foreign['id'] not in json.dumps(c.get('/api/users').json())
 assert login(c,'foreign@local.test').status_code==200
 assert c.get('/api/dashboard').status_code==403
 assert c.patch('/api/users/'+viewer['id'],json={'role':'admin'},headers=headers(c)).status_code==404

def test_create_user_reset_token_once_and_revoke(env):
 c,*_=env;assert login(c).status_code==200
 created=c.post('/api/users',json={'email':'created@local.test','password':PASS,'role':'operator'},headers=headers(c));assert created.status_code==201;uid=created.json()['id'];assert 'password_hash' not in created.text and PASS not in created.text
 assert c.post('/api/users',json={'email':'bad@local.test','password':'password123456','role':'viewer'},headers=headers(c)).status_code==422
 reset=c.post('/api/users/'+uid+'/reset-password',headers=headers(c));assert reset.status_code==200;token=reset.json()['reset_token']
 assert c.post('/api/auth/logout',headers=headers(c)).status_code==200;c.get('/api/auth/csrf')
 assert c.post('/api/auth/reset',json={'token':token,'new_password':NEXT},headers=headers(c)).status_code==200
 assert c.post('/api/auth/reset',json={'token':token,'new_password':PASS},headers=headers(c)).status_code==401
 assert login(c,'created@local.test',NEXT).status_code==200
 assert c.get('/api/auth/me').json()['user']['role']=='operator'
 with c.app.state.sessions() as db:stored=db.scalar(select(PasswordReset));assert token not in stored.token_hash

def test_rate_limit(env):
 c,*_=env
 for _ in range(5):assert login(c,password='wrong').status_code==401
 assert login(c).status_code==429

def test_concurrent_sessions_and_own_revoke(env):
 c,*_=env;assert login(c).status_code==200;first=c.cookies.get(COOKIE);c.cookies.clear();assert login(c).status_code==200
 sessions=c.get('/api/auth/sessions').json()['items'];assert len(sessions)==2
 old=next(s for s in sessions if not s['current']);assert c.post('/api/auth/sessions/'+old['id']+'/revoke',headers=headers(c)).status_code==200
 c.cookies.clear();c.cookies.set(COOKIE,first);assert c.get('/api/auth/me').status_code==401

def test_secure_cookie_setting(env):
 c,*_=env;c.base_url='https://testserver';c.app.state.authentication.settings.auth_cookie_secure=True;c.app.state.authentication.settings.auth_allowed_origins=['https://testserver']
 r=login(c);assert r.status_code==200;assert all('Secure' in value for value in r.headers.get_list('set-cookie'))

def test_origin_realm_and_automatic_https_security(env):
 c,*_=env;assert login(c).status_code==200
 assert c.post('/api/auth/logout',headers={**headers(c),'Origin':'http://127.0.0.1:3002'}).status_code==403
 c.cookies.clear();c.base_url='https://testserver';c.app.state.authentication.settings.auth_cookie_secure=False;c.app.state.authentication.settings.auth_allowed_origins=['https://testserver']
 result=login(c);assert result.status_code==200;assert all('Secure' in cookie for cookie in result.headers.get_list('set-cookie'))

def test_admin_revocation_and_block_invalidate_active_session(env):
 c,admin,viewer,_=env;assert login(c,'viewer@local.test').status_code==200;token=c.cookies.get(COOKIE);c.cookies.clear();assert login(c).status_code==200
 assert c.post('/api/users/'+viewer['id']+'/revoke-sessions',headers=headers(c)).status_code==200
 admin_token=c.cookies.get(COOKIE);admin_csrf=c.cookies.get(CSRF);c.cookies.clear();c.cookies.set(COOKIE,token);assert c.get('/api/auth/me').status_code==401
 c.cookies.clear();assert login(c,'viewer@local.test').status_code==200;new_token=c.cookies.get(COOKIE);c.cookies.clear();c.cookies.set(COOKIE,admin_token);c.cookies.set(CSRF,admin_csrf)
 assert c.patch('/api/users/'+viewer['id'],headers=headers(c),json={'status':'disabled'}).status_code==200
 c.cookies.clear();c.cookies.set(COOKIE,new_token);assert c.get('/api/auth/me').status_code==401

def test_management_tenant_injection_and_modern_weak_passwords(env):
 c,*_=env;assert login(c).status_code==200
 assert c.post('/api/users',headers=headers(c),json={'email':'injected@local.test','password':PASS,'role':'admin','tenant_id':'foreign'}).status_code==422
 assert c.post('/api/users',headers=headers(c),json={'email':'invalid-role@local.test','password':PASS,'role':'superuser'}).status_code==422
 assert c.post('/api/users',headers=headers(c),json={'email':'weak@local.test','password':'Welcome123456!','role':'viewer'}).status_code==422
