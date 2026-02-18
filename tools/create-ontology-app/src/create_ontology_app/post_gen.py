"""Post-generation steps: git init, dependency installation."""
import subprocess
from pathlib import Path

from rich.console import Console

from create_ontology_app.generator import ProjectConfig

console = Console()


def _run(cmd: list[str], cwd: Path, label: str) -> bool:
    """Run a subprocess command, return True on success."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            console.print(f"  [yellow]Warning:[/yellow] {label} failed: {result.stderr[:200]}")
            return False
        return True
    except FileNotFoundError:
        console.print(f"  [yellow]Warning:[/yellow] {cmd[0]} not found, skipping {label}")
        return False
    except subprocess.TimeoutExpired:
        console.print(f"  [yellow]Warning:[/yellow] {label} timed out")
        return False


def post_generate(
    project_dir: Path,
    config: ProjectConfig,
    skip_git: bool = False,
    skip_install: bool = False,
):
    """Run post-generation steps."""
    backend_dir = project_dir / "backend"
    frontend_dir = project_dir / "frontend"

    # Git init
    if not skip_git:
        console.print("  Initializing git repository...")
        if _run(["git", "init"], project_dir, "git init"):
            _run(["git", "add", "."], project_dir, "git add")
            _run(
                ["git", "commit", "-m", "Initial scaffold from create-ontology-app"],
                project_dir,
                "git commit",
            )

    # Backend dependencies
    if not skip_install:
        console.print("  Installing backend dependencies (uv sync)...")
        _run(["uv", "sync"], backend_dir, "uv sync")

        console.print("  Installing frontend dependencies (npm install)...")
        _run(["npm", "install"], frontend_dir, "npm install")

        console.print("  Initializing database...")
        _run(["uv", "run", "python", "init_data.py"], backend_dir, "init_data.py")
