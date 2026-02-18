"""Input validation for CLI arguments."""
import re
from pathlib import Path


PROJECT_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_-]+$')
DOMAIN_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')


def validate_project_name(name: str) -> str:
    """Validate project name: lowercase, starts with letter, alphanumeric + hyphens/underscores."""
    if not PROJECT_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid project name '{name}'. "
            "Must start with a lowercase letter and contain only lowercase letters, digits, hyphens, underscores."
        )
    return name


def validate_domain_name(name: str) -> str:
    """Validate domain name: snake_case identifier."""
    if not DOMAIN_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid domain name '{name}'. "
            "Must be a valid Python identifier in snake_case (lowercase letters, digits, underscores)."
        )
    return name


def validate_port(port: int) -> int:
    """Validate port number."""
    if not (1024 <= port <= 65535):
        raise ValueError(f"Port {port} out of range. Must be between 1024 and 65535.")
    return port


def validate_output_dir(path: Path) -> Path:
    """Validate that output directory is writable and target doesn't already exist."""
    if not path.parent.exists():
        raise ValueError(f"Parent directory '{path.parent}' does not exist.")
    return path


def to_pascal_case(snake_str: str) -> str:
    """Convert snake_case to PascalCase. e.g. 'my_clinic' -> 'MyClinic'."""
    return ''.join(word.capitalize() for word in snake_str.split('_'))


def to_slug(name: str) -> str:
    """Convert project name (may contain hyphens) to Python-safe slug with underscores."""
    return name.replace('-', '_')
