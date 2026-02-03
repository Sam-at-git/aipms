"""
Tests for ontology API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_db, SessionLocal, engine, Base
from app.models.ontology import Employee, EmployeeRole, Room, RoomType, Guest, RoomStatus
from app.security.auth import get_password_hash, create_access_token


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Test client with database dependency override"""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def manager_user(db):
    """Create a manager user for testing"""
    user = Employee(
        username="test_manager",
        password_hash=get_password_hash("password123"),
        name="Test Manager",
        role=EmployeeRole.MANAGER,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def receptionist_user(db):
    """Create a receptionist user for testing"""
    user = Employee(
        username="test_receptionist",
        password_hash=get_password_hash("password123"),
        name="Test Receptionist",
        role=EmployeeRole.RECEPTIONIST,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(manager_user):
    """Get authorization headers for manager"""
    token = create_access_token(manager_user.id, manager_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def receptionist_headers(receptionist_user):
    """Get authorization headers for receptionist"""
    token = create_access_token(receptionist_user.id, receptionist_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_data(db):
    """Create sample data for statistics testing"""
    # Create room type
    room_type = RoomType(
        name="Standard",
        description="Standard room",
        base_price=100.00,
        max_occupancy=2
    )
    db.add(room_type)
    db.flush()

    # Create rooms
    for i in range(5):
        room = Room(
            room_number=f"10{i}",
            floor=1,
            room_type_id=room_type.id,
            status=RoomStatus.VACANT_CLEAN if i < 3 else RoomStatus.OCCUPIED
        )
        db.add(room)

    # Create guests
    for i in range(3):
        guest = Guest(
            name=f"Guest {i}",
            phone=f"1380000000{i}",
            tier="normal" if i < 2 else "gold"
        )
        db.add(guest)

    db.commit()
    return {"room_type": room_type}


class TestOntologySchema:
    """Tests for ontology schema endpoint"""

    def test_get_ontology_schema(self, client, auth_headers):
        """Test getting ontology schema"""
        response = client.get("/ontology/schema", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "entities" in data
        assert "relationships" in data

        # Verify entities
        entity_names = [e["name"] for e in data["entities"]]
        assert "RoomType" in entity_names
        assert "Room" in entity_names
        assert "Guest" in entity_names
        assert "Reservation" in entity_names
        assert "StayRecord" in entity_names
        assert "Bill" in entity_names
        assert "Task" in entity_names
        assert "Employee" in entity_names

    def test_get_ontology_schema_unauthorized(self, client, receptionist_headers):
        """Test that non-managers cannot access ontology schema"""
        response = client.get("/ontology/schema", headers=receptionist_headers)
        assert response.status_code == 403

    def test_get_ontology_schema_no_auth(self, client):
        """Test that unauthenticated users cannot access ontology schema"""
        response = client.get("/ontology/schema")
        # Returns 401 for unauthenticated, 403 for unauthorized
        assert response.status_code == 401

    def test_schema_entity_attributes(self, client, auth_headers):
        """Test that entity attributes are correctly defined"""
        response = client.get("/ontology/schema", headers=auth_headers)
        data = response.json()

        # Find Room entity
        room_entity = next(e for e in data["entities"] if e["name"] == "Room")

        # Verify attributes
        attr_names = [a["name"] for a in room_entity["attributes"]]
        assert "id" in attr_names
        assert "room_number" in attr_names
        assert "floor" in attr_names
        assert "status" in attr_names

        # Verify primary key
        id_attr = next(a for a in room_entity["attributes"] if a["name"] == "id")
        assert id_attr.get("primary") is True

    def test_schema_relationships(self, client, auth_headers):
        """Test that relationships are correctly defined"""
        response = client.get("/ontology/schema", headers=auth_headers)
        data = response.json()

        # Verify some key relationships
        rel_pairs = [(r["from"], r["to"]) for r in data["relationships"]]
        assert ("Room", "RoomType") in rel_pairs
        assert ("Reservation", "Guest") in rel_pairs
        assert ("StayRecord", "Room") in rel_pairs
        assert ("Bill", "StayRecord") in rel_pairs


class TestOntologyStatistics:
    """Tests for ontology statistics endpoint"""

    def test_get_ontology_statistics(self, client, auth_headers, sample_data):
        """Test getting ontology statistics"""
        response = client.get("/ontology/statistics", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "entities" in data

        # Verify room statistics
        room_stats = data["entities"]["Room"]
        assert room_stats["total"] == 5
        assert room_stats["by_status"]["vacant_clean"] == 3
        assert room_stats["by_status"]["occupied"] == 2

    def test_get_ontology_statistics_guest_tiers(self, client, auth_headers, sample_data):
        """Test guest tier statistics"""
        response = client.get("/ontology/statistics", headers=auth_headers)
        data = response.json()

        guest_stats = data["entities"]["Guest"]
        assert guest_stats["total"] == 3
        assert guest_stats["by_tier"]["normal"] == 2
        assert guest_stats["by_tier"]["gold"] == 1

    def test_get_ontology_statistics_empty_db(self, client, auth_headers):
        """Test statistics with empty database"""
        response = client.get("/ontology/statistics", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["entities"]["Room"]["total"] == 0
        assert data["entities"]["Guest"]["total"] == 0


class TestOntologyInstanceGraph:
    """Tests for ontology instance graph endpoint"""

    def test_get_overview_graph(self, client, auth_headers, sample_data):
        """Test getting overview graph without center entity"""
        response = client.get("/ontology/instance-graph", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "nodes" in data
        assert "edges" in data

        # Should have entity type nodes
        node_ids = [n["id"] for n in data["nodes"]]
        assert "RoomType" in node_ids
        assert "Room" in node_ids
        assert "Guest" in node_ids

    def test_get_overview_graph_has_statistics(self, client, auth_headers, sample_data):
        """Test that overview graph includes statistics"""
        response = client.get("/ontology/instance-graph", headers=auth_headers)
        data = response.json()

        room_node = next(n for n in data["nodes"] if n["id"] == "Room")
        assert room_node["data"]["total"] == 5

    def test_get_instance_graph_invalid_depth(self, client, auth_headers):
        """Test instance graph with invalid depth"""
        response = client.get(
            "/ontology/instance-graph",
            params={"depth": 10},
            headers=auth_headers
        )
        # Should be clamped or return error
        assert response.status_code in [200, 422]
