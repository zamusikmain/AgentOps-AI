"""Resolve original fixture identity declarations without executing test code."""
import ast,json
from pathlib import Path
def resolve(root,manifest):
 result=[]
 def value(node,symbols,depth=0):
  if depth>6:return None
  if isinstance(node,ast.Name):return value(symbols.get(node.id),symbols,depth+1)
  if isinstance(node,ast.Call) and getattr(node.func,'id',None)=='SecretStr' and node.args:return value(node.args[0],symbols,depth+1)
  try:return ast.literal_eval(node)
  except (ValueError,TypeError):return None
 for identity in manifest:
  source=identity['source']
  if source=='Current running local workspace':
   from app.config import Settings
   token=Settings().api_token.get_secret_value() or (root/'backend/.local-token').read_text().strip()
  else:
   path,line=source.split(':',1);line=int(line.split()[0]);tree=ast.parse((root/path).read_text(encoding='utf-8-sig'));symbols={}
   for n in ast.walk(tree):
    if isinstance(n,ast.Assign):
     for target in n.targets:
      if isinstance(target,ast.Name):symbols[target.id]=n.value
    if isinstance(n,ast.ImportFrom) and n.module and n.module.startswith('test_'):
     dependency=root/'backend/tests'/(n.module+'.py')
     if dependency.exists():
      for a in ast.walk(ast.parse(dependency.read_text(encoding='utf-8-sig'))):
       if isinstance(a,ast.Assign):
        for t in a.targets:
         if isinstance(t,ast.Name):
          for alias in n.names:
           if alias.name==t.id:symbols[alias.asname or alias.name]=a.value
   call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and n.lineno==line and any(k.arg in ('api_token','llm_principals') for k in n.keywords))
   kwargs={k.arg:k.value for k in call.keywords};principals=value(kwargs.get('llm_principals'),symbols) or []
   match=next((p for p in principals if p['user']==identity['user'] and p['tenant']==identity['tenant'] and p.get('role','viewer')==identity['role']),None)
   token=match['token'] if match else value(kwargs.get('api_token'),symbols)
  if not isinstance(token,str) or not token:raise RuntimeError('Fixture identity could not be resolved; do not invent credentials')
  result.append({**identity,'token':token})
 return result
