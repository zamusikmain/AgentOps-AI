"""Immutable isolated synthetic live smoke corpus; reference data never enters prompts."""
import hashlib,json
from pathlib import Path
PATH=Path(__file__).resolve().parents[2]/'docs/fixtures/gemini-live-smoke-v1.json'
def corpus():
 raw=PATH.read_bytes();data=json.loads(raw)
 if data['id']!='gemini-live-smoke-v1' or len(data['questions'])!=12:raise ValueError('smoke_dataset_invalid')
 return data,hashlib.sha256(raw).hexdigest()
