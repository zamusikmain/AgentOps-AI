"""Durable evaluation history, additive to knowledge/vector storage."""
from alembic import op
import sqlalchemy as sa
revision='006';down_revision='005';branch_labels=None;depends_on=None
def upgrade():
    op.create_table('evaluation_runs',sa.Column('id',sa.String(36),primary_key=True),sa.Column('agent_id',sa.String(36),nullable=False),sa.Column('document_ids',sa.JSON(),nullable=False),sa.Column('dataset_version',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('provider_metadata',sa.JSON(),nullable=False),sa.Column('metrics',sa.JSON(),nullable=False),sa.Column('error',sa.String(80)),sa.Column('duration_ms',sa.Integer()),sa.Column('created_at',sa.String(40),nullable=False),sa.Column('finished_at',sa.String(40)))
    op.create_index('ix_evaluation_runs_agent_id','evaluation_runs',['agent_id'])
    op.create_table('evaluation_cases',sa.Column('id',sa.String(36),primary_key=True),sa.Column('run_id',sa.String(36),sa.ForeignKey('evaluation_runs.id'),nullable=False),sa.Column('case_id',sa.String(40),nullable=False),sa.Column('mode',sa.String(20),nullable=False),sa.Column('result',sa.JSON(),nullable=False))
    op.create_index('ix_evaluation_cases_run_id','evaluation_cases',['run_id'])
def downgrade():
    op.drop_table('evaluation_cases');op.drop_table('evaluation_runs')
