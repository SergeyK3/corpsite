"""Proposed adoption of an observed legacy marker, NOT the lost original migration.

Only for the separately reviewed local recovery graph. Existing databases must
pass the next revision's snapshot checks. Never install in the canonical graph.
"""
revision = 'za0b1c2d3e4f'
down_revision = None
branch_labels = ('local_personnel_recovery',)
depends_on = None


def upgrade():
    raise RuntimeError('This is an observed existing baseline, not a database creation migration')


def downgrade():
    raise RuntimeError('The original migration history is unknown; restore the reviewed backup')
