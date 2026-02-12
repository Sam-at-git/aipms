"""
OAG Benchmark 专用 fixtures

提供独立的内存数据库，seed 完整的 init_data 数据，
以及真实的 AIService 实例（需要 OPENAI_API_KEY 环境变量）。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ontology, snapshots
from app.models.ontology import Employee

# 导入 init_data.py 中的种子函数
import sys
import os

# 确保 backend 目录在 path 中
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from init_data import init_room_types, init_rooms, init_employees, init_rate_plans


def _seed_init_data(session):
    """使用 init_data.py 的函数填充种子数据"""
    room_types = init_room_types(session)
    init_rooms(session, room_types)
    init_employees(session)
    init_rate_plans(session, room_types)


@pytest.fixture(scope="function")
def benchmark_db():
    """创建内存 SQLite，seed init_data 等价数据。每个 test function 重置。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    _seed_init_data(session)

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def ai_service(benchmark_db):
    """创建真实 AIService 实例（需要 OPENAI_API_KEY 环境变量）"""
    from app.services.ai_service import AIService
    from app.services.actions import get_action_registry, reset_action_registry, register_smart_updates

    # Reset to ensure fresh registry each test
    reset_action_registry()

    # Bootstrap OntologyRegistry + smart update actions (mirrors main.py startup)
    try:
        from core.ontology.registry import OntologyRegistry
        from app.hotel.hotel_domain_adapter import HotelDomainAdapter

        ont_registry = OntologyRegistry()
        adapter = HotelDomainAdapter()
        adapter.register_ontology(ont_registry)

        action_registry = get_action_registry()
        action_registry.set_ontology_registry(ont_registry)
        register_smart_updates(ont_registry)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Ontology bootstrap warning: {e}")

    return AIService(benchmark_db)


@pytest.fixture(scope="function")
def receptionist_user(benchmark_db):
    """获取前台用户 front1"""
    user = benchmark_db.query(Employee).filter(Employee.username == "front1").first()
    assert user is not None, "front1 user not found in seed data"
    return user
