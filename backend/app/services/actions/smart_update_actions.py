"""
app/services/actions/smart_update_actions.py

Generic smart update factory - auto-registers update_{entity}_smart actions
for all entities with smart_update config in OntologyRegistry extensions.

One generic implementation powers all entities, reading field metadata
from PropertyMetadata at runtime.
"""
import json
import importlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from sqlalchemy.orm import Session

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee
from app.services.actions.base import SmartUpdateParams
from app.services.llm_service import LLMService

if TYPE_CHECKING:
    from core.ontology.registry import OntologyRegistry

logger = logging.getLogger(__name__)


@dataclass
class SmartUpdateConfig:
    """Parsed config from entity extensions['smart_update']."""
    entity_name: str
    name_column: str
    editable_fields: List[str]
    update_schema: str
    service_class: str
    service_method: str
    allowed_roles: Set[str]
    display_name: str
    action_description: str = ""
    glossary_examples: Optional[List[Dict[str, str]]] = None


def parse_smart_update_config(entity_name: str, raw: Dict[str, Any]) -> Optional[SmartUpdateConfig]:
    """Parse smart_update extension dict into SmartUpdateConfig."""
    if not raw or not raw.get("enabled"):
        return None
    return SmartUpdateConfig(
        entity_name=entity_name,
        name_column=raw.get("identifier_fields", {}).get("name_column", "name"),
        editable_fields=raw.get("editable_fields", []),
        update_schema=raw.get("update_schema", ""),
        service_class=raw.get("service_class", ""),
        service_method=raw.get("service_method", ""),
        allowed_roles=set(raw.get("allowed_roles", set())),
        display_name=raw.get("display_name", entity_name),
        action_description=raw.get("action_description", ""),
        glossary_examples=raw.get("glossary_examples"),
    )


def build_smart_update_prompt(
    config: SmartUpdateConfig,
    entity_instance: Any,
    instructions: str,
    ontology_registry: "OntologyRegistry",
) -> str:
    """
    Build LLM prompt dynamically from PropertyMetadata.

    Uses display_name for Chinese labels, type for type hints.
    Injects current values from the entity instance.
    """
    entity_meta = ontology_registry.get_entity(config.entity_name)

    # Build field descriptions from PropertyMetadata
    field_lines = []
    json_fields = []
    for field_name in config.editable_fields:
        prop = entity_meta.get_property(field_name) if entity_meta else None
        display = prop.display_name if prop and prop.display_name else field_name
        current_val = getattr(entity_instance, field_name, None) or "无"
        field_lines.append(f"- {display} ({field_name}): {current_val}")
        json_fields.append(f'    "new_{field_name}": "新{display}（如果不修改则为null）"')

    fields_text = "\n".join(field_lines)
    json_template = "{\n" + ",\n".join(json_fields) + ',\n    "explanation": "修改说明"\n}'

    return f"""你是酒店管理系统的修改意图解析器。

当前{config.display_name}信息：
{fields_text}

用户的修改指令：
{instructions}

请根据修改指令，一步一步计算出新值：
1. 先明确当前值的每一个字符
2. 确定要替换的位置和内容
3. 执行替换并验证结果长度正确

替换规则：
- "后N位改为X" → 保留前面(总长度-N)个字符 + X。例：13912345611 后三位改为888 → 13912345（前8位） + 888 = 13912345888
- "前缀改为X" → X + 保留后面的字符（保持总长度不变）。例：13912345888 前缀改为159 → 159 + 12345888 = 15912345888
- "改为xxx" → 完全替换为xxx
- 如果当前值为"无"，则直接使用新值

只返回JSON格式：
{json_template}

如果某个字段没有对应的修改指令，设为null。"""


def _resolve_service(config: SmartUpdateConfig, db: Session):
    """Import and instantiate the service class."""
    module_path, class_name = config.service_class.rsplit(".", 1)
    module = importlib.import_module(module_path)
    service_cls = getattr(module, class_name)
    return service_cls(db)


def _resolve_update_schema(config: SmartUpdateConfig):
    """Import the update Pydantic schema."""
    import app.models.schemas as schemas_module
    return getattr(schemas_module, config.update_schema)


def _find_entity(
    config: SmartUpdateConfig,
    params: SmartUpdateParams,
    db: Session,
    ontology_registry: "OntologyRegistry",
) -> Dict[str, Any]:
    """
    Find entity by id or name. Returns dict with 'entity' or error info.
    """
    model_class = ontology_registry.get_model(config.entity_name)
    if model_class is None:
        return {"error": f"未找到实体模型: {config.entity_name}"}

    entity = None

    if params.entity_id:
        entity = db.get(model_class, params.entity_id)
        if not entity:
            return {
                "error": f"未找到ID为 {params.entity_id} 的{config.display_name}",
                "error_code": "not_found",
            }
    elif params.entity_name:
        name_col = getattr(model_class, config.name_column, None)
        if name_col is None:
            return {"error": f"实体 {config.entity_name} 没有名称列 {config.name_column}"}

        # Exact match first
        candidates = db.query(model_class).filter(name_col == params.entity_name).all()
        if not candidates:
            # Fuzzy match
            candidates = db.query(model_class).filter(
                name_col.like(f"%{params.entity_name}%")
            ).all()

        if len(candidates) == 0:
            return {
                "error": f"未找到名为「{params.entity_name}」的{config.display_name}",
                "error_code": "not_found",
            }
        elif len(candidates) > 1:
            name_attr = config.name_column
            candidate_list = [
                {"id": getattr(c, "id", None), "name": getattr(c, name_attr, "")}
                for c in candidates
            ]
            return {
                "error": f"找到多个名为「{params.entity_name}」的{config.display_name}，请确认：",
                "error_code": "ambiguous",
                "candidates": candidate_list,
            }
        else:
            entity = candidates[0]
    else:
        return {
            "error": f"请提供{config.display_name}ID或名称",
            "error_code": "missing_identifier",
        }

    return {"entity": entity}


def register_smart_update_actions(
    registry: ActionRegistry,
    ontology_registry: "OntologyRegistry",
) -> None:
    """
    Factory entry point: iterate all entities in OntologyRegistry,
    register update_{entity_lower}_smart for those with smart_update enabled.
    """
    entities = ontology_registry.get_entities()

    for entity_meta in entities:
        raw_config = entity_meta.extensions.get("smart_update")
        config = parse_smart_update_config(entity_meta.name, raw_config)
        if config is None:
            continue

        _register_one(registry, ontology_registry, config)

    logger.info("Smart update factory: registration complete")


def _register_one(
    registry: ActionRegistry,
    ontology_registry: "OntologyRegistry",
    config: SmartUpdateConfig,
) -> None:
    """Register a single update_{entity}_smart action."""
    action_name = f"update_{config.entity_name.lower()}_smart"
    entity_name = config.entity_name
    display_name = config.display_name

    # Capture config and ontology_registry in closure
    _config = config
    _ont_reg = ontology_registry

    # Use domain-provided description or generate default
    description = _config.action_description or (
        f"智能更新{display_name}信息。当用户描述的是相对修改、部分修改等无法直接得出完整新值的指令时使用。"
    )
    glossary = _config.glossary_examples or []

    @registry.register(
        name=action_name,
        entity=entity_name,
        description=description,
        category="mutation",
        requires_confirmation=True,
        allowed_roles=_config.allowed_roles,
        undoable=False,
        side_effects=[f"updates_{entity_name.lower()}"],
        search_keywords=[f"修改{display_name}", f"更新{display_name}", "智能修改", "部分修改",
                         "后几位改为", "前缀改为", "改一下"],
        semantic_category="update_style",
        category_description="更新方式（直接赋值 vs 智能解析修改指令）",
        glossary_examples=glossary,
    )
    def handle_smart_update(
        params: SmartUpdateParams,
        db: Session,
        user: Employee,
        **context,
    ) -> Dict[str, Any]:
        return _execute_smart_update(params, db, user, _config, _ont_reg)


def _execute_smart_update(
    params: SmartUpdateParams,
    db: Session,
    user: Employee,
    config: SmartUpdateConfig,
    ontology_registry: "OntologyRegistry",
) -> Dict[str, Any]:
    """
    Generic smart update execution:
    1. Find entity
    2. Build LLM prompt from metadata + current values
    3. Parse LLM JSON response
    4. Validate via ConstraintEngine
    5. Apply via service
    """
    # 1. Find entity
    lookup = _find_entity(config, params, db, ontology_registry)
    if "error" in lookup:
        result = {
            "success": False,
            "message": lookup["error"],
            "error": lookup.get("error_code", "lookup_error"),
        }
        if "candidates" in lookup:
            result["requires_confirmation"] = True
            result["action"] = f"select_{config.entity_name.lower()}"
            result["candidates"] = lookup["candidates"]
        return result

    entity = lookup["entity"]

    # 2. Build LLM prompt
    prompt = build_smart_update_prompt(config, entity, params.instructions, ontology_registry)

    # 3. Call LLM
    llm_service = LLMService()
    if not llm_service.is_enabled():
        return {
            "success": False,
            "message": f"LLM 服务未启用，无法解析复杂修改指令。请使用 update_{config.entity_name.lower()} 动作直接提供完整的新值。",
            "error": "llm_disabled",
        }

    try:
        from app.config import settings
        response = llm_service.client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是精确的数据修改解析器，只返回纯JSON格式。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"LLM call failed in smart update: {e}")
        return {
            "success": False,
            "message": f"LLM 解析失败: {str(e)}",
            "error": "llm_error",
        }

    # 4. Extract update fields from LLM response
    update_fields = {}
    changes = []
    entity_meta = ontology_registry.get_entity(config.entity_name)

    for field_name in config.editable_fields:
        new_val = result.get(f"new_{field_name}")
        if new_val is not None:
            update_fields[field_name] = new_val
            prop = entity_meta.get_property(field_name) if entity_meta else None
            label = prop.display_name if prop and prop.display_name else field_name
            old_val = getattr(entity, field_name, None) or "无"
            if old_val and str(old_val) != "无":
                changes.append(f"{label}: {old_val} → {new_val}")
            else:
                changes.append(f"{label}: 设置为 {new_val}")

    if not update_fields:
        return {
            "success": False,
            "message": "LLM 未解析出任何需要修改的字段",
            "error": "no_updates",
        }

    # 5. Constraint validation
    from core.reasoning.constraint_engine import ConstraintEngine

    constraint_engine = ConstraintEngine(ontology_registry)
    user_context = {"role": user.role.value if hasattr(user.role, "value") else user.role}

    for field_name, new_value in update_fields.items():
        old_value = getattr(entity, field_name, None)
        if new_value == old_value:
            continue

        decision = constraint_engine.validate_property_update(
            entity_type=config.entity_name,
            property_name=field_name,
            old_value=old_value,
            new_value=new_value,
            user_context=user_context,
            db=db,
            entity_id=entity.id,
        )

        if not decision.allowed:
            response_dict = decision.to_response_dict()
            response_dict["explanation"] = result.get("explanation", "")
            return response_dict

    # 6. Apply update via service
    try:
        update_schema_cls = _resolve_update_schema(config)
        update_data = update_schema_cls(**update_fields)

        service = _resolve_service(config, db)
        update_method = getattr(service, config.service_method)
        updated = update_method(entity.id, update_data)

        name_val = getattr(updated, config.name_column, str(entity.id))

        return {
            "success": True,
            "message": f"已更新{config.display_name}「{name_val}」的信息：{'；'.join(changes)}",
            f"{config.entity_name.lower()}_id": updated.id,
            f"{config.entity_name.lower()}_name": name_val,
            "updated_fields": update_fields,
            "changes": changes,
            "explanation": result.get("explanation", ""),
        }
    except Exception as e:
        logger.error(f"Smart update apply failed: {e}")
        return {
            "success": False,
            "message": f"更新失败: {str(e)}",
            "error": "execution_error",
        }


__all__ = ["register_smart_update_actions", "SmartUpdateConfig", "build_smart_update_prompt"]
