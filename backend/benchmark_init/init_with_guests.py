"""
Example benchmark init script: seed data with pre-existing guests.

All init scripts must define:
    def run(db: Session) -> None

The runner will:
1. Clear business tables (rooms, guests, reservations, etc.)
2. Re-seed room types, rooms, employees, rate plans (via reset_business_data)
3. Call this script's run(db) to add extra seed data
"""
from sqlalchemy.orm import Session
from app.hotel.models.ontology import Guest


def run(db: Session) -> None:
    """Add sample guests for benchmark testing."""
    guests = [
        Guest(name="张三", phone="13800138000", id_type="身份证", id_number="110101199001011234"),
        Guest(name="李四", phone="13900139000", id_type="身份证", id_number="110101199002022345"),
        Guest(name="王五", phone="13500135000", id_type="身份证", id_number="110101199003033456"),
    ]
    for g in guests:
        db.add(g)
    db.commit()
