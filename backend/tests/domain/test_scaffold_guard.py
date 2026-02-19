"""
Scaffold Architecture Guard Tests

Ensure the app/ root is domain-agnostic (scaffold-ready), with all hotel-specific
code isolated in app/hotel/. These tests guarantee that "delete app/hotel/ +
add empty domain template" produces a clean scaffold.
"""
import os
import re

# Project root directories
BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
APP_DIR = os.path.join(BACKEND_DIR, 'app')
HOTEL_DIR = os.path.join(APP_DIR, 'hotel')
FRONTEND_DIR = os.path.normpath(os.path.join(BACKEND_DIR, '..', 'frontend', 'src'))


def _scan_py_files(directory, exclude_dirs=None):
    """Yield (filepath, line_number, line_text) for all .py files."""
    exclude_dirs = exclude_dirs or []
    for root, dirs, files in os.walk(directory):
        if '__pycache__' in root:
            continue
        skip = False
        for exc in exclude_dirs:
            if os.path.normpath(root).startswith(os.path.normpath(exc)):
                skip = True
                break
        if skip:
            continue
        for f in files:
            if not f.endswith('.py'):
                continue
            filepath = os.path.join(root, f)
            with open(filepath) as fh:
                for i, line in enumerate(fh, 1):
                    yield filepath, i, line


class TestScaffoldGuard:
    """Scaffold architecture guard — enforces domain isolation."""

    def test_app_root_no_hotel_imports(self):
        """
        app/ (excluding app/hotel/) must not import from app.hotel
        unless the file is in an explicitly allowed list.

        This documents every coupling point between the generic scaffold
        and the hotel domain. When switching to a new domain, these are
        the files that need updating.

        Allowed directories (all files within may reference app.hotel):
        - app/routers/        — all routers need Employee for JWT auth
        - app/system/         — system modules need Employee for auth
        - app/services/actions/ — action handlers reference hotel types

        Allowed individual files:
        - app/main.py              (plugin loading)
        - app/database.py          (ORM table registration)
        - app/security/auth.py     (user model)
        - app/models/__init__.py   (re-export compatibility)
        - app/models/schemas.py    (cross-cutting schema imports)
        - app/services/undo_service.py            (hotel ORM for undo)
        - app/services/audit_service.py           (SystemLog)
        - app/services/benchmark_runner.py        (AIService + Employee)
        - app/services/ontology_metadata_service.py (entity metadata)
        """
        # Directories where all .py files are allowed to import from app.hotel
        allowed_dirs = [
            os.path.normpath(os.path.join(APP_DIR, 'routers')),
            os.path.normpath(os.path.join(APP_DIR, 'system')),
            os.path.normpath(os.path.join(APP_DIR, 'services', 'actions')),
        ]

        # Specific files allowed to import from app.hotel
        allowed_files = {
            os.path.join(APP_DIR, 'main.py'),
            os.path.join(APP_DIR, 'database.py'),
            os.path.join(APP_DIR, 'security', 'auth.py'),
            os.path.join(APP_DIR, 'models', '__init__.py'),
            os.path.join(APP_DIR, 'models', 'schemas.py'),
            os.path.join(APP_DIR, 'services', 'undo_service.py'),
            os.path.join(APP_DIR, 'services', 'audit_service.py'),
            os.path.join(APP_DIR, 'services', 'benchmark_runner.py'),
            os.path.join(APP_DIR, 'services', 'ontology_metadata_service.py'),
        }
        allowed_files = {os.path.normpath(f) for f in allowed_files}

        violations = []
        for filepath, lineno, line in _scan_py_files(APP_DIR, exclude_dirs=[HOTEL_DIR]):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if 'app.hotel' in stripped and ('import' in stripped or 'from' in stripped):
                norm_path = os.path.normpath(filepath)
                # Check allowed dirs
                in_allowed_dir = any(
                    norm_path.startswith(d + os.sep) or os.path.dirname(norm_path) == d
                    for d in allowed_dirs
                )
                if not in_allowed_dir and norm_path not in allowed_files:
                    rel = os.path.relpath(filepath, BACKEND_DIR)
                    violations.append(f"{rel}:{lineno}: {stripped}")

        assert violations == [], (
            f"app/ (non-hotel) has {len(violations)} unexpected import(s) from app.hotel.\n"
            f"If legitimate, add the file to the allowed list in this test.\n"
            + "\n".join(violations)
        )

    def test_generic_models_no_hotel_orm(self):
        """
        app/models/ontology.py must not define hotel ORM classes.
        It should only contain SecurityLevel (generic framework type).
        """
        ontology_path = os.path.join(APP_DIR, 'models', 'ontology.py')
        with open(ontology_path) as f:
            content = f.read()

        # Should contain SecurityLevel
        assert 'SecurityLevel' in content, "app/models/ontology.py should contain SecurityLevel"

        # Should NOT contain hotel ORM models
        hotel_models = ['class Room(', 'class Guest(', 'class Reservation(', 'class StayRecord(',
                        'class Bill(', 'class Task(', 'class Employee(', 'class RoomType(',
                        'class RatePlan(', 'class Payment(']
        found = [m for m in hotel_models if m in content]
        assert found == [], (
            f"app/models/ontology.py still contains hotel ORM models: {found}"
        )

    def test_generic_routers_no_hotel_models(self):
        """Generic routers in app/routers/ must not directly import hotel ORM models."""
        routers_dir = os.path.join(APP_DIR, 'routers')
        if not os.path.isdir(routers_dir):
            return

        hotel_orm_pattern = re.compile(
            r'from\s+app\.hotel\.models\.ontology\s+import\s+'
            r'(Room|Guest|Reservation|StayRecord|Bill|Task|RoomType|RatePlan|Payment)\b'
        )

        violations = []
        for filepath, lineno, line in _scan_py_files(routers_dir):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if hotel_orm_pattern.search(stripped):
                rel = os.path.relpath(filepath, BACKEND_DIR)
                violations.append(f"{rel}:{lineno}: {stripped}")

        assert violations == [], (
            f"Generic routers import hotel ORM models:\n" + "\n".join(violations)
        )

    def test_hotel_domain_self_contained(self):
        """
        app/hotel/ should only import from:
        - core/ (framework)
        - app.database (DB session)
        - app.config (settings)
        - app.models (generic models: schemas for MissingField, etc.)
        - app.services (generic services: llm_service, event_bus, audit, undo, etc.)
        - app.security (generic auth framework: JWT decorators, password utils)
        - app.hotel (itself)
        - stdlib / third-party

        It must NOT import from app.routers or app.system.
        (app.security is allowed — it's a generic auth framework, not a domain module.)
        """
        forbidden_patterns = [
            'from app.routers',
            'from app.system',
            'import app.routers',
            'import app.system',
        ]

        violations = []
        for filepath, lineno, line in _scan_py_files(HOTEL_DIR):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            for pattern in forbidden_patterns:
                if pattern in stripped:
                    rel = os.path.relpath(filepath, BACKEND_DIR)
                    violations.append(f"{rel}:{lineno}: {stripped}")

        assert violations == [], (
            f"app/hotel/ has {len(violations)} forbidden import(s):\n"
            + "\n".join(violations)
        )

    def test_frontend_api_split(self):
        """
        services/api.ts should not contain hotel API definitions
        (roomApi, reservationApi, etc. should be in hotelApi.ts).
        """
        api_path = os.path.join(FRONTEND_DIR, 'services', 'api.ts')
        if not os.path.isfile(api_path):
            return

        with open(api_path) as f:
            content = f.read()

        hotel_apis = ['const roomApi', 'const reservationApi', 'const checkinApi',
                      'const checkoutApi', 'const taskApi', 'const billingApi',
                      'const employeeApi', 'const reportApi', 'const priceApi',
                      'const guestApi']
        found = [api for api in hotel_apis if api in content]
        assert found == [], (
            f"services/api.ts still contains hotel API definitions: {found}\n"
            f"These should be in services/hotelApi.ts"
        )

    def test_frontend_hotel_pages_in_hotel_dir(self):
        """
        Hotel pages should be in pages/hotel/, not pages/ root.
        """
        pages_dir = os.path.join(FRONTEND_DIR, 'pages')
        if not os.path.isdir(pages_dir):
            return

        hotel_pages = ['Dashboard.tsx', 'Rooms.tsx', 'Reservations.tsx', 'Guests.tsx',
                       'Customers.tsx', 'Tasks.tsx', 'Billing.tsx', 'Employees.tsx',
                       'Prices.tsx', 'Reports.tsx']
        found_in_root = [p for p in hotel_pages if os.path.isfile(os.path.join(pages_dir, p))]
        assert found_in_root == [], (
            f"Hotel pages found in pages/ root (should be in pages/hotel/): {found_in_root}"
        )
