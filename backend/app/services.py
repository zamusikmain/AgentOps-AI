import asyncio
from .repository import Repository
from .db import Agent, Task, Execution, Workflow, serialize
from sqlalchemy import select

class ServiceError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code

def required(repository, entity, identifier):
    row = repository.get(entity, identifier)
    if row is None:
        raise ServiceError(404, 'not_found')
    return row

class WorkspaceService:
    """Business invariants shared by HTTP and future workers/CLI adapters."""
    def __init__(self, sessions, runner, settings):
        self.sessions, self.runner, self.settings = sessions, runner, settings
        self.launch_lock = asyncio.Lock()
        self.job_count = lambda:len(self.runner.jobs)

    def create_agent(self, body):
        if body.document_ids:self.knowledge.validate_scope(body.document_ids)
        with self.sessions() as db:
            row = Repository(db).add(Agent(**body.model_dump()))
            db.commit()
            return serialize(row)

    def update_agent(self, identifier, body):
        if body.document_ids:self.knowledge.validate_scope(body.document_ids)
        with self.sessions() as db:
            row = required(Repository(db), Agent, identifier)
            for key, value in body.model_dump().items():
                setattr(row, key, value)
            db.commit()
            return serialize(row)

    def delete_agent(self, identifier):
        with self.sessions() as db:
            repo = Repository(db)
            row = required(repo, Agent, identifier)
            if repo.count(Task, Task.agent_id == identifier) or any(identifier in w.agent_ids for w in db.scalars(select(Workflow))):
                raise ServiceError(409, 'agent_in_use')
            repo.delete(row)
            db.commit()

    def save_task(self, body, identifier=None):
        with self.sessions() as db:
            repo = Repository(db)
            required(repo, Agent, body.agent_id)
            if identifier:
                row = required(repo, Task, identifier)
                if row.status == 'running':
                    raise ServiceError(409, 'task_running')
                for key, value in body.model_dump().items():
                    setattr(row, key, value)
                row.status = 'draft'
            else:
                row = repo.add(Task(**body.model_dump()))
            db.commit()
            return serialize(row)

    def delete_task(self, identifier):
        with self.sessions() as db:
            repo = Repository(db)
            row = required(repo, Task, identifier)
            if repo.count(Execution, Execution.task_id == identifier):
                raise ServiceError(409, 'task_has_history')
            repo.delete(row)
            db.commit()

    async def launch(self, identifier):
        async with self.launch_lock:
            with self.sessions() as db:
                repo = Repository(db)
                task = required(repo, Task, identifier)
                agent = required(repo, Agent, task.agent_id)
                if agent.status != 'active':
                    raise ServiceError(409, 'agent_disabled')
                if task.status == 'running':
                    raise ServiceError(409, 'task_running')
                if self.job_count() >= 10:
                    raise ServiceError(429, 'queue_full')
                if self.settings.llm_provider == 'gemini' and not self.settings.gemini_api_key.get_secret_value():
                    raise ServiceError(503, 'missing_api_key')
                row = repo.add(Execution(task_id=task.id, agent_id=agent.id, snapshot={**serialize(agent), 'prompt': task.prompt}))
                task.status = 'running'
                db.commit()
                self.runner.start(row.id)
                return {k:v for k,v in serialize(row).items() if k != 'snapshot'}

    def cancel(self, identifier):
        with self.sessions() as db:
            row = required(Repository(db), Execution, identifier)
            if row.status not in ('queued', 'running'):
                raise ServiceError(409, 'execution_finished')
        self.runner.cancel(identifier)
        self.runner.finish(identifier, 'cancelled')
        return {'status': 'cancelled'}
