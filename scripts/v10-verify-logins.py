"""Verify all native local browser logins; document secrets only in ignored local files."""
import sys,json,urllib.request,urllib.error,http.cookiejar,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];data=root/'backend/data';file=data/'auth-development-credentials.local.json';records=json.loads(file.read_text())
for r in records:
 jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));base=r['api_url'];origin=r['login_url'].split('/login')[0]
 def request(path,body=None):
  csrf=next((c.value for c in jar if c.name in ('agentops_csrf','agentops_dev_csrf')),'')
  req=urllib.request.Request(base+'/api/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Origin':origin,'X-CSRF-Token':csrf,'Content-Type':'application/json'})
  with opener.open(req,timeout=20) as response:return response.status,json.load(response)
 request('auth/csrf');status,result=request('auth/login',{'email':r['email'],'password':r['password']});assert status==200
 _,me=request('auth/me');assert me['user']['id']==r['id'] and me['user']['role']==r['role'] and me['user']['tenant_id']==r['tenant']
 try:code,_=request('users')
 except urllib.error.HTTPError as exc:code=exc.code
 assert code==(200 if r['role']=='admin' else 403)
 r['verified']=True;r['role_verified']=True;request('auth/logout',{})
file.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
print('Native local email/password logins and roles: PASS',len(records),'/',len(records),'; no passwords printed.')
