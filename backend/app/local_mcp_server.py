"""Bundled read-only MCP server, pinned protocol 2025-11-25, newline JSON-RPC over stdio."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.tools import MODELS,DESCRIPTIONS,invoke,validated
TOOLS={'local_time':'mcp_local_time','knowledge_search':'mcp_knowledge_search'}
initialized=False
ready=False
for line in sys.stdin.buffer:
    if len(line)>65536:break
    try:
        req=json.loads(line);method=req.get('method');ident=req.get('id');params=req.get('params',{})
        if method=='notifications/initialized':
            ready=initialized;continue
        if ident is None:continue
        if method=='initialize':
            if params.get('protocolVersion')!='2025-11-25':raise ValueError('unsupported_version')
            initialized=True
            result={'protocolVersion':'2025-11-25','capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'agentops-bundled-readonly','version':'0.3.0'}}
        elif not ready:raise ValueError('not_initialized')
        elif method=='tools/list':
            result={'tools':[{'name':name,'description':DESCRIPTIONS[tool],'inputSchema':MODELS[tool].model_json_schema(),'annotations':{'readOnlyHint':True,'destructiveHint':False}} for name,tool in TOOLS.items()]}
        elif method=='tools/call':
            tool=TOOLS.get(params.get('name'))
            if not tool:raise ValueError('tool_denied')
            try:
                validated(tool,params.get('arguments',{}),[tool])
                evidence=params.get('knowledgeEvidence')
                if evidence is not None:
                    if tool!='mcp_knowledge_search' or not isinstance(evidence,dict) or evidence.get('scope')!='uploaded-pdf' or not isinstance(evidence.get('matches'),list) or len(json.dumps(evidence).encode())>16384:raise ValueError('tool_invalid_arguments')
                    value=evidence
                else:value=invoke(tool,params.get('arguments',{}),[tool])
                result={'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'structuredContent':value,'isError':False}
            except Exception:result={'content':[{'type':'text','text':'tool_invalid_arguments'}],'isError':True}
        elif method=='ping':result={}
        else:raise ValueError('method_not_found')
        response={'jsonrpc':'2.0','id':ident,'result':result}
    except Exception:response={'jsonrpc':'2.0','id':req.get('id') if isinstance(locals().get('req'),dict) else None,'error':{'code':-32602,'message':'invalid_request'}}
    sys.stdout.buffer.write((json.dumps(response,ensure_ascii=False)+'\n').encode('utf8'));sys.stdout.buffer.flush()
