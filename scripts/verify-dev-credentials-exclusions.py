"""Verify exclude rules without initializing or changing Git in the project."""
import subprocess,tempfile,shutil,json,urllib.request,urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='credential-ignore-check-',dir=root/'backend/data') as td:
 path=Path(td);shutil.copyfile(root/'.gitignore',path/'.gitignore');(path/'DEV_CREDENTIALS.local.md').write_text('No credentials in this verification fixture.',encoding='utf8')
 result=subprocess.run(['git','init','-q',str(path)],capture_output=True);assert result.returncode==0
 result=subprocess.run(['git','-C',str(path),'check-ignore','-v','--no-index','DEV_CREDENTIALS.local.md'],capture_output=True,text=True);assert result.returncode==0 and 'DEV_CREDENTIALS.local.md' in result.stdout
print('Git ignore pattern: PASS in isolated temporary repository; project itself has no Git repository.')
for port in (3000,8000):
 try:
  with urllib.request.urlopen(f'http://127.0.0.1:{port}/DEV_CREDENTIALS.local.md',timeout=10) as response:status=response.status
 except urllib.error.HTTPError as error:status=error.code
 assert status in (401,404),status
 print('Local public credential-file URL:',port,'blocked with HTTP',status)
assert 'DEV_CREDENTIALS.local.md' in (root/'.dockerignore').read_text()
assert not (root/'frontend/public/DEV_CREDENTIALS.local.md').exists()
assert not any(p.name=='DEV_CREDENTIALS.local.md' for p in (root/'frontend/.next').rglob('*'))
print('Docker exclusions and public artifact paths: PASS')
