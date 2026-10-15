"""Add only orchestration metadata; legacy evaluation remains the quality store."""
from alembic import op
from app.db import Base
from sqlalchemy import inspect
revision='008';down_revision='007';branch_labels=None;depends_on=None
def upgrade():
 Base.metadata.tables['validation_runs'].create(op.get_bind())
 existing={i['name'] for i in inspect(op.get_bind()).get_indexes('llm_executions')}
 for name,columns in [('ix_llm_tenant_created',['tenant_id','created_at']),('ix_llm_tenant_trace_created',['tenant_id','trace_id','created_at'])]:
  if name not in existing:op.create_index(name,'llm_executions',columns)
def downgrade():
 op.drop_index('ix_llm_tenant_trace_created',table_name='llm_executions');op.drop_index('ix_llm_tenant_created',table_name='llm_executions');Base.metadata.tables['validation_runs'].drop(op.get_bind())
