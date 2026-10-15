"""PDF knowledge index and explicit agent document scope."""
from alembic import op
import sqlalchemy as sa
revision='004'
down_revision='003'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('agents',sa.Column('document_ids',sa.JSON(),nullable=False,server_default='[]'))
    op.create_table('knowledge_documents',sa.Column('id',sa.String(36),primary_key=True),sa.Column('name',sa.String(200),nullable=False),sa.Column('sha256',sa.String(64),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('error',sa.String(80),nullable=True),sa.Column('pages',sa.Integer(),nullable=False),sa.Column('chunks',sa.Integer(),nullable=False),sa.Column('bytes',sa.Integer(),nullable=False),sa.Column('created_at',sa.String(40),nullable=False))
    op.create_table('knowledge_chunks',sa.Column('id',sa.String(36),primary_key=True),sa.Column('document_id',sa.String(36),sa.ForeignKey('knowledge_documents.id'),nullable=False),sa.Column('page',sa.Integer(),nullable=False),sa.Column('ordinal',sa.Integer(),nullable=False),sa.Column('text',sa.Text(),nullable=False),sa.Column('terms',sa.JSON(),nullable=False))
    op.create_index('ix_knowledge_chunks_document_id','knowledge_chunks',['document_id'])
def downgrade():
    op.drop_table('knowledge_chunks');op.drop_table('knowledge_documents')
    with op.batch_alter_table('agents') as batch:batch.drop_column('document_ids')
