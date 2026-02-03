"""
Pytest 配置和共享 fixtures
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ontology, snapshots


@pytest.fixture(scope="function")
def db_engine():
    """创建内存数据库引擎"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """创建数据库会话"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_employee(db_session):
    """创建测试员工"""
    from app.models.ontology import Employee, EmployeeRole

    employee = Employee(
        username="testuser",
        password_hash="hashed",
        name="Test User",
        role=EmployeeRole.MANAGER
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    return employee


@pytest.fixture
def sample_room_type(db_session):
    """创建测试房型"""
    from app.models.ontology import RoomType
    from decimal import Decimal

    room_type = RoomType(
        name="标准间",
        description="Standard Room",
        base_price=Decimal("288.00"),
        max_occupancy=2
    )
    db_session.add(room_type)
    db_session.commit()
    db_session.refresh(room_type)
    return room_type


@pytest.fixture
def sample_room(db_session, sample_room_type):
    """创建测试房间"""
    from app.models.ontology import Room, RoomStatus

    room = Room(
        room_number="101",
        floor=1,
        room_type_id=sample_room_type.id,
        status=RoomStatus.VACANT_CLEAN
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


@pytest.fixture
def sample_guest(db_session):
    """创建测试客人"""
    from app.models.ontology import Guest

    guest = Guest(
        name="张三",
        phone="13800138000",
        id_type="身份证",
        id_number="110101199001011234"
    )
    db_session.add(guest)
    db_session.commit()
    db_session.refresh(guest)
    return guest


@pytest.fixture
def sample_cleaner(db_session):
    """创建测试清洁员"""
    from app.models.ontology import Employee, EmployeeRole

    cleaner = Employee(
        username="cleaner1",
        password_hash="hashed",
        name="清洁员小李",
        role=EmployeeRole.CLEANER
    )
    db_session.add(cleaner)
    db_session.commit()
    db_session.refresh(cleaner)
    return cleaner
