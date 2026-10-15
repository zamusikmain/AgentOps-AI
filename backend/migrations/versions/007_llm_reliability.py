"""Additive metadata, configuration, prompt and budget persistence."""
from alembic import op
from app.db import Base
revision='007';down_revision='006';branch_labels=None;depends_on=None
def upgrade():
    for name in ('llm_configurations','prompt_versions','llm_executions','budget_reservations','evaluation_comparisons'):
        Base.metadata.tables[name].create(op.get_bind())
def downgrade():
    for name in ('evaluation_comparisons','budget_reservations','llm_executions','prompt_versions','llm_configurations'):
        Base.metadata.tables[name].drop(op.get_bind())
