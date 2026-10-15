from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
credential=(root/'backend/.local-token').read_text().strip()
assert len(credential)>20
for directory in (root/'frontend/.next/static',root/'frontend/public'):
 if directory.exists():
  for file in directory.rglob('*'):
   if file.is_file():assert credential.encode() not in file.read_bytes(),'Local owner credential in public artifact'
print('Public static bundle owner credential scan: PASS')
