from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

@lru_cache
def get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)

def get_session():
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as session:
        yield session


def get_analysis_session():
    # 一次任务的测量、规则和事件共享同一MVCC快照，输入不会在计算中途变化。
    with sessionmaker(bind=get_engine().execution_options(isolation_level='REPEATABLE READ'), expire_on_commit=False)() as session:
        yield session
