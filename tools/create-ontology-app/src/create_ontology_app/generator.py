"""Core scaffold generation logic."""
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


@dataclass
class ProjectConfig:
    project_name: str
    project_slug: str
    domain_name: str
    domain_class_name: str
    domain_display_name: str
    backend_port: int
    frontend_port: int
    description: str
    db_name: str

    def to_context(self) -> dict:
        return asdict(self)


# Files/directories that should never be copied
EXCLUDE_PATTERNS = {
    "__pycache__",
    ".pyc",
    ".pyo",
    ".db",
    ".db-shm",
    ".db-wal",
    ".coverage",
    "node_modules",
    "dist",
    ".venv",
    ".env",
}


def _should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from copying."""
    for part in path.parts:
        if part in EXCLUDE_PATTERNS:
            return True
        for pattern in EXCLUDE_PATTERNS:
            if part.endswith(pattern):
                return True
    return False


def generate(config: ProjectConfig, project_dir: Path):
    """Generate the complete project scaffold."""
    project_dir.mkdir(parents=True, exist_ok=True)
    context = config.to_context()

    # Set up Jinja2 environment
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        # Use different delimiters for files that may contain {{ in JS/TS
        # We'll handle this by using .j2 extension for templates
    )

    # Walk templates directory and process each file
    for template_file in sorted(TEMPLATES_DIR.rglob("*")):
        if template_file.is_dir():
            continue
        if _should_exclude(template_file):
            continue

        # Compute relative path from templates dir
        rel_path = template_file.relative_to(TEMPLATES_DIR)

        # Replace {{ domain_name }} in directory/file names
        rel_str = str(rel_path)
        rel_str = rel_str.replace("__domain_name__", config.domain_name)
        rel_str = rel_str.replace("__domain_class_name__", config.domain_class_name)
        rel_str = rel_str.replace("__project_slug__", config.project_slug)

        # Handle .j2 templates
        is_template = rel_str.endswith(".j2")
        if is_template:
            rel_str = rel_str[:-3]  # Remove .j2 extension

        dest_path = project_dir / rel_str
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if is_template:
            # Render Jinja2 template
            template_rel = str(rel_path).replace("\\", "/")
            template = env.get_template(template_rel)
            rendered = template.render(**context)
            dest_path.write_text(rendered, encoding="utf-8")
        else:
            # Copy file as-is
            shutil.copy2(template_file, dest_path)

    # Post-copy: replace remaining app.hotel references in static files
    _fixup_hotel_references(project_dir, config)

    # Make start.sh executable
    start_sh = project_dir / "start.sh"
    if start_sh.exists():
        start_sh.chmod(0o755)


# Import patterns to replace: (old_pattern, new_template)
# These are found in static-copied files (routers, system, actions)
_HOTEL_REPLACEMENTS = [
    # More specific patterns first (order matters — longer matches before shorter)
    ("app.hotel.models.schemas as hotel_schemas", "app.{domain_name}.models.schemas as domain_schemas"),
    ("app.hotel.services.employee_service", "app.{domain_name}.services.employee_service"),
    ("app.hotel.services.ai_service", "app.{domain_name}.services.ai_service"),
    ("app.hotel.services.param_parser_service", "app.{domain_name}.services.param_parser_service"),
    # General import replacements (after specific ones)
    ("app.hotel.models.ontology", "app.{domain_name}.models.ontology"),
    ("app.hotel.models.schemas", "app.{domain_name}.models.schemas"),
    # Variable name replacements
    ("hotel_schemas", "domain_schemas"),
    # Comment references
    ("Hotel-specific ORM models are in app.hotel.models.ontology.", "Domain ORM models are in app.{domain_name}.models.ontology."),
]


def _fixup_hotel_references(project_dir: Path, config: ProjectConfig):
    """Replace remaining app.hotel references in static-copied Python files."""
    replacements = [
        (old, new.format(domain_name=config.domain_name))
        for old, new in _HOTEL_REPLACEMENTS
    ]

    backend_dir = project_dir / "backend"
    for py_file in backend_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        content = py_file.read_text(encoding="utf-8")
        original = content
        for old, new in replacements:
            content = content.replace(old, new)
        if content != original:
            py_file.write_text(content, encoding="utf-8")
