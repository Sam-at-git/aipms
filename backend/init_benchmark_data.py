"""
Benchmark 种子数据脚本
从 YAML 文件导入 benchmark suites 到数据库。
幂等：按 suite name 去重，已存在的 suite 不会重复插入。

用法:
    cd backend
    uv run python init_benchmark_data.py              # merge 模式（跳过已有）
    uv run python init_benchmark_data.py --replace    # replace 模式（清空后重新导入）
"""
import sys
from pathlib import Path

sys.path.insert(0, '.')

from app.database import SessionLocal, init_db

# 确保 ORM 模型全部注册（含外键依赖）
import app.hotel.models.ontology  # noqa
import app.models.benchmark  # noqa
import app.system.models  # noqa

# YAML 文件路径
BENCHMARK_YAML_DIR = Path(__file__).parent / "tests" / "benchmark"
YAML_FILES = [
    BENCHMARK_YAML_DIR / "benchmark_data.yaml",
    BENCHMARK_YAML_DIR / "query_benchmark_data.yaml",
]


def seed_benchmark_data(db, mode="merge"):
    """从 YAML 文件导入 benchmark 种子数据。

    Args:
        db: Database session
        mode: "merge"（跳过已存在的 suite）或 "replace"（清空后重新导入）
    """
    from app.services.benchmark_service import import_suites

    total_created_suites = 0
    total_created_cases = 0
    total_skipped = 0

    for yaml_path in YAML_FILES:
        if not yaml_path.exists():
            print(f"  [SKIP] {yaml_path.name} not found")
            continue

        yaml_content = yaml_path.read_text(encoding="utf-8")
        result = import_suites(db, yaml_content, mode=mode)

        total_created_suites += result["created_suites"]
        total_created_cases += result["created_cases"]
        total_skipped += result["skipped_suites"]

        print(f"  {yaml_path.name}: created {result['created_suites']} suites, "
              f"{result['created_cases']} cases, skipped {result['skipped_suites']}")

    return total_created_suites, total_created_cases, total_skipped


def main():
    mode = "replace" if "--replace" in sys.argv else "merge"

    print("=" * 50)
    print(f"Benchmark 种子数据 (mode={mode})")
    print("=" * 50)

    # 确保表存在
    init_db()

    db = SessionLocal()
    try:
        created_suites, created_cases, skipped = seed_benchmark_data(db, mode=mode)
        print(f"\n新建: {created_suites} suites, {created_cases} cases")
        if skipped:
            print(f"跳过: {skipped} suites (已存在)")
        print("=" * 50)
    finally:
        db.close()


if __name__ == "__main__":
    main()
