"""
数据库配置 - SQLite 持久化层
遵循 Palantir 原则：数据库仅作为持久化层，所有业务操作通过本体对象进行
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = "sqlite:///./pms.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库表"""
    from app.models import ontology  # noqa
    from app.models import snapshots  # noqa - 操作快照和配置历史表
    from app.models import security_events  # noqa - 安全事件表
    Base.metadata.create_all(bind=engine)

    # 启用 WAL 模式以提高并发性能
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))
        conn.commit()
