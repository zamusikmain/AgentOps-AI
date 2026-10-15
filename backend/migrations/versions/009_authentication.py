"""Add password users and opaque server sessions. Existing rows/tables untouched."""
from alembic import op
from sqlalchemy import inspect
from app.db import Base
revision='009'
down_revision='008'
branch_labels=None
depends_on=None
def upgrade():
 bind=op.get_bind();existing=set(inspect(bind).get_table_names())
 for name in ('users','user_sessions','login_attempts','auth_audit','password_resets'):
  if name not in existing:Base.metadata.tables[name].create(bind)
def downgrade():
 raise RuntimeError('Destructive auth downgrade requires explicit review; preserve user/session data.')
