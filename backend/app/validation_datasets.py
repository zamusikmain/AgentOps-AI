"""Immutable tenant dataset sidecars; built-in Gold files are never edited."""
import json,hashlib,re
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict,model_validator
from sqlalchemy import select
from .db import LLMConfiguration,serialize
from .evaluation import dataset
from .services import ServiceError
class Evidence(BaseModel):
 model_config=ConfigDict(extra='forbid')
 document_id:str=Field(max_length=80)
 page:int=Field(ge=1,le=200)
 contains:str=Field(default='',max_length=1000)
class Question(BaseModel):
 model_config=ConfigDict(extra='forbid')
 id:str=Field(pattern=r'^[a-zA-Z0-9_-]{1,60}$')
 question:str=Field(min_length=1,max_length=2000)
 language:Literal['ru','en']
 expected_behavior:Literal['answer','abstain','partial']
 expected_answer:list[str]=Field(default_factory=list,max_length=20)
 expected_sources:list[Evidence]=Field(default_factory=list,max_length=10)
 scope:list[str]=Field(default_factory=list,max_length=50)
 difficulty:Literal['easy','medium','hard']='medium'
 category:str=Field(default='independent',max_length=50)
 split:Literal['development','calibration','holdout']='holdout'
 @model_validator(mode='after')
 def sources(self):
  if len(set(self.scope))!=len(self.scope) or any(e.document_id not in self.scope for e in self.expected_sources):raise ValueError('invalid evidence scope')
  if self.expected_behavior!='abstain' and not self.expected_answer:raise ValueError('expected answer required')
  return self
class DatasetInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 id:str=Field(pattern=r'^[a-z][a-z0-9_-]{0,59}$')
 version:int=Field(ge=1,le=10000)
 name:str=Field(min_length=1,max_length=120)
 classification:Literal['public','internal','sensitive']='internal'
 questions:list[Question]=Field(min_length=1,max_length=200)
 @model_validator(mode='after')
 def unique(self):
  if len(set(q.id for q in self.questions))!=len(self.questions):raise ValueError('duplicate question id')
  return self
class Datasets:
 def __init__(self,sessions):self.sessions=sessions
 def seed(self):
  for name,source,split in [('original40','v1',None),('expanded64','v2',None),('holdout12','v2','holdout')]:
   data,digest=dataset(source);cases=[c for c in data['cases'] if split is None or c.get('split')==split]
   body={'id':name,'version':1,'name':name,'classification':'public','source':source,'source_hash':digest,'split':split,'questions':[{**c,'language':'ru' if re.search('[а-яА-Я]',c['question']) else 'en','difficulty':'hard' if c['category'] in ('multi-hop','adversarial') else 'medium','split':c.get('split','development')} for c in cases]}
   self.save('workspace',body)
 def save(self,tenant,body):
  raw=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':'));digest=hashlib.sha256(raw.encode()).hexdigest();body={**body,'hash':digest}
  if re.search(r'AIza[\w-]{20,}|(?:api[_-]?key|password)\s*[:=]\s*[^\s"]+',raw,re.I):raise ServiceError(422,'dataset_secret_denied')
  if len(raw.encode())>300000:raise ServiceError(422,'dataset_too_large')
  with self.sessions() as db:
   key=f'{tenant}:validation_dataset:{body["id"]}:{body["version"]}';r=db.get(LLMConfiguration,key)
   if r:
    if r.body['hash']!=digest:raise ServiceError(409,'dataset_version_immutable')
    return self.describe(r.body)
   r=LLMConfiguration(id=key,tenant_id=tenant,kind='validation_dataset',name=body['id'],version=body['version'],body=body);db.add(r);db.commit();return self.describe(body)
 def read(self,tenant,identifier,version):
  with self.sessions() as db:r=db.get(LLMConfiguration,f'{tenant}:validation_dataset:{identifier}:{version}');body=r.body if r else None
  if not body:raise ServiceError(404,'dataset_not_found')
  check={k:v for k,v in body.items() if k!='hash'}
  if hashlib.sha256(json.dumps(check,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=body['hash']:raise ServiceError(409,'dataset_integrity_failed')
  if body.get('source') and dataset(body['source'])[1]!=body['source_hash']:raise ServiceError(409,'dataset_integrity_failed')
  return body
 def describe(self,body):return {k:body[k] for k in ('id','version','hash','name','classification')}|{'questions':len(body['questions']),'source':body.get('source'),'splits':{s:sum(q.get('split','development')==s for q in body['questions']) for s in ('development','calibration','holdout')}}
 def list(self,tenant):
  with self.sessions() as db:return [self.describe(r.body) for r in db.scalars(select(LLMConfiguration).where(LLMConfiguration.tenant_id==tenant,LLMConfiguration.kind=='validation_dataset'))]
