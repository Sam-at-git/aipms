"""Smoke tests: generate a project and verify structure + no hotel references."""
import os
import re
import tempfile
import shutil
import pytest
from pathlib import Path

from create_ontology_app.generator import ProjectConfig, generate


@pytest.fixture
def config():
    return ProjectConfig(
        project_name="test-clinic",
        project_slug="test_clinic",
        domain_name="clinic",
        domain_class_name="Clinic",
        domain_display_name="Clinic Management",
        backend_port=8030,
        frontend_port=3030,
        description="A test clinic project",
        db_name="test_clinic.db",
    )


@pytest.fixture
def generated_project(config):
    """Generate a project into a temp directory and return the path."""
    tmpdir = tempfile.mkdtemp(prefix="ontology_smoke_")
    project_dir = Path(tmpdir) / config.project_name
    generate(config, project_dir)
    yield project_dir
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestProjectStructure:
    """Verify generated project has correct directory structure."""

    def test_backend_dirs_exist(self, generated_project):
        backend = generated_project / "backend"
        assert (backend / "core").is_dir()
        assert (backend / "app").is_dir()
        assert (backend / "app" / "clinic").is_dir()
        assert (backend / "app" / "system").is_dir()
        assert (backend / "tests").is_dir()

    def test_domain_plugin_files(self, generated_project):
        domain_dir = generated_project / "backend" / "app" / "clinic"
        assert (domain_dir / "plugin.py").is_file()
        assert (domain_dir / "clinic_domain_adapter.py").is_file()
        assert (domain_dir / "models" / "ontology.py").is_file()
        assert (domain_dir / "models" / "schemas.py").is_file()
        assert (domain_dir / "actions" / "__init__.py").is_file()
        assert (domain_dir / "routers" / "__init__.py").is_file()
        assert (domain_dir / "security" / "__init__.py").is_file()
        assert (domain_dir / "domain" / "relationships.py").is_file()

    def test_frontend_dirs_exist(self, generated_project):
        frontend = generated_project / "frontend"
        assert (frontend / "src").is_dir()
        assert (frontend / "package.json").is_file()
        assert (frontend / "vite.config.ts").is_file()

    def test_frontend_domain_files(self, generated_project):
        src = generated_project / "frontend" / "src"
        assert (src / "pages" / "clinic" / "routes.tsx").is_file()
        assert (src / "services" / "clinicApi.ts").is_file()
        assert (src / "store" / "clinicStore.ts").is_file()
        assert (src / "types" / "clinic.ts").is_file()

    def test_root_files(self, generated_project):
        assert (generated_project / "start.sh").is_file()
        assert (generated_project / ".gitignore").is_file()
        assert (generated_project / "README.md").is_file()
        assert (generated_project / "backend" / "pyproject.toml").is_file()
        assert (generated_project / "backend" / "init_data.py").is_file()

    def test_main_py_exists(self, generated_project):
        assert (generated_project / "backend" / "app" / "main.py").is_file()

    def test_database_py_exists(self, generated_project):
        assert (generated_project / "backend" / "app" / "database.py").is_file()

    def test_no_j2_files_remain(self, generated_project):
        """No .j2 template files should remain in the generated project."""
        j2_files = list(generated_project.rglob("*.j2"))
        assert not j2_files, f"Found leftover .j2 files: {j2_files}"


class TestNoHotelReferences:
    """Verify generated project has no hotel import references in domain-sensitive areas."""

    def _get_files(self, directory: Path, extensions: list[str], exclude_dirs: list[str] = None):
        exclude_dirs = exclude_dirs or []
        for f in directory.rglob("*"):
            if f.is_file() and f.suffix in extensions and "__pycache__" not in str(f):
                if not any(excl in f.parts for excl in exclude_dirs):
                    yield f

    def test_no_hotel_imports_in_app(self, generated_project):
        """No Python file in app/ should have 'app.hotel' import paths."""
        # Check for actual import references like "from app.hotel" or "import app.hotel"
        hotel_import_pattern = re.compile(r'(from|import)\s+app\.hotel')
        violations = []

        app_dir = generated_project / "backend" / "app"
        for f in self._get_files(app_dir, [".py"]):
            content = f.read_text(encoding="utf-8")
            if hotel_import_pattern.search(content):
                violations.append(str(f.relative_to(generated_project)))

        assert not violations, f"Hotel import references found in:\n" + "\n".join(f"  - {v}" for v in violations)

    def test_no_hotel_imports_in_frontend(self, generated_project):
        """No TypeScript file should reference hotelApi, hotelStore, or hotel/ paths."""
        hotel_import_pattern = re.compile(r"(hotelApi|hotelStore|/hotel/|'\.\/hotel')")
        violations = []

        for f in self._get_files(generated_project / "frontend" / "src", [".ts", ".tsx"]):
            content = f.read_text(encoding="utf-8")
            if hotel_import_pattern.search(content):
                violations.append(str(f.relative_to(generated_project)))

        assert not violations, f"Hotel references found in:\n" + "\n".join(f"  - {v}" for v in violations)


class TestTemplateRendering:
    """Verify Jinja2 variables were correctly rendered."""

    def test_main_py_imports_clinic(self, generated_project):
        main_py = (generated_project / "backend" / "app" / "main.py").read_text()
        assert "from app.clinic.plugin import ClinicPlugin" in main_py
        assert "Clinic Management" in main_py

    def test_database_py_imports_clinic(self, generated_project):
        db_py = (generated_project / "backend" / "app" / "database.py").read_text()
        assert "from app.clinic.models import ontology" in db_py
        assert "test_clinic.db" in db_py

    def test_auth_imports_clinic(self, generated_project):
        auth_py = (generated_project / "backend" / "app" / "security" / "auth.py").read_text()
        assert "from app.clinic.models.ontology import Employee" in auth_py

    def test_package_json_name(self, generated_project):
        pkg = (generated_project / "frontend" / "package.json").read_text()
        assert "test_clinic-frontend" in pkg

    def test_vite_config_ports(self, generated_project):
        vite = (generated_project / "frontend" / "vite.config.ts").read_text()
        assert "3030" in vite
        assert "8030" in vite

    def test_init_data_uses_clinic(self, generated_project):
        init = (generated_project / "backend" / "init_data.py").read_text()
        assert "from app.clinic.models.ontology import Employee" in init

    def test_plugin_class_name(self, generated_project):
        plugin = (generated_project / "backend" / "app" / "clinic" / "plugin.py").read_text()
        assert "class ClinicPlugin" in plugin

    def test_domain_adapter_class_name(self, generated_project):
        adapter = (generated_project / "backend" / "app" / "clinic" / "clinic_domain_adapter.py").read_text()
        assert "class ClinicDomainAdapter" in adapter

    def test_gitignore_db_name(self, generated_project):
        gitignore = (generated_project / ".gitignore").read_text()
        assert "test_clinic.db" in gitignore

    def test_readme_content(self, generated_project):
        readme = (generated_project / "README.md").read_text()
        assert "Clinic Management" in readme
        assert "A test clinic project" in readme

    def test_start_sh_executable(self, generated_project):
        start = generated_project / "start.sh"
        assert os.access(start, os.X_OK)

    def test_config_py_db_name(self, generated_project):
        config = (generated_project / "backend" / "app" / "config.py").read_text()
        assert "test_clinic.db" in config

    def test_frontend_app_imports_domain(self, generated_project):
        app_tsx = (generated_project / "frontend" / "src" / "App.tsx").read_text()
        assert "getClinicRoutes" in app_tsx
        assert "clinicNavItems" in app_tsx

    def test_frontend_types_exports_domain(self, generated_project):
        types_index = (generated_project / "frontend" / "src" / "types" / "index.ts").read_text()
        assert "from './clinic'" in types_index

    def test_frontend_store_exports_domain(self, generated_project):
        store_index = (generated_project / "frontend" / "src" / "store" / "index.ts").read_text()
        assert "from './clinicStore'" in store_index
