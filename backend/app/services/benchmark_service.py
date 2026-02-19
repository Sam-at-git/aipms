"""
Benchmark 服务 — AI 预期生成 + YAML 导入/导出
"""
import json
from typing import Dict, List, Optional

import yaml
from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models.benchmark import BenchmarkSuite, BenchmarkCase

# DB schema description for the LLM prompt
DB_SCHEMA_PROMPT = """
## Database Tables

### rooms
- room_number (VARCHAR, unique): e.g. "201", "305"
- floor (INTEGER)
- room_type_id (FK → room_types.id)
- status (ENUM): "vacant_clean", "occupied", "vacant_dirty", "out_of_order"
- is_active (BOOLEAN)

### room_types
- id, name (VARCHAR): "标间", "大床房", "豪华间"
- base_price (DECIMAL)

### guests
- name (VARCHAR), phone, id_type, id_number
- tier (ENUM): "normal", "silver", "gold", "platinum"

### reservations
- reservation_no (VARCHAR), guest_id (FK), room_type_id (FK)
- check_in_date (DATE), check_out_date (DATE)
- status (ENUM): "confirmed", "checked_in", "completed", "cancelled", "no_show"
- total_amount, prepaid_amount

### stay_records
- guest_id (FK → guests.id), room_id (FK → rooms.id)
- reservation_id (FK, nullable)
- check_in_time (DATETIME), check_out_time (DATETIME, nullable)
- expected_check_out (DATETIME)
- deposit_amount (DECIMAL)
- status (ENUM): "active", "checked_out"

### bills
- stay_record_id (FK → stay_records.id)
- total_amount, paid_amount, adjustment_amount
- is_settled (BOOLEAN)

### payments
- bill_id (FK → bills.id)
- amount (DECIMAL), method (ENUM): "cash", "card", "wechat", "alipay", "bank_transfer"

### tasks
- room_id (FK → rooms.id)
- task_type (ENUM): "cleaning", "maintenance"
- status (ENUM): "pending", "in_progress", "completed", "cancelled"
- assignee_id (FK → employees.id, nullable)

### employees
- username, name, role (ENUM): "sysadmin", "manager", "receptionist", "cleaner"
"""

ASSERTION_SYSTEM_PROMPT = f"""你是一个测试断言生成器。根据用户的自然语言指令，生成用于验证 AI 执行结果的断言。

{DB_SCHEMA_PROMPT}

## 输出格式（JSON）

生成的断言包含两部分：
1. **verify_db**: SQL 查询验证数据库状态变化（L3断言）
2. **response_contains / response_not_contains**: 验证 AI 回复内容（L4断言）
3. **suggested_follow_up_fields**: 如果指令可能需要补充参数（如 missing_fields），建议的字段值

## 规则
- verify_db 中的 SQL 必须是 SELECT 语句
- expect.values 中的枚举值使用小写（如 "occupied" 而非 "OCCUPIED"）
- response_contains 包含预期出现在回复中的关键词
- response_not_contains 包含不应出现的关键词（通常是 "失败"、"错误"）
- 对于 mutation 操作，verify_db 至少包含一条验证
- 对于 query 操作，可以只有 response_contains

请严格返回 JSON，不要其他文字。"""


def generate_assertions(input_text: str, case_type: Optional[str] = "mutation") -> dict:
    """Call LLM to generate test assertions for a benchmark case.

    Args:
        input_text: Natural language instruction (e.g. "帮张三办理201房间入住")
        case_type: "mutation" or "query"

    Returns:
        Dict with "assertions" and "suggested_follow_up_fields" keys
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key or not settings.ENABLE_LLM:
        raise RuntimeError("LLM 未启用，无法生成断言")

    client = OpenAI(
        api_key=api_key,
        base_url=settings.OPENAI_BASE_URL,
        timeout=30.0,
    )

    user_prompt = f"指令类型: {case_type}\n指令内容: {input_text}"

    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": ASSERTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model=settings.LLM_MODEL,
        temperature=0.3,  # Lower temperature for structured output
        max_tokens=settings.LLM_MAX_TOKENS,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    result = json.loads(content)

    # Normalize structure
    assertions = {}
    if "assertions" in result:
        assertions = result["assertions"]
    else:
        # LLM may return flat structure
        assertions = {
            "verify_db": result.get("verify_db", []),
            "response_contains": result.get("response_contains", []),
            "response_not_contains": result.get("response_not_contains", []),
        }

    suggested_fields = result.get("suggested_follow_up_fields", {})

    return {
        "assertions": assertions,
        "suggested_follow_up_fields": suggested_fields,
    }


# ============== YAML Import/Export ==============

def export_suites(db: Session, suite_ids: Optional[List[int]] = None) -> str:
    """Export suites to YAML string.

    Args:
        db: Database session
        suite_ids: Optional list of suite IDs to export. None = export all.

    Returns:
        YAML string
    """
    query = db.query(BenchmarkSuite)
    if suite_ids:
        query = query.filter(BenchmarkSuite.id.in_(suite_ids))
    suites = query.order_by(BenchmarkSuite.id).all()

    data = {"suites": []}
    for suite in suites:
        suite_data = {
            "name": suite.name,
            "category": suite.category,
            "description": suite.description,
            "init_script": suite.init_script,
            "cases": [],
        }
        for case in suite.cases:
            case_data = {
                "name": case.name,
                "input": case.input,
            }
            if case.run_as:
                case_data["run_as"] = case.run_as
            case_data["assertions"] = json.loads(case.assertions) if case.assertions else {}
            if case.follow_up_fields:
                case_data["follow_up_fields"] = json.loads(case.follow_up_fields)
            suite_data["cases"].append(case_data)
        data["suites"].append(suite_data)

    return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)


def import_suites(db: Session, yaml_content: str, mode: str = "merge") -> Dict:
    """Import suites from YAML string.

    Args:
        db: Database session
        yaml_content: YAML string
        mode: "merge" (add new, skip existing by name) or "replace" (delete all, reimport)

    Returns:
        Dict with import statistics
    """
    data = yaml.safe_load(yaml_content)

    raw_suites = data.get("suites", [])

    if mode == "replace":
        db.query(BenchmarkCase).delete()
        db.query(BenchmarkSuite).delete()
        db.commit()

    created_suites = 0
    created_cases = 0
    skipped_suites = 0

    for suite_data in raw_suites:
        name = suite_data.get("name", "")

        if mode == "merge":
            existing = db.query(BenchmarkSuite).filter_by(name=name).first()
            if existing:
                skipped_suites += 1
                continue

        suite = BenchmarkSuite(
            name=name,
            category=suite_data.get("category", "未分类"),
            description=suite_data.get("description"),
            init_script=suite_data.get("init_script") or suite_data.get("reset_script"),
        )
        db.add(suite)
        db.flush()  # Get suite.id

        for i, case_data in enumerate(suite_data.get("cases", []), start=1):
            assertions = case_data.get("assertions", {})
            follow_up = case_data.get("follow_up_fields")

            case = BenchmarkCase(
                suite_id=suite.id,
                sequence_order=i,
                name=case_data.get("name", f"Case {i}"),
                input=case_data.get("input", ""),
                run_as=case_data.get("run_as"),
                assertions=json.dumps(assertions, ensure_ascii=False),
                follow_up_fields=json.dumps(follow_up, ensure_ascii=False) if follow_up else None,
            )
            db.add(case)
            created_cases += 1

        created_suites += 1

    db.commit()
    return {
        "created_suites": created_suites,
        "created_cases": created_cases,
        "skipped_suites": skipped_suites,
    }


