"""Initial application schema."""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('agents',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('name', sa.String(120), nullable=False),
        sa.Column('role', sa.String(30), nullable=False), sa.Column('instructions', sa.Text(), nullable=False),
        sa.Column('model', sa.String(120), nullable=False), sa.Column('tools', sa.JSON(), nullable=False),
        sa.Column('max_steps', sa.Integer(), nullable=False), sa.Column('max_tokens', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('created_at', sa.String(40), nullable=False))
    op.create_table('tasks', sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(200), nullable=False), sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('created_at', sa.String(40), nullable=False))
    op.create_table('executions', sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id'), nullable=False),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False), sa.Column('status', sa.String(20), nullable=False),
        sa.Column('result', sa.Text()), sa.Column('error', sa.String(100)),
        sa.Column('input_tokens', sa.Integer(), nullable=False), sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('estimated_cost_usd', sa.Float()), sa.Column('duration_ms', sa.Integer()),
        sa.Column('created_at', sa.String(40), nullable=False), sa.Column('finished_at', sa.String(40)))
    op.create_table('execution_events', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('execution_id', sa.String(36), sa.ForeignKey('executions.id'), nullable=False),
        sa.Column('kind', sa.String(40), nullable=False), sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.String(40), nullable=False))
    op.create_index('ix_execution_events_execution', 'execution_events', ['execution_id'])
    op.create_index('ix_executions_task', 'executions', ['task_id'])

def downgrade():
    op.drop_table('execution_events')
    op.drop_table('executions')
    op.drop_table('tasks')
    op.drop_table('agents')
