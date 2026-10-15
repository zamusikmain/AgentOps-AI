from typing import Literal
from fastapi import APIRouter,Query
from pydantic import BaseModel,ConfigDict
from sqlalchemy import select
from .db import ToolCall,serialize
from .repository import Repository
from .services import required,ServiceError
class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    decision:Literal['approve','reject']
def tool_router(sessions,executor):
    router=APIRouter(prefix='/api',tags=['Tools'])
    @router.get('/mcp-servers')
    def servers():return {'items':[executor.server_view()]}
    @router.post('/mcp-servers/local-readonly/discover')
    async def discover():
        try:await executor.discover()
        except Exception:raise ServiceError(503,"mcp_unavailable") from None
        return executor.server_view()
    @router.get('/tool-calls')
    def calls(run_kind:Literal['single','workflow'],run_id:str,offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100)):
        with sessions() as db:
            predicate=(ToolCall.run_kind==run_kind)&(ToolCall.run_id==run_id)
            return {'items':[serialize(t) for t in db.scalars(select(ToolCall).where(predicate).order_by(ToolCall.created_at,ToolCall.id).offset(offset).limit(limit))],'total':Repository(db).count(ToolCall,predicate),'offset':offset,'limit':limit}
    @router.post('/tool-calls/{identifier}/decision')
    def decide(identifier:str,body:Decision):return executor.decide(identifier,body.decision)
    return router
