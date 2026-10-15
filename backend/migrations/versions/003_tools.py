"""Tool history and approved application notes; preserves existing tables."""
from alembic import op
import sqlalchemy as sa
revision='003'
down_revision='002'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('tool_calls',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('run_kind',sa.String(20),nullable=False),sa.Column('run_id',sa.String(36),nullable=False),
        sa.Column('stage_id',sa.String(36),nullable=True),sa.Column('tool_id',sa.String(80),nullable=False),
        sa.Column('operation_key',sa.String(128),nullable=False,unique=True),sa.Column('arguments',sa.JSON(),nullable=False),
        sa.Column('access',sa.String(20),nullable=False),sa.Column('status',sa.String(30),nullable=False),
        sa.Column('result',sa.JSON(),nullable=True),sa.Column('error',sa.String(80),nullable=True),
        sa.Column('duration_ms',sa.Integer(),nullable=True),sa.Column('decision',sa.String(20),nullable=True),
        sa.Column('decided_at',sa.String(40),nullable=True),sa.Column('created_at',sa.String(40),nullable=False),
        sa.Column('finished_at',sa.String(40),nullable=True))
    op.create_index('ix_tool_calls_run_kind','tool_calls',['run_kind'])
    op.create_index('ix_tool_calls_run_id','tool_calls',['run_id'])
    op.create_table('tool_notes',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('call_id',sa.String(36),sa.ForeignKey('tool_calls.id'),nullable=False,unique=True),
        sa.Column('text',sa.Text(),nullable=False),sa.Column('created_at',sa.String(40),nullable=False))

def downgrade():
    op.drop_table('tool_notes');op.drop_table('tool_calls')
