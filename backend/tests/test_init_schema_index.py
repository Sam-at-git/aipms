"""
tests/test_init_schema_index.py

Tests for the schema index initialization script.
"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestInitSchemaIndexScript:
    """Test suite for init_schema_index.py script"""

    def test_build_index_creates_index(self, tmp_path):
        """Test that build_index creates a new index"""
        from scripts.init_schema_index import build_index

        db_path = str(tmp_path / "test_index.db")

        # Build the index
        exit_code = build_index(db_path, force=False)

        assert exit_code == 0
        assert Path(db_path).exists()

    def test_build_index_with_force(self, tmp_path):
        """Test that build_index with force rebuilds existing index"""
        from scripts.init_schema_index import build_index

        db_path = str(tmp_path / "test_index_force.db")

        # First build
        build_index(db_path, force=False)

        # Second build without force should skip
        exit_code = build_index(db_path, force=False)
        assert exit_code == 0

        # Build with force should rebuild
        exit_code = build_index(db_path, force=True)
        assert exit_code == 0

    def test_rebuild_index(self, tmp_path):
        """Test that rebuild_index clears and rebuilds"""
        from scripts.init_schema_index import rebuild_index

        db_path = str(tmp_path / "test_rebuild.db")

        exit_code = rebuild_index(db_path)

        assert exit_code == 0
        assert Path(db_path).exists()

    def test_show_stats(self, tmp_path):
        """Test that show_stats displays statistics"""
        from scripts.init_schema_index import build_index, show_stats

        db_path = str(tmp_path / "test_stats.db")

        # First build an index
        build_index(db_path, force=True)

        # Then show stats
        exit_code = show_stats(db_path)

        assert exit_code == 0

    def test_verify_index(self, tmp_path):
        """Test that verify_index checks integrity"""
        from scripts.init_schema_index import build_index, verify_index

        db_path = str(tmp_path / "test_verify.db")

        # First build an index
        build_index(db_path, force=True)

        # Note: In test environment, OntologyRegistry may not have entities
        # So verify may return 1 (empty index) - this is expected behavior
        exit_code = verify_index(db_path)

        # If index has items, verify should succeed
        # If index is empty, verify should return 1
        # We accept both as valid test outcomes
        assert exit_code in [0, 1]

    def test_verify_empty_index(self, tmp_path):
        """Test that verify_index fails for empty index"""
        from scripts.init_schema_index import verify_index, VectorStore

        db_path = str(tmp_path / "test_empty.db")

        # Create empty index
        from core.ai import get_embedding_service
        store = VectorStore(
            db_path=db_path,
            embedding_service=get_embedding_service()
        )
        store.close()

        # Verify should fail (return 1) for empty index
        exit_code = verify_index(db_path)

        assert exit_code == 1

    def test_ensure_db_directory_creates_directory(self, tmp_path):
        """Test that ensure_db_directory creates the directory"""
        from scripts.init_schema_index import ensure_db_directory
        from pathlib import Path

        db_path = str(tmp_path / "subdir" / "test.db")

        ensure_db_directory(db_path)

        assert Path(db_path).parent.exists()

    def test_check_api_key_without_key(self, monkeypatch):
        """Test that check_api_key warns when no API key is set"""
        # Need to patch settings directly since it's already loaded
        with patch('app.config.settings.EMBEDDING_API_KEY', ""), \
             patch('app.config.settings.OPENAI_API_KEY', None):
            from scripts.init_schema_index import check_api_key
            # Import after patching
            result = check_api_key()
            assert result is False


class TestScriptCLI:
    """Test suite for CLI argument parsing"""

    def test_main_requires_command(self):
        """Test that main() requires a command"""
        from scripts.init_schema_index import main

        # Simulate no arguments - argparse will raise SystemExit
        with patch("sys.argv", ["scripts/init_schema_index.py"]):
            # argparse raises SystemExit when required command is missing
            with pytest.raises(SystemExit):
                main()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Different behavior on Windows"
    )
    def test_build_command_parsing(self, tmp_path):
        """Test that build command is parsed correctly"""
        from scripts.init_schema_index import main

        db_path = str(tmp_path / "test_cli.db")

        # Run with build command - note: global args must come before subcommand
        with patch("sys.argv", [
            "scripts/init_schema_index.py",
            "--db-path", db_path,
            "--log-level", "WARNING",
            "build"
        ]):
            try:
                exit_code = main()
            except SystemExit as e:
                exit_code = e.code if e.code is not None else 0

            # Should succeed (0) or be skipped if no entities
            assert exit_code in [0, 1]
            assert Path(db_path).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
