from .db import Agent, Workflow, WorkflowRun, serialize
from .repository import Repository
from .services import required, ServiceError
from .workflow_execution import run_view

class WorkflowService:
    def __init__(self,sessions,runner,settings,launch_lock,job_count):
        self.sessions,self.runner,self.settings,self.launch_lock,self.job_count=sessions,runner,settings,launch_lock,job_count

    def save(self,body,identifier=None):
        with self.sessions() as db:
            repo=Repository(db)
            agents=[required(repo,Agent,aid) for aid in body.agent_ids]
            if agents[-1].role!='reviewer' or any(a.role=='reviewer' for a in agents[:-1]):
                raise ServiceError(422,'reviewer_must_be_last')
            if identifier:
                row=required(repo,Workflow,identifier)
                if repo.count(WorkflowRun,(WorkflowRun.workflow_id==identifier)&WorkflowRun.status.in_(['queued','running'])):
                    raise ServiceError(409,'workflow_running')
                for k,v in body.model_dump().items():
                    setattr(row,k,v)
            else:
                row=repo.add(Workflow(**body.model_dump()))
            db.commit()
            return serialize(row)

    def delete(self,identifier):
        with self.sessions() as db:
            repo=Repository(db)
            row=required(repo,Workflow,identifier)
            if repo.count(WorkflowRun,WorkflowRun.workflow_id==identifier):
                raise ServiceError(409,'workflow_has_history')
            repo.delete(row);db.commit()

    async def launch(self,identifier,body):
        async with self.launch_lock:
            with self.sessions() as db:
                repo=Repository(db)
                workflow=required(repo,Workflow,identifier)
                if workflow.status!='active':
                    raise ServiceError(409,'workflow_disabled')
                agents=[required(repo,Agent,aid) for aid in workflow.agent_ids]
                if any(a.status!='active' for a in agents):
                    raise ServiceError(409,'agent_disabled')
                if agents[-1].role!='reviewer' or any(a.role=='reviewer' for a in agents[:-1]):
                    raise ServiceError(422,'reviewer_must_be_last')
                if self.job_count()>=10:
                    raise ServiceError(429,'queue_full')
                if self.settings.llm_provider=='gemini' and not self.settings.gemini_api_key.get_secret_value():
                    raise ServiceError(503,'missing_api_key')
                snapshot={**serialize(workflow),'agents':[serialize(a) for a in agents], 'task':body.model_dump()}
                snapshot['timeout_seconds']=min(workflow.timeout_seconds,self.settings.execution_timeout_seconds)
                run=repo.add(WorkflowRun(workflow_id=identifier,title=body.title,prompt=body.prompt,snapshot=snapshot))
                db.commit()
                self.runner.start(run.id)
                return run_view(run)

    def cancel(self,identifier):
        with self.sessions() as db:
            run=required(Repository(db),WorkflowRun,identifier)
            if run.status not in ('queued','running'):
                raise ServiceError(409,'execution_finished')
        self.runner.cancel(identifier)
        return {'status':'cancelled'}
