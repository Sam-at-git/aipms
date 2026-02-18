"""
Architecture guard: core/ must have zero imports from app/.

This test ensures the ontology runtime framework (core/) remains domain-agnostic.
"""
import os
import re
import pytest


def _get_python_files(directory: str):
    """Yield all .py files in directory recursively."""
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f.endswith('.py'):
                yield os.path.join(root, f)


def test_core_has_no_app_imports():
    """Verify that core/ has zero imports from app/."""
    core_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'core')
    if not os.path.isdir(core_dir):
        pytest.skip("core/ directory not found")

    violations = []
    app_import_pattern = re.compile(r'^\s*(from|import)\s+app[\.\s]', re.MULTILINE)

    for filepath in _get_python_files(core_dir):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        matches = app_import_pattern.findall(content)
        if matches:
            rel_path = os.path.relpath(filepath, core_dir)
            violations.append(rel_path)

    assert not violations, (
        f"core/ must not import from app/. Violations found in:\n"
        + "\n".join(f"  - core/{v}" for v in violations)
    )
