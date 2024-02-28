"""Removed EpicApp=PalServer Added query_port

Revision ID: 170971d44a48
Revises: 3103e5ae5314
Create Date: 2024-02-28 06:35:48.288870

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '170971d44a48'
down_revision = '3103e5ae5314'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('launcher_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('query_port', sa.Integer(), nullable=True))
        batch_op.drop_column('epicApp')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('launcher_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('epicApp', sa.BOOLEAN(), nullable=True))
        batch_op.drop_column('query_port')

    # ### end Alembic commands ###
