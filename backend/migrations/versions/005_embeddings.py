"""Persistent vector index and content-addressed embedding cache."""
from alembic import op
import sqlalchemy as sa
revision='005'
down_revision='004'
branch_labels=None
depends_on=None
def upgrade():
    for column in [sa.Column('embedding_status',sa.String(30),nullable=False,server_default='not_indexed'),sa.Column('embedding_error',sa.String(80)),sa.Column('embedding_signature',sa.String(64)),sa.Column('embedded_chunks',sa.Integer(),nullable=False,server_default='0')]:op.add_column('knowledge_documents',column)
    op.create_table('embedding_cache',sa.Column('id',sa.String(64),primary_key=True),sa.Column('signature',sa.String(64),nullable=False),sa.Column('dimension',sa.Integer(),nullable=False),sa.Column('vector',sa.LargeBinary(),nullable=False),sa.Column('created_at',sa.String(40),nullable=False))
    op.create_index('ix_embedding_cache_signature','embedding_cache',['signature'])
    op.create_table('knowledge_vectors',sa.Column('chunk_id',sa.String(36),sa.ForeignKey('knowledge_chunks.id'),primary_key=True),sa.Column('cache_id',sa.String(64),sa.ForeignKey('embedding_cache.id'),nullable=False))
    op.create_index('ix_knowledge_vectors_cache_id','knowledge_vectors',['cache_id'])
def downgrade():
    op.drop_table('knowledge_vectors');op.drop_table('embedding_cache')
    with op.batch_alter_table('knowledge_documents') as batch:
        for name in ('embedding_status','embedding_error','embedding_signature','embedded_chunks'):batch.drop_column(name)
