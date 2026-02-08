"""
scripts/init_schema_index.py

Schema index management CLI.

Provides commands to build, rebuild, verify, and show statistics
for the semantic search index used by SchemaRetriever.
"""
import argparse
import sys
import os
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.schema_index_service import SchemaIndexService
from core.ai import VectorStore, get_embedding_service


logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO"):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def ensure_db_directory(db_path: str) -> None:
    """Ensure the directory for the database file exists"""
    db_path_obj = Path(db_path)
    if db_path_obj != ":memory:":
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)


def check_api_key() -> bool:
    """Check if API key is available for embedding"""
    from app.config import settings

    api_key = settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY
    if not api_key:
        logger.warning("No API key found. EMBEDDINGS will be zero vectors (for testing).")
        logger.warning("Set EMBEDDING_API_KEY or OPENAI_API_KEY environment variable.")
        return False
    return True


def build_index(db_path: str, force: bool = False) -> int:
    """
    Build the schema index

    Args:
        db_path: Path to the database file
        force: Rebuild even if index exists

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger.info(f"Building schema index at: {db_path}")

    # Check API key
    has_api_key = check_api_key()

    # Ensure directory exists
    ensure_db_directory(db_path)

    try:
        # Create vector store
        vector_store = VectorStore(
            db_path=db_path,
            embedding_service=get_embedding_service()
        )

        # Check if index already exists
        stats = vector_store.get_stats()
        if stats["total_items"] > 0 and not force:
            logger.info(f"Index already exists with {stats['total_items']} items")
            logger.info("Use --force to rebuild or 'rebuild' command to clear and rebuild")
            return 0

        # Create index service
        service = SchemaIndexService(vector_store=vector_store)

        # Build the index
        service.build_index()

        # Show results
        final_stats = service.get_stats()
        logger.info(f"✓ Index built successfully!")
        logger.info(f"  Total items: {final_stats['total_items']}")
        logger.info(f"  By type/entity:")
        for key, count in final_stats.get('by_type_entity', {}).items():
            logger.info(f"    - {key}: {count}")

        return 0

    except Exception as e:
        logger.error(f"Failed to build index: {e}")
        import traceback
        traceback.print_exc()
        return 1


def rebuild_index(db_path: str) -> int:
    """
    Rebuild the schema index (clear and build)

    Args:
        db_path: Path to the database file

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger.info(f"Rebuilding schema index at: {db_path}")

    # Check API key
    check_api_key()

    # Ensure directory exists
    ensure_db_directory(db_path)

    try:
        # Create vector store
        vector_store = VectorStore(
            db_path=db_path,
            embedding_service=get_embedding_service()
        )

        # Create index service
        service = SchemaIndexService(vector_store=vector_store)

        # Rebuild
        service.rebuild_index()

        # Show results
        final_stats = service.get_stats()
        logger.info(f"✓ Index rebuilt successfully!")
        logger.info(f"  Total items: {final_stats['total_items']}")
        logger.info(f"  By type/entity:")
        for key, count in final_stats.get('by_type_entity', {}).items():
            logger.info(f"    - {key}: {count}")

        return 0

    except Exception as e:
        logger.error(f"Failed to rebuild index: {e}")
        import traceback
        traceback.print_exc()
        return 1


def show_stats(db_path: str) -> int:
    """
    Show index statistics

    Args:
        db_path: Path to the database file

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        vector_store = VectorStore(
            db_path=db_path,
            embedding_service=get_embedding_service()
        )

        stats = vector_store.get_stats()

        print("\n=== Schema Index Statistics ===")
        print(f"Database: {db_path}")
        print(f"Total items: {stats['total_items']}")
        print(f"Embedding dimension: {stats['embedding_dim']}")
        print(f"Cache size: {stats.get('cache_size', 'N/A')}")

        if stats.get('by_type_entity'):
            print("\nBy type/entity:")
            for key, count in sorted(stats['by_type_entity'].items()):
                print(f"  {key}: {count}")

        print()

        return 0

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return 1


def verify_index(db_path: str) -> int:
    """
    Verify index integrity

    Args:
        db_path: Path to the database file

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger.info(f"Verifying index at: {db_path}")

    try:
        vector_store = VectorStore(
            db_path=db_path,
            embedding_service=get_embedding_service()
        )

        stats = vector_store.get_stats()

        if stats["total_items"] == 0:
            logger.warning("⚠ Index is empty")
            return 1

        # Check if we have entities
        items = vector_store.list_items(item_type="entity")
        if not items:
            logger.warning("⚠ No entities found in index")
            return 1

        # Check if we have properties
        properties = vector_store.list_items(item_type="property")
        if not properties:
            logger.warning("⚠ No properties found in index")
            return 1

        # Check if we have actions
        actions = vector_store.list_items(item_type="action")
        if not actions:
            logger.warning("⚠ No actions found in index")
            return 1

        logger.info(f"✓ Index is healthy!")
        logger.info(f"  Entities: {len(items)}")
        logger.info(f"  Properties: {len(properties)}")
        logger.info(f"  Actions: {len(actions)}")

        return 0

    except Exception as e:
        logger.error(f"✗ Index verification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Schema index management for semantic search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.init_schema_index build
  python -m scripts.init_schema_index rebuild --force
  python -m scripts.init_schema_index stats
  python -m scripts.init_schema_index verify
        """
    )

    parser.add_argument(
        "--db-path",
        default="backend/data/schema_index.db",
        help="Path to the index database (default: backend/data/schema_index.db)"
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.required = True

    # build command
    build_parser = subparsers.add_parser("build", help="Build the schema index")
    build_parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even if index exists"
    )

    # rebuild command
    subparsers.add_parser("rebuild", help="Clear and rebuild the schema index")

    # stats command
    subparsers.add_parser("stats", help="Show index statistics")

    # verify command
    subparsers.add_parser("verify", help="Verify index integrity")

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Execute command
    if args.command == "build":
        return build_index(args.db_path, args.force)
    elif args.command == "rebuild":
        return rebuild_index(args.db_path)
    elif args.command == "stats":
        return show_stats(args.db_path)
    elif args.command == "verify":
        return verify_index(args.db_path)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
