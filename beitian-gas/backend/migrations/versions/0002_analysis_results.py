"""新增不可变的逐任务单井结果，保留最新快照更新前的历史判断。"""
from alembic import op
import sqlalchemy as sa
revision='0002_analysis_results'
down_revision='0001_initial'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('well_analysis_results',
        sa.Column('analysis_run_id',sa.Uuid(),nullable=False),
        sa.Column('as_of',sa.DateTime(timezone=True),nullable=False),
        sa.Column('screening_status',sa.String(40),nullable=False),
        sa.Column('production_state',sa.String(40),nullable=False),
        sa.Column('evidence',sa.JSON(),nullable=False),
        sa.Column('id',sa.Uuid(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('well_id',sa.Uuid(),nullable=False),
        sa.CheckConstraint("screening_status IN ('可信正常', '疑似异常', '措施影响', '数据待核实', '工况待核实')",name=op.f('ck_well_analysis_results_screening_status')),
        sa.ForeignKeyConstraint(['analysis_run_id'],['analysis_runs.id'],ondelete='RESTRICT',name=op.f('fk_well_analysis_results_analysis_run_id_analysis_runs')),
        sa.ForeignKeyConstraint(['well_id'],['wells.id'],ondelete='RESTRICT',name=op.f('fk_well_analysis_results_well_id_wells')),
        sa.PrimaryKeyConstraint('id',name=op.f('pk_well_analysis_results')),
        sa.UniqueConstraint('analysis_run_id','well_id',name='uq_analysis_result_run_well'))
    op.create_index('ix_well_analysis_results_analysis_run_id','well_analysis_results',['analysis_run_id'])
    op.create_index('ix_well_analysis_results_well_id','well_analysis_results',['well_id'])
    op.create_index('ix_well_analysis_results_screening_status','well_analysis_results',['screening_status'])

def downgrade():
    op.drop_table('well_analysis_results')
