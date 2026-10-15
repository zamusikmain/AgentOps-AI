import asyncio
import json
import os
import sys
import subprocess
from pathlib import Path
from .tools import MODELS

class MCPError(ValueError):pass
class LocalMCP:
    mapping={'mcp_local_time':'local_time','mcp_knowledge_search':'knowledge_search'}
    def __init__(self,enabled=True,startup_timeout_seconds=20):
        self.enabled=enabled;self.startup_timeout_seconds=startup_timeout_seconds;self.process=None;self.lock=asyncio.Lock();self.counter=0;self.status='disconnected';self.discovered=[]
    async def rpc(self,method,params=None,notification=False,timeout_seconds=5):
        if not self.process or self.process.returncode is not None:raise MCPError('mcp_disconnected')
        self.counter+=1;request={'jsonrpc':'2.0','method':method,'params':params or {}}
        if not notification:request['id']=self.counter
        self.process.stdin.write((json.dumps(request)+'\n').encode());await self.process.stdin.drain()
        if notification:return
        try:
            raw=await asyncio.wait_for(self.process.stdout.readline(),timeout_seconds)
            if not raw or len(raw)>65536:raise MCPError('mcp_disconnected')
            response=json.loads(raw)
            if response.get('id')!=self.counter or response.get('jsonrpc')!='2.0' or 'error' in response:raise MCPError('mcp_protocol_error')
            return response['result']
        except (TimeoutError,ValueError,KeyError):raise MCPError('mcp_protocol_error') from None
    async def discover(self):
        async with self.lock:
            await self.close()
            if not self.enabled:self.status='disabled';return []
            try:
                env={k:v for k,v in os.environ.items() if k in ('SystemRoot','WINDIR','TEMP','TMP')}
                self.process=await asyncio.create_subprocess_exec(sys.executable,'-I',str(Path(__file__).with_name('local_mcp_server.py')),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,env=env,limit=65536,**({"creationflags":subprocess.CREATE_NO_WINDOW} if os.name=="nt" else {}))
                info=await self.rpc('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'agentops','version':'0.3.0'}},timeout_seconds=self.startup_timeout_seconds)
                if info.get('protocolVersion')!='2025-11-25':raise MCPError('mcp_protocol_error')
                await self.rpc('notifications/initialized',notification=True)
                items=(await self.rpc('tools/list')).get('tools',[])
                if len(items)!=2:raise MCPError('mcp_schema_denied')
                for local,remote in self.mapping.items():
                    matches=[t for t in items if t.get('name')==remote]
                    if len(matches)!=1 or matches[0].get('inputSchema')!=MODELS[local].model_json_schema():raise MCPError('mcp_schema_denied')
                self.discovered=items;self.status='available';return items
            except Exception:
                await self.close();self.status='unavailable';raise MCPError('mcp_unavailable') from None
    async def call(self,name,args,knowledge_evidence=None):
        async with self.lock:
            if self.status!='available' or name not in self.mapping:raise MCPError('mcp_unavailable')
            try:
                params={'name':self.mapping[name],'arguments':args}
                if knowledge_evidence is not None:params['knowledgeEvidence']=knowledge_evidence
                result=await self.rpc('tools/call',params)
                if result.get('isError'):raise MCPError('mcp_tool_error')
                value=result.get('structuredContent')
                if not isinstance(value,dict) or len(json.dumps(value).encode())>16384:raise MCPError('tool_result_limit')
                return value
            except BaseException:
                await self.close();self.status='unavailable';raise
    async def close(self):
        if self.process:
            if self.process.returncode is None:
                self.process.kill()
            await self.process.communicate();self.process=None
        self.discovered=[]
        if self.status=='available':self.status='disconnected'
