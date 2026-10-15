import ast
import json
import math
import operator
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from jsonschema import Draft202012Validator

class Arguments(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
class CalculatorArgs(Arguments):
    expression:str=Field(min_length=1,max_length=200)
class EmptyArgs(Arguments): pass
class DateArgs(Arguments):
    operation:Literal['now','add_days','difference_days']='now'
    date:str|None=Field(default=None,max_length=40)
    other_date:str|None=Field(default=None,max_length=40)
    days:int=Field(default=0,ge=-36500,le=36500)
class JsonArgs(Arguments):
    document:str=Field(max_length=16000)
    validation_schema:dict|None=Field(default=None,alias='schema')
class FetchArgs(Arguments):
    url:str=Field(min_length=1,max_length=2048)
class SearchArgs(Arguments):
    query:str=Field(min_length=1,max_length=200)
    limit:int=Field(default=3,ge=1,le=5)
class KnowledgeArgs(SearchArgs):
    document_ids:list[str]|None=Field(default=None,max_length=50)
    mode:Literal['lexical','semantic','hybrid']='hybrid'
    rerank:bool=True
class NoteArgs(Arguments):
    text:str=Field(min_length=1,max_length=2000)

MODELS={'calculator':CalculatorArgs,'utc_time':EmptyArgs,'datetime':DateArgs,'json_validator':JsonArgs,
        'http_fetch':FetchArgs,'knowledge_search':KnowledgeArgs,'save_note':NoteArgs,
        'mcp_local_time':EmptyArgs,'mcp_knowledge_search':KnowledgeArgs}
DESCRIPTIONS={'calculator':'Bounded arithmetic via AST; no code execution.','utc_time':'Current UTC time.',
 'datetime':'UTC time, add days or date difference using ISO 8601 dates.',
 'json_validator':'Parse JSON and optionally validate against a bounded JSON Schema; no external references.',
 'http_fetch':'Fetch a configured exact HTTPS URL, public IPs only, bounded text response.',
 'knowledge_search':'Search explicitly permitted indexed PDF documents, or bundled fixtures when no PDFs are assigned. Returns document, page, chunk and evidence.',
 'save_note':'Append a note to this application SQLite after explicit human approval.',
 'mcp_local_time':'Read current UTC time from the trusted bundled MCP server.',
 'mcp_knowledge_search':'Search bundled test documents through the trusted local MCP server.'}
CATALOG=[{'id':name,'name':name,'description':DESCRIPTIONS[name],'side_effects':name=='save_note',
 'access':'write' if name=='save_note' else 'read-only','timeout_seconds':10 if name=='http_fetch' else 5,
 'max_calls':4,'max_result_bytes':16384,'status':'configured' if name.startswith('mcp_') else 'available',
 'source':'local-mcp' if name.startswith('mcp_') else 'builtin','parameters':model.model_json_schema()}
 for name,model in MODELS.items()]

def declarations(allowed):
    return [{'name':t['name'],'description':t['description'],'parameters_json_schema':t['parameters']} for t in CATALOG if t['name'] in allowed]

def validated(name,arguments,allowed):
    if name not in allowed or name not in MODELS:raise ValueError('tool_denied')
    if not isinstance(arguments,dict) or len(json.dumps(arguments).encode())>20000:raise ValueError('tool_invalid_arguments')
    try:return MODELS[name].model_validate(arguments).model_dump(by_alias=True)
    except Exception:raise ValueError('tool_invalid_arguments') from None

def calculate(expression):
    tree=ast.parse(expression,mode='eval')
    if len(list(ast.walk(tree)))>60:raise ValueError('invalid_expression')
    ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}
    def walk(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):value=n.value
        elif isinstance(n,ast.BinOp) and type(n.op) in ops:value=ops[type(n.op)](walk(n.left),walk(n.right))
        elif isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):value=walk(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
        else:raise ValueError('invalid_expression')
        if not math.isfinite(value) or abs(value)>1e15:raise ValueError('invalid_expression')
        return value
    return {'value':walk(tree.body)}

def iso(value):
    if not value:raise ValueError('tool_invalid_arguments')
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

def search(query,limit=3):
    # Explicit filenames, no model-controlled paths or file discovery.
    root=Path(__file__).resolve().parent/'knowledge'
    words=query.casefold().split()
    result=[]
    for name in ('portal.md','security.md'):
        content=(root/name).read_text(encoding='utf8')
        score=sum(word in content.casefold() for word in words)
        if score:result.append({'document_id':name,'score':score,'excerpt':content[:4000]})
    return {'matches':sorted(result,key=lambda d:-d['score'])[:limit],'scope':'bundled-test-documents'}

def check_schema(schema):
    if len(json.dumps(schema))>8000:raise ValueError('tool_invalid_schema')
    def walk(v,depth=0):
        if depth>12:raise ValueError('tool_invalid_schema')
        if isinstance(v,dict):
            if any(k in v for k in ('$ref','$dynamicRef','$recursiveRef','pattern','patternProperties','allOf','anyOf','oneOf','not','if','then','else','contains','dependentSchemas','unevaluatedProperties','unevaluatedItems')):raise ValueError('tool_invalid_schema')
            for child in v.values():walk(child,depth+1)
        elif isinstance(v,list):
            for child in v:walk(child,depth+1)
    walk(schema);Draft202012Validator.check_schema(schema)

def invoke(name,arguments,allowed):
    a=validated(name,arguments,allowed)
    if name=='calculator':return calculate(a['expression'])
    if name in ('utc_time','mcp_local_time'):return {'utc':datetime.now(timezone.utc).isoformat()}
    if name=='datetime':
        if a['operation']=='now':return {'utc':datetime.now(timezone.utc).isoformat()}
        if a['operation']=='add_days':return {'date':(iso(a['date'])+timedelta(days=a['days'])).isoformat()}
        return {'days':(iso(a['other_date'])-iso(a['date'])).total_seconds()/86400}
    if name=='json_validator':
        try:data=json.loads(a['document'],parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError,RecursionError):return {'valid':False,'errors':['invalid_json']}
        if a['schema'] is not None:
            check_schema(a['schema'])
            errors=list(Draft202012Validator(a['schema']).iter_errors(data))[:10]
            return {'valid':not errors,'errors':[{'path':list(e.path),'keyword':e.validator} for e in errors]}
        return {'valid':True,'type':type(data).__name__}
    if name in ('knowledge_search','mcp_knowledge_search'):
        a.pop('document_ids',None)
        a.pop('mode',None);a.pop('rerank',None)
        return search(**a)
    raise ValueError('tool_requires_executor')

class ToolRegistry:
    """Pinned IDs and schemas shared by builtin tools and verified MCP discovery."""
    def __init__(self):self.definitions={t['name']:dict(t) for t in CATALOG}
    def import_mcp(self,discovered,mapping):
        for identifier,remote_name in mapping.items():
            remote=next(t for t in discovered if t['name']==remote_name)
            if remote['inputSchema']!=MODELS[identifier].model_json_schema():raise ValueError('mcp_schema_denied')
            self.definitions[identifier]={**self.definitions[identifier],'description':remote['description'],'parameters':remote['inputSchema'],'access':'read-only','side_effects':False,'source':'local-mcp'}
    def catalog(self):return list(self.definitions.values())
