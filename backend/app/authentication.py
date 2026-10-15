"""Email authentication, tenant-scoped management, opaque cookie sessions and CSRF."""
import hashlib,hmac,secrets,time,re
from typing import Literal
from fastapi import APIRouter,Request,Response
from pydantic import BaseModel,ConfigDict,Field,field_validator
from sqlalchemy import select,text,func,delete
from .db import User,UserSession,LoginAttempt,AuthAudit,PasswordReset,now,uid
from .llm_reliability import Scope
from .password_security import hash_password,verify_password,validate_password
from .services import ServiceError
COOKIE='agentops_session';CSRF='agentops_csrf'
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def public(user):return {k:getattr(user,k) for k in ('id','email','tenant_id','role','status','created_at','password_changed_at')}
class LoginInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 email:str=Field(min_length=3,max_length=254)
 password:str=Field(min_length=1,max_length=128,repr=False)
 @field_validator('email')
 @classmethod
 def email_value(cls,value):
  value=value.strip().casefold()
  if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('invalid_email')
  return value
class CreateUser(LoginInput):
 role:Literal['admin','operator','viewer']='viewer'
class ChangePassword(BaseModel):
 model_config=ConfigDict(extra='forbid')
 current_password:str=Field(min_length=1,max_length=128,repr=False)
 new_password:str=Field(min_length=12,max_length=128,repr=False)
class UserUpdate(BaseModel):
 model_config=ConfigDict(extra='forbid')
 role:Literal['admin','operator','viewer']|None=None
 status:Literal['active','disabled']|None=None
class ResetInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 token:str=Field(min_length=32,max_length=100,repr=False)
 new_password:str=Field(min_length=12,max_length=128,repr=False)
class Authentication:
 def __init__(self,sessions,settings):self.sessions=sessions;self.settings=settings;self.cookie=settings.auth_cookie_name;self.csrf_cookie=settings.auth_csrf_cookie_name;self.dummy=hash_password(secrets.token_urlsafe(32))
 def audit(self,db,tenant,actor,action,target=None):db.add(AuthAudit(tenant_id=tenant,actor_id=actor,action=action,target_id=target))
 def csrf(self,request,session=None):
  origin=request.headers.get('origin','');cookie=request.cookies.get(self.csrf_cookie,'');header=request.headers.get('x-csrf-token','')
  if origin not in self.settings.auth_allowed_origins or len(cookie)<32 or not hmac.compare_digest(cookie,header) or (session and not hmac.compare_digest(digest(header),session.csrf_hash)):raise ServiceError(403,'csrf_invalid')
 def secure(self,request):return self.settings.auth_cookie_secure or self.settings.environment_id!='local' or request.url.scheme=='https' or (request.headers.get('origin','').startswith('https://') and request.headers.get('origin') in self.settings.auth_allowed_origins)
 def cookies(self,request,response,token,csrf):
  response.set_cookie(self.cookie,token,httponly=True,secure=self.secure(request),samesite='lax',max_age=self.settings.auth_session_seconds,path='/')
  response.set_cookie(self.csrf_cookie,csrf,httponly=False,secure=self.secure(request),samesite='lax',max_age=self.settings.auth_session_seconds,path='/')
 def authenticate(self,request):
  token=request.cookies.get(self.cookie,'')
  if not token:return None,None
  with self.sessions() as db:
   session=db.scalar(select(UserSession).where(UserSession.token_hash==digest(token)))
   user=db.get(User,session.user_id) if session else None
  if not session or session.revoked_at or session.expires_at<=time.time() or not user or user.status!='active':raise ServiceError(401,'session_expired')
  return user,session
 def limit(self,request,email):
  key=digest(email);client=digest(request.client.host if request.client else 'local')
  with self.sessions() as db:
   db.execute(text('BEGIN IMMEDIATE'));cutoff=time.time()-self.settings.auth_login_window_seconds
   db.execute(delete(LoginAttempt).where(LoginAttempt.occurred_at<cutoff))
   account=db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.account_key==key));ip=db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.client_key==client))
   if account>=self.settings.auth_login_account_limit or ip>=self.settings.auth_login_client_limit:raise ServiceError(429,'login_rate_limited')
   attempt=LoginAttempt(account_key=key,client_key=client,occurred_at=time.time());db.add(attempt);db.commit();return attempt.id
 def login(self,request,response,body):
  self.csrf(request);attempt_id=self.limit(request,body.email)
  with self.sessions() as db:user=db.scalar(select(User).where(User.email==body.email))
  valid=verify_password(body.password,user.password_hash if user else self.dummy)
  if not valid or not user or user.status!='active':
   with self.sessions() as db:self.audit(db,user.tenant_id if user else 'unknown',None,'login_failed',user.id if user else None);db.commit()
   raise ServiceError(401,'invalid_credentials')
  token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
  with self.sessions() as db:
   db.execute(text('BEGIN IMMEDIATE'));current=db.get(User,user.id)
   if not current or current.status!='active' or current.password_hash!=user.password_hash:raise ServiceError(401,'invalid_credentials')
   old=request.cookies.get(self.cookie)
   if old:
    previous=db.scalar(select(UserSession).where(UserSession.token_hash==digest(old)))
    if previous:previous.revoked_at=now()
   db.add(UserSession(user_id=user.id,token_hash=digest(token),csrf_hash=digest(csrf),expires_at=time.time()+self.settings.auth_session_seconds))
   db.execute(delete(LoginAttempt).where(LoginAttempt.id==attempt_id));self.audit(db,user.tenant_id,user.id,'login_success');db.commit()
  self.cookies(request,response,token,csrf);return {'user':public(user),'csrf_cookie_name':self.csrf_cookie}
 def revoke(self,db,user_id):
  for session in db.scalars(select(UserSession).where(UserSession.user_id==user_id,UserSession.revoked_at.is_(None))):session.revoked_at=now()
 def user(self,request):
  user=getattr(request.state,'auth_user',None)
  if not user:raise ServiceError(403,'browser_session_required')
  return user
 def admin(self,request):
  scope=getattr(request.state,'llm_scope',Scope())
  if scope.role!='admin':raise ServiceError(403,'permission_denied')
  return scope
 def target(self,db,scope,id):
  user=db.get(User,id)
  if not user or user.tenant_id!=scope.tenant:raise ServiceError(404,'not_found')
  return user
 def create(self,scope,body,identifier=None):
  try:validate_password(body.password,body.email)
  except ValueError:raise ServiceError(422,'weak_password') from None
  password_hash=hash_password(body.password)
  with self.sessions() as db:
   db.execute(text('BEGIN IMMEDIATE'))
   if db.scalar(select(User.id).where(User.email==body.email)):raise ServiceError(409,'user_creation_unavailable')
   user=User(id=identifier or uid(),email=body.email,tenant_id=scope.tenant,role=body.role,password_hash=password_hash);db.add(user);self.audit(db,scope.tenant,scope.user,'user_created',user.id);db.commit();return public(user)

def auth_router(auth):
 api=APIRouter(prefix='/api',tags=['Authentication'])
 @api.get('/auth/csrf')
 def csrf(request:Request,response:Response):
  value=secrets.token_urlsafe(32);response.set_cookie(auth.csrf_cookie,value,httponly=False,secure=auth.secure(request),samesite='lax',path='/');return {'csrf_token':value,'csrf_cookie_name':auth.csrf_cookie}
 @api.post('/auth/login')
 def login(body:LoginInput,request:Request,response:Response):return auth.login(request,response,body)
 @api.get('/auth/me')
 def me(request:Request):return {'user':public(auth.user(request)),'csrf_cookie_name':auth.csrf_cookie}
 @api.post('/auth/logout')
 def logout(request:Request,response:Response):
  user=auth.user(request)
  with auth.sessions() as db:session=db.get(UserSession,request.state.auth_session.id);session.revoked_at=now();auth.audit(db,user.tenant_id,user.id,'logout');db.commit()
  response.delete_cookie(auth.cookie,path='/',secure=auth.secure(request),samesite='lax');response.delete_cookie(auth.csrf_cookie,path='/',secure=auth.secure(request),samesite='lax');return {'ok':True}
 @api.get('/auth/sessions')
 def sessions(request:Request):
  user=auth.user(request)
  with auth.sessions() as db:return {'items':[{'id':s.id,'created_at':s.created_at,'expires_at':s.expires_at,'revoked':bool(s.revoked_at),'current':s.id==request.state.auth_session.id} for s in db.scalars(select(UserSession).where(UserSession.user_id==user.id).order_by(UserSession.created_at.desc()))]}
 @api.post('/auth/sessions/{identifier}/revoke')
 def revoke_session(identifier:str,request:Request):
  user=auth.user(request)
  with auth.sessions() as db:
   session=db.get(UserSession,identifier)
   if not session or session.user_id!=user.id:raise ServiceError(404,'not_found')
   session.revoked_at=now();auth.audit(db,user.tenant_id,user.id,'session_revoked');db.commit()
  return {'ok':True}
 @api.post('/auth/password')
 def password(body:ChangePassword,request:Request):
  user=auth.user(request)
  if not verify_password(body.current_password,user.password_hash):raise ServiceError(401,'invalid_credentials')
  try:validate_password(body.new_password,user.email)
  except ValueError:raise ServiceError(422,'weak_password') from None
  new_hash=hash_password(body.new_password)
  with auth.sessions() as db:
   db.execute(text('BEGIN IMMEDIATE'));current=db.get(User,user.id)
   if current.status!='active' or current.password_hash!=user.password_hash:raise ServiceError(401,'session_expired')
   current.password_hash=new_hash;current.password_changed_at=now();auth.revoke(db,user.id);auth.audit(db,user.tenant_id,user.id,'password_changed');db.commit()
  return {'ok':True,'reauthenticate':True}
 @api.post('/auth/reset')
 def reset(body:ResetInput,request:Request):
  auth.csrf(request)
  with auth.sessions() as db:r=db.scalar(select(PasswordReset).where(PasswordReset.token_hash==digest(body.token)));user=db.get(User,r.user_id) if r else None
  if not r or r.used_at or r.expires_at<=time.time() or not user or user.status!='active':raise ServiceError(401,'invalid_credentials')
  try:validate_password(body.new_password,user.email)
  except ValueError:raise ServiceError(422,'weak_password') from None
  new_hash=hash_password(body.new_password)
  with auth.sessions() as db:
   db.execute(text('BEGIN IMMEDIATE'));current=db.get(PasswordReset,r.id)
   if current.used_at or current.expires_at<=time.time():raise ServiceError(401,'invalid_credentials')
   u=db.get(User,user.id)
   if not u or u.status!='active':raise ServiceError(401,'invalid_credentials')
   current.used_at=now();u.password_hash=new_hash;u.password_changed_at=now();auth.revoke(db,u.id);auth.audit(db,u.tenant_id,u.id,'password_reset_completed');db.commit()
  return {'ok':True}
 @api.get('/users')
 def users(request:Request):
  scope=auth.admin(request)
  with auth.sessions() as db:return {'items':[public(u) for u in db.scalars(select(User).where(User.tenant_id==scope.tenant).order_by(User.created_at))]}
 @api.post('/users',status_code=201)
 def create(body:CreateUser,request:Request):return auth.create(auth.admin(request),body)
 @api.patch('/users/{identifier}')
 def update(identifier:str,body:UserUpdate,request:Request):
  scope=auth.admin(request)
  if identifier==scope.user:raise ServiceError(403,'self_management_denied')
  with auth.sessions() as db:
   db.execute(text('BEGIN IMMEDIATE'));user=auth.target(db,scope,identifier)
   if user.role=='admin' and user.status=='active' and (body.role and body.role!='admin' or body.status=='disabled') and db.scalar(select(func.count()).select_from(User).where(User.tenant_id==scope.tenant,User.role=='admin',User.status=='active'))<=1:raise ServiceError(409,'last_admin_required')
   if body.role:user.role=body.role
   if body.status:user.status=body.status
   auth.revoke(db,user.id);auth.audit(db,scope.tenant,scope.user,'user_updated',user.id);db.commit();return public(user)
 @api.post('/users/{identifier}/revoke-sessions')
 def revoke_user(identifier:str,request:Request):
  scope=auth.admin(request)
  with auth.sessions() as db:user=auth.target(db,scope,identifier);auth.revoke(db,user.id);auth.audit(db,scope.tenant,scope.user,'user_sessions_revoked',user.id);db.commit()
  return {'ok':True}
 @api.post('/users/{identifier}/reset-password')
 def reset_user(identifier:str,request:Request):
  scope=auth.admin(request);token=secrets.token_urlsafe(32)
  if identifier==scope.user:raise ServiceError(403,'self_management_denied')
  with auth.sessions() as db:
   user=auth.target(db,scope,identifier)
   for old in db.scalars(select(PasswordReset).where(PasswordReset.user_id==user.id,PasswordReset.used_at.is_(None))):old.used_at=now()
   db.add(PasswordReset(user_id=user.id,token_hash=digest(token),expires_at=time.time()+900));auth.revoke(db,user.id);auth.audit(db,scope.tenant,scope.user,'password_reset_issued',user.id);db.commit()
  return {'reset_token':token,'expires_in_seconds':900,'delivery':'manual_local_only'}
 @api.get('/users/audit')
 def audit(request:Request):
  scope=auth.admin(request)
  with auth.sessions() as db:return {'items':[{'id':a.id,'actor_id':a.actor_id,'target_id':a.target_id,'action':a.action,'created_at':a.created_at} for a in db.scalars(select(AuthAudit).where(AuthAudit.tenant_id==scope.tenant).order_by(AuthAudit.created_at.desc()).limit(200))]}
 return api
