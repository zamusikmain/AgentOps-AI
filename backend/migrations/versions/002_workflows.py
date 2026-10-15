"""Add workflows without modifying existing single-agent tables."""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('workflows', sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False), sa.Column('agent_ids', sa.JSON(), nullable=False),
        sa.Column('retry_from', sa.Integer(), nullable=False), sa.Column('max_revisions', sa.Integer(), nullable=False),
        sa.Column('max_calls', sa.Integer(), nullable=False), sa.Column('max_total_tokens', sa.Integer(), nullable=False),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False), sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.String(40), nullable=False))
    op.create_table('workflow_runs', sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workflow_id', sa.String(36), sa.ForeignKey('workflows.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False), sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False), sa.Column('status', sa.String(20), nullable=False),
        sa.Column('current_stage', sa.Integer()), sa.Column('current_agent_id', sa.String(36)),
        sa.Column('revisions', sa.Integer(), nullable=False), sa.Column('calls', sa.Integer(), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False), sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('result', sa.JSON()), sa.Column('error', sa.String(100)), sa.Column('duration_ms', sa.Integer()),
        sa.Column('started_at', sa.String(40)), sa.Column('finished_at', sa.String(40)),
        sa.Column('created_at', sa.String(40), nullable=False))
    op.create_table('workflow_steps', sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('workflow_runs.id'), nullable=False),
        sa.Column('stage_index', sa.Integer(), nullable=False), sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.String(36), nullable=False), sa.Column('agent_name', sa.String(120), nullable=False),
        sa.Column('role', sa.String(30), nullable=False), sa.Column('status', sa.String(20), nullable=False),
        sa.Column('input', sa.JSON(), nullable=False), sa.Column('output', sa.JSON()), sa.Column('raw_output', sa.Text()),
        sa.Column('error', sa.String(100)), sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False), sa.Column('duration_ms', sa.Integer()),
        sa.Column('finished_at', sa.String(40)), sa.Column('created_at', sa.String(40), nullable=False))
    op.create_table('workflow_events', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('workflow_runs.id'), nullable=False),
        sa.Column('kind', sa.String(40), nullable=False), sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.String(40), nullable=False))
    op.create_index('ix_workflow_steps_run_id', 'workflow_steps', ['run_id'])
    op.create_index('ix_workflow_events_run_id', 'workflow_events', ['run_id'])
    op.create_index('ix_workflow_runs_workflow_id', 'workflow_runs', ['workflow_id'])

def downgrade():
    for table in ('workflow_events', 'workflow_steps', 'workflow_runs', 'workflows'):
        op.drop_table(table)
