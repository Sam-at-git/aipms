"""Add sample data for testing"""
from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Add room types
    conn.execute(text('''
        INSERT INTO room_types (name, base_price, description, max_occupancy)
        VALUES
            ('Standard Room', 288.00, '标准间', 2),
            ('Deluxe Room', 388.00, '豪华间', 3),
            ('Suite', 588.00, '套房', 4)
    '''))

    # Add rooms
    conn.execute(text('''
        INSERT INTO rooms (room_number, room_type_id, status, floor)
        VALUES
            ('101', 1, 'VACANT_CLEAN', 1),
            ('102', 1, 'VACANT_CLEAN', 1),
            ('201', 2, 'VACANT_CLEAN', 2),
            ('202', 2, 'OCCUPIED', 2),
            ('301', 3, 'VACANT_CLEAN', 3)
    '''))

    conn.commit()
    print('Sample data added successfully!')

    # Verify
    result = conn.execute(text('SELECT rt.name, COUNT(*) as count FROM rooms r JOIN room_types rt ON r.room_type_id = rt.id GROUP BY rt.name'))
    print('\nRoom types and counts:')
    for row in result:
        print(f'  {row[0]}: {row[1]}')
