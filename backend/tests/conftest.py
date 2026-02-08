"""
Pytest 配置和共享 fixtures
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from typing import Generator
from fastapi.testclient import TestClient
from decimal import Decimal

from app.database import Base, get_db
from app.models import ontology, snapshots
from app.models.ontology import Employee, EmployeeRole, RoomType, Room, RoomStatus, Guest
from app.security.auth import get_password_hash, create_access_token
from app.main import app


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


@pytest.fixture(scope="function")
def client(db_session):
    """创建测试客户端"""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============== 认证相关 Fixtures ==============

@pytest.fixture
def manager_token(db_session):
    """创建经理用户并返回token"""
    manager = Employee(
        username="manager",
        password_hash=get_password_hash("123456"),
        name="经理",
        role=EmployeeRole.MANAGER,
        is_active=True
    )
    db_session.add(manager)
    db_session.commit()
    db_session.refresh(manager)
    return create_access_token(manager.id, manager.role)


@pytest.fixture
def receptionist_token(db_session):
    """创建前台用户并返回token"""
    receptionist = Employee(
        username="front1",
        password_hash=get_password_hash("123456"),
        name="前台小王",
        role=EmployeeRole.RECEPTIONIST,
        is_active=True
    )
    db_session.add(receptionist)
    db_session.commit()
    db_session.refresh(receptionist)
    return create_access_token(receptionist.id, receptionist.role)


@pytest.fixture
def cleaner_token(db_session):
    """创建清洁员用户并返回token"""
    cleaner = Employee(
        username="cleaner1",
        password_hash=get_password_hash("123456"),
        name="清洁员小李",
        role=EmployeeRole.CLEANER,
        is_active=True
    )
    db_session.add(cleaner)
    db_session.commit()
    db_session.refresh(cleaner)
    return create_access_token(cleaner.id, cleaner.role)


@pytest.fixture
def auth_headers(manager_token):
    """返回带认证的请求头"""
    return {"Authorization": f"Bearer {manager_token}"}


@pytest.fixture
def manager_auth_headers(manager_token):
    """返回经理认证的请求头"""
    return {"Authorization": f"Bearer {manager_token}"}


@pytest.fixture
def receptionist_auth_headers(receptionist_token):
    """返回前台认证的请求头"""
    return {"Authorization": f"Bearer {receptionist_token}"}


@pytest.fixture
def cleaner_auth_headers(cleaner_token):
    """返回清洁员认证的请求头"""
    return {"Authorization": f"Bearer {cleaner_token}"}


# ============== 实体相关 Fixtures ==============

@pytest.fixture
def sample_room_type(db_session):
    """创建测试房型"""
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
def sample_room_type_luxury(db_session):
    """创建豪华房型"""
    room_type = RoomType(
        name="豪华间",
        description="Luxury Room",
        base_price=Decimal("588.00"),
        max_occupancy=2
    )
    db_session.add(room_type)
    db_session.commit()
    db_session.refresh(room_type)
    return room_type


@pytest.fixture
def sample_room(db_session, sample_room_type):
    """创建测试房间"""
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
def sample_room_102(db_session, sample_room_type):
    """创建102房间"""
    room = Room(
        room_number="102",
        floor=1,
        room_type_id=sample_room_type.id,
        status=RoomStatus.VACANT_CLEAN
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


@pytest.fixture
def sample_room_201(db_session, sample_room_type):
    """创建201房间"""
    room = Room(
        room_number="201",
        floor=2,
        room_type_id=sample_room_type.id,
        status=RoomStatus.VACANT_CLEAN
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


@pytest.fixture
def multiple_rooms(db_session, sample_room_type):
    """创建多个房间"""
    rooms = []
    for i in range(101, 106):
        room = Room(
            room_number=str(i),
            floor=1 if i < 200 else 2,
            room_type_id=sample_room_type.id,
            status=RoomStatus.VACANT_CLEAN
        )
        db_session.add(room)
        rooms.append(room)
    db_session.commit()
    for room in rooms:
        db_session.refresh(room)
    return rooms


@pytest.fixture
def sample_cleaner(db_session):
    """创建测试清洁员（使用不同用户名避免与cleaner_token冲突）"""
    cleaner = Employee(
        username="cleaner_test",
        password_hash=get_password_hash("123456"),
        name="测试清洁员",
        role=EmployeeRole.CLEANER,
        is_active=True
    )
    db_session.add(cleaner)
    db_session.commit()
    db_session.refresh(cleaner)
    return cleaner


@pytest.fixture
def sample_guest(db_session):
    """创建测试客人"""
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
def sample_guest_2(db_session):
    """创建第二个测试客人"""
    guest = Guest(
        name="李四",
        phone="13900139000",
        id_type="身份证",
        id_number="110101199002021234"
    )
    db_session.add(guest)
    db_session.commit()
    db_session.refresh(guest)
    return guest


@pytest.fixture
def sample_employee(db_session):
    """创建测试员工"""
    employee = Employee(
        username="test_employee",
        password_hash=get_password_hash("password123"),
        name="测试员工",
        role=EmployeeRole.RECEPTIONIST,
        is_active=True
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    return employee
