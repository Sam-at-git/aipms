"""CLI entry point using Typer."""
import typer
from pathlib import Path
from typing import Optional

from create_ontology_app.validators import (
    validate_project_name,
    validate_domain_name,
    validate_port,
    to_pascal_case,
    to_slug,
)
from create_ontology_app.generator import ProjectConfig, generate
from create_ontology_app.post_gen import post_generate

app = typer.Typer(
    name="create-ontology-app",
    help="Scaffold generator for Ontology Runtime applications.",
    add_completion=False,
)


@app.command()
def main(
    project_path: str = typer.Argument(
        ...,
        help="Project directory path (will be created). e.g. /tmp/my-clinic or just my-clinic",
    ),
    domain: str = typer.Option(
        "my_domain",
        "--domain",
        help="Domain name in snake_case (e.g. clinic, warehouse)",
    ),
    display_name: Optional[str] = typer.Option(
        None,
        "--display-name",
        help="Human-readable domain name (defaults to title-cased domain name)",
    ),
    backend_port: int = typer.Option(
        8020,
        "--backend-port",
        help="Backend server port",
    ),
    frontend_port: int = typer.Option(
        3020,
        "--frontend-port",
        help="Frontend dev server port",
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        help="Project description",
    ),
    no_git: bool = typer.Option(
        False,
        "--no-git",
        help="Skip git init",
    ),
    no_install: bool = typer.Option(
        False,
        "--no-install",
        help="Skip dependency installation (uv sync, npm install)",
    ),
):
    """Generate a new Ontology Runtime project scaffold."""
    from rich.console import Console
    console = Console()

    # Resolve path
    path = Path(project_path).resolve()
    project_name = path.name

    # Validate inputs
    try:
        validate_project_name(project_name)
        validate_domain_name(domain)
        validate_port(backend_port)
        validate_port(frontend_port)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    if path.exists():
        console.print(f"[red]Error:[/red] Directory '{path}' already exists.")
        raise typer.Exit(code=1)

    # Build config
    domain_class = to_pascal_case(domain)
    project_slug = to_slug(project_name)
    resolved_display_name = display_name or domain_class
    resolved_description = description or f"{resolved_display_name} — powered by Ontology Runtime"

    config = ProjectConfig(
        project_name=project_name,
        project_slug=project_slug,
        domain_name=domain,
        domain_class_name=domain_class,
        domain_display_name=resolved_display_name,
        backend_port=backend_port,
        frontend_port=frontend_port,
        description=resolved_description,
        db_name=f"{project_slug}.db",
    )

    console.print(f"\n[bold]Creating project:[/bold] {path}")
    console.print(f"  Domain: {domain} ({domain_class})")
    console.print(f"  Ports:  backend={backend_port}, frontend={frontend_port}\n")

    # Generate project
    generate(config, path)

    console.print("[green]Project generated successfully![/green]\n")

    # Post-generation steps
    post_generate(path, config, skip_git=no_git, skip_install=no_install)

    # Print next steps
    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  cd {path}")
    if no_install:
        console.print("  cd backend && uv sync")
        console.print("  cd frontend && npm install")
    console.print(f"  cd backend && uv run python init_data.py")
    console.print(f"  cd backend && uv run uvicorn app.main:app --reload --port {backend_port}")
    console.print(f"  cd frontend && npm run dev")
    console.print(f"\n  Login: sysadmin / 123456")
    console.print()


if __name__ == "__main__":
    app()
